import json
import re
import asyncio
import os
import random
import time
from openai import OpenAI
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from .utils import clean_html_for_ai
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, SITE_COOKIES
from .rankings import get_ranking, CCF_RANKINGS, get_venue_score # Updated Import
from .observability import get_logger

from curl_cffi.requests import AsyncSession

logger = get_logger(__name__)

FETCH_MAX_RETRIES = int(os.getenv("SCRAPER_FETCH_RETRIES", "3"))
AI_MAX_RETRIES = int(os.getenv("SCRAPER_AI_RETRIES", "3"))
BACKOFF_BASE_SECONDS = float(os.getenv("SCRAPER_BACKOFF_SECONDS", "1.5"))
PER_HOST_DELAY_SECONDS = float(os.getenv("SCRAPER_PER_HOST_DELAY_SECONDS", "1.0"))

_last_request_at: Dict[str, float] = {}
_rate_limit_lock = asyncio.Lock()


class ScraperError(Exception):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        error_type: str,
        retryable: bool = True,
        attempts: int = 1,
        url: str = "",
    ):
        super().__init__(message)
        self.stage = stage
        self.error_type = error_type
        self.retryable = retryable
        self.attempts = attempts
        self.url = url


def _backoff_delay(attempt: int) -> float:
    jitter = random.uniform(0, 0.35)
    return BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1)) + jitter


def _classify_exception(error: Exception, status_code: int = None) -> tuple[str, bool]:
    text = str(error).lower()
    if status_code == 429 or "rate limit" in text or "too many requests" in text:
        return "rate_limited", True
    if status_code in {401, 403}:
        return "access_denied", False
    if status_code and 400 <= status_code < 500:
        return "client_error", False
    if status_code and status_code >= 500:
        return "server_error", True
    if "timeout" in text or "timed out" in text:
        return "timeout", True
    if "json" in text:
        return "invalid_json", True
    if "connection" in text or "network" in text or "tls" in text:
        return "network_error", True
    return "unknown_error", True


async def _rate_limit(url: str) -> None:
    if PER_HOST_DELAY_SECONDS <= 0:
        return

    host = urlparse(url).netloc or url
    async with _rate_limit_lock:
        now = time.monotonic()
        last_seen = _last_request_at.get(host, 0)
        wait_for = PER_HOST_DELAY_SECONDS - (now - last_seen)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _last_request_at[host] = time.monotonic()


async def _get_with_retries(session: AsyncSession, request_url: str, *, source_url: str, headers=None, timeout=30):
    last_error = None
    for attempt in range(1, FETCH_MAX_RETRIES + 1):
        await _rate_limit(source_url)
        try:
            response = await session.get(request_url, timeout=timeout, headers=headers)
            if response.status_code >= 400:
                error_type, retryable = _classify_exception(Exception(response.reason), response.status_code)
                raise ScraperError(
                    f"HTTP {response.status_code}: {response.reason}",
                    stage="fetch",
                    error_type=error_type,
                    retryable=retryable,
                    attempts=attempt,
                    url=source_url,
                )
            return response
        except ScraperError as e:
            last_error = e
            if not e.retryable or attempt >= FETCH_MAX_RETRIES:
                raise
            logger.warning("fetch_retry url=%s attempt=%s error_type=%s error=%s", source_url, attempt, e.error_type, e)
        except Exception as e:
            error_type, retryable = _classify_exception(e)
            last_error = ScraperError(
                str(e),
                stage="fetch",
                error_type=error_type,
                retryable=retryable,
                attempts=attempt,
                url=source_url,
            )
            if not retryable or attempt >= FETCH_MAX_RETRIES:
                raise last_error from e
            logger.warning("fetch_retry url=%s attempt=%s error_type=%s error=%s", source_url, attempt, error_type, e)

        await asyncio.sleep(_backoff_delay(attempt))

    raise last_error or ScraperError(
        "fetch failed",
        stage="fetch",
        error_type="unknown_error",
        retryable=True,
        attempts=FETCH_MAX_RETRIES,
        url=source_url,
    )


async def _fetch_arxiv_listing(source_url: str) -> str:
    match = re.search(r"list/([^/]+)", source_url)
    if not match:
        raise ScraperError(
            "Could not parse arxiv category from URL",
            stage="fetch",
            error_type="client_error",
            retryable=False,
            url=source_url,
        )

    category = match.group(1)
    from datetime import datetime, timedelta, timezone

    html_parts = [f"<html><body><h1>Arxiv {category} Recent Papers</h1>"]
    offset = 0
    max_results = 20
    fetched_count = 0
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=72)
    stop_fetching = False

    logger.info("arxiv_fetch_start url=%s category=%s cutoff=%s", source_url, category, cutoff_date.date())

    async with AsyncSession(impersonate="chrome120") as session:
        while not stop_fetching and fetched_count < 100:
            api_url = (
                "http://export.arxiv.org/api/query?"
                f"search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending"
                f"&start={offset}&max_results={max_results}"
            )
            response = await _get_with_retries(session, api_url, source_url=source_url)
            try:
                root = ET.fromstring(response.content)
            except Exception as e:
                raise ScraperError(
                    str(e),
                    stage="fetch",
                    error_type="invalid_xml",
                    retryable=True,
                    url=source_url,
                ) from e

            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            entries = root.findall("atom:entry", ns)
            if not entries:
                break

            batch_valid_count = 0
            for entry in entries:
                published = entry.find("atom:published", ns)
                title_node = entry.find("atom:title", ns)
                summary_node = entry.find("atom:summary", ns)
                link_node = entry.find("atom:id", ns)
                if published is None or title_node is None or summary_node is None or link_node is None:
                    continue

                published_str = published.text.strip()
                try:
                    pub_date = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except Exception:
                    pub_date = datetime.now(timezone.utc)

                if pub_date < cutoff_date:
                    stop_fetching = True
                    break

                batch_valid_count += 1
                fetched_count += 1

                title = title_node.text.strip().replace("\n", " ")
                summary = summary_node.text.strip().replace("\n", " ")
                link = link_node.text.strip()

                venue_info = []
                journal_ref = entry.find("arxiv:journal_ref", ns)
                comment = entry.find("arxiv:comment", ns)
                if journal_ref is not None and journal_ref.text:
                    venue_info.append(f"Journal: {journal_ref.text}")
                if comment is not None and comment.text:
                    venue_info.append(f"Comment: {comment.text}")

                venue_str = " | ".join(venue_info)
                if venue_str:
                    venue_str = get_ranking(venue_str)

                html_parts.append("<article>")
                html_parts.append(f"<h2>{title}</h2>")
                html_parts.append(f"<p>Date: {published_str}</p>")
                html_parts.append(f"<p>Venue: {venue_str}</p>")
                html_parts.append(f"<p>Link: {link}</p>")
                html_parts.append(f"<div>{summary}</div>")
                html_parts.append("</article><hr/>")

            logger.info("arxiv_fetch_batch url=%s offset=%s count=%s total=%s", source_url, offset, batch_valid_count, fetched_count)
            if batch_valid_count < len(entries):
                stop_fetching = True
            offset += max_results

    html_parts.append("</body></html>")
    return "".join(html_parts)


async def fetch_webpage(url: str, raise_on_error: bool = False) -> str:
    source_url = url
    try:
        if "newsroom.tiktok.com" in url and "_data" not in url:
            url = f"{url.split('?')[0]}?_data=routes%2F_app._index&lang=en"
            logger.info("fetch_tiktok_data_endpoint source_url=%s request_url=%s", source_url, url)

        if "arxiv.org/list/" in source_url:
            return await _fetch_arxiv_listing(source_url)

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        for domain, cookie in SITE_COOKIES.items():
            if domain in source_url and cookie:
                headers["Cookie"] = cookie
                logger.info("fetch_cookie_injected url=%s domain=%s", source_url, domain)
                break

        logger.info("fetch_start url=%s", source_url)
        async with AsyncSession(impersonate="chrome120") as session:
            response = await _get_with_retries(session, url, source_url=source_url, headers=headers, timeout=30)

        if "application/json" in response.headers.get("content-type", ""):
            try:
                data = response.json()
                if "mainArticle" in data:
                    article = data["mainArticle"]
                    logger.info("fetch_json_article_parsed url=%s", source_url)
                    return (
                        f"<h1>{article.get('title', '')}</h1>"
                        f"<p>Date: {article.get('publishedDate', '')}</p>"
                        f"<div>{article.get('content', '')}</div>"
                    )
            except Exception as e:
                logger.warning("fetch_json_parse_failed url=%s error=%s", source_url, e)
                return response.text

        return response.text
    except ScraperError as e:
        logger.error("fetch_failed url=%s error_type=%s retryable=%s attempts=%s error=%s", source_url, e.error_type, e.retryable, e.attempts, e)
        if raise_on_error:
            raise
        return ""
    except Exception as e:
        error_type, retryable = _classify_exception(e)
        scraper_error = ScraperError(
            str(e),
            stage="fetch",
            error_type=error_type,
            retryable=retryable,
            attempts=FETCH_MAX_RETRIES,
            url=source_url,
        )
        logger.error("fetch_failed url=%s error_type=%s retryable=%s error=%s", source_url, error_type, retryable, e)
        if raise_on_error:
            raise scraper_error from e
        return ""


async def _extract_news_with_ai_once(html: str, url: str, mode: str = "news", user_interests: List[str] = None) -> List[Dict[str, Any]]:
    """
    使用 AI 智能提取信息
    mode: "news" (默认新闻) 或 "paper" (科研论文)
    user_interests: 用户收藏夹关键词列表 (用于 Personal Score)
    """
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    
    # 获取今天日期
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    
    # Build Personal Context
    personal_context = ""
    if user_interests and len(user_interests) > 0:
        interest_str = ", ".join(user_interests[:20]) # Limit to top 20
        personal_context = f"\n   - `personal_score` (0-100): **用户个性化推荐分**。基于用户历史收藏关键词 ({interest_str}) 打分。越匹配越高。"
    else:
        personal_context = "\n   - `personal_score` (0-100): 默认为 0 (无用户偏好数据)。"

    # Helper function to query AI
    def _query_ai(text_content: str) -> List[Dict[str, Any]]:
        # 构造 CCF 上下文简表
        ccf_context = "Rankings Reference:\n"
        class_a = [k for k, v in CCF_RANKINGS.items() if v == "CCF A"]
        class_b = [k for k, v in CCF_RANKINGS.items() if v == "CCF B"]
        class_c = [k for k, v in CCF_RANKINGS.items() if v == "CCF C"]
        
        ccf_context += f"Class A (Top): {', '.join(class_a[:50])}\n"
        ccf_context += f"Class B (Excellent): {', '.join(class_b[:30])}\n"
        
        # --- PROMPT DESIGN ---
        if mode == "paper":
            prompt = f"""你是一个顶尖科研论文鉴赏专家。请从网页文本中提取论文列表，并进行深度评分。
任务要求：
1. 提取论文信息：
   - 标题 (title): 英文原题
   - 链接 (link): 必须是绝对路径。
   - 摘要 (summary): **中文总结**，侧重研究方法、贡献和创新点。
   - 日期 (date): 格式统一为 `YYYY-MM-DD`. 如果文中日期不明确，默认为今天 ({today_str}).
   - 发表处 (venue): 期刊/会议名称。
2. **深度评分 (Scoring)** for Impact:
   - `ai_score` (0-100): 语义相关性打分。用户兴趣点：**AI, Agent, HCI, XR/Spatial, Generation, Diffusion, 3D, VR, AR, MR, Spatial Computing, Brain, Recognition, Cognitive, Health, Sense Control, Emotion, Affective, Eye Tracking, Gesture, Face**. 相关度越高分数越高。
   - `impact_score` (0-50): 学术影响力。发表在 CCF A (如 CVPR, CHI, NeurIPS) 或 Top Journal (Nature/Science) 得 50 分；CCF B 得 25 分；一般会议 10 分；Arxiv 预印本 5 分。{personal_context}
   - `is_tech_release` (bool): 论文是否伴随代码发布(GitHub)、模型权重发布(HuggingFace)或 Demo 发布。
   - `code_url` (str): 如果 `is_tech_release` 为真，提取具体的开源链接 (GitHub/HuggingFace), 否则为 null.
   - `score_reason` (str): 一句话解释打分理由 (e.g., "Agent领域CCF A类论文，且开源代码").
   - `tags` (List[str]): 3-5个技术标签 (e.g. "LLM", "Vision", "Robotics", "Agent", "3D", "Hardware", "Audio", "RL").
3. 过滤非论文内容。只返回 JSON 数组。

参考：
{ccf_context}

网页内容：
{text_content[:60000]}

返回 JSON 格式：
[
    {{
        "title": "Paper Title",
        "link": "https://...",
        "summary": "中文技术总结...",
        "date": "2025-12-10",
        "venue": "CVPR 2025",
        "ai_score": 95,
        "impact_score": 50,
        "personal_score": 85,
        "is_tech_release": true,
        "code_url": "https://github.com/...",
        "score_reason": "High interest Agent paper in CVPR with Code.",
        "tags": ["Agent", "LLM", "Planning"]
    }}
]
"""
        else: # mode == "news"
            prompt = f"""你是一个前沿科技猎手。请从网页文本中提取新闻列表，并进行价值评估。
任务要求：
1. 提取新闻信息：
   - 标题 (title): 英文原题
   - 链接 (link): 必须是绝对路径。
   - 摘要 (summary): **中文总结**，侧重发生了什么事、产品发布或商业影响。
   - 日期 (date): 格式统一为 `YYYY-MM-DD`. 如果文中日期不明确，默认为今天 ({today_str}).
   - 来源 (venue): 新闻来源名称。
2. **深度评分 (Scoring)**：
   - `ai_score` (0-100): 语义相关性打分。用户兴趣点：**AI, Agent, HCI, XR/Spatial, Generation, Diffusion, 3D, VR, AR, MR, Spatial Computing, Brain, Recognition, Cognitive, Health, Sense, Control, Emotion, Affective, Eye Tracking, Gesture, Face, Disability,**.
   - `impact_score` (0-50): 行业影响力。重磅可穿戴产品发布(GPT-5, Vision Pro 2) 或 重大技术突破(Sora) 得 50 分；普通更新 10-20 分。{personal_context}
   - `is_tech_release` (bool): 是否有**即刻可用**的技术发布 (Open Source, Model Weights, Public Beta)。
   - `code_url` (str): 如果 `is_tech_release` 为真，提取具体的开源链接 (GitHub/HuggingFace), 否则为 null.
   - `score_reason` (str): 一句话解释打分理由 (e.g., "重磅模型 GPT-5 发布").
   - 'negtive score'(-100-0): 不关心监管政策、法律还有CPU和显卡的基础设施硬件消息, 出现给负分。
   - `tags` (List[str]): 3-5个技术标签 (e.g. "LLM", "Hardware", "Mobile", "App", "Policy", "Vision").
3. 过滤非新闻内容。只返回 JSON 数组。

网页内容：
{text_content[:60000]}

返回 JSON 格式：
[
    {{
        "title": "News Title",
        "link": "https://...",
        "summary": "中文新闻摘要...",
        "date": "2025-12-10",
        "venue": "The Verge",
        "ai_score": 85,
        "impact_score": 50,
        "personal_score": 90,
        "is_tech_release": true,
        "score_reason": "Major model release.",
        "tags": ["LLM", "Product-Launch"]
    }}
]
"""
        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": "你是一个新闻提取专家。只返回纯净的 JSON 数组。summary 必须是中文。"},
                    {"role": "user", "content": prompt}
                ],
                stream=False,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = re.sub(r"^```(json)?|```$", "", result_text, flags=re.MULTILINE).strip()
            
            logger.debug("ai_result_sample url=%s sample=%s", url, result_text[:500])
                
            data = json.loads(result_text)
            return data if isinstance(data, list) else []
            
        except Exception as e:
            logger.warning(
                "ai_extraction_inner_failed url=%s error=%s output_sample=%s",
                url,
                e,
                result_text[:500] if 'result_text' in locals() else 'N/A',
            )
            return None

    # --- MAIN EXTRACTION LOGIC ---
    
    final_articles = []
    
    # Check for Arxiv Batching Strategy
    if mode == "paper" and "arxiv.org" in url and "<h1>Arxiv" in html:
        # Split raw HTML by article tag
        raw_articles = re.findall(r"<article>.*?</article>", html, re.DOTALL)
        logger.info("ai_batch_start url=%s raw_articles=%s", url, len(raw_articles))
        
        # Batch size of 8 is safe for DeepSeek output limits (4k tokens)
        batch_size = 8
        
        for i in range(0, len(raw_articles), batch_size):
            batch = raw_articles[i : i+batch_size]
            logger.info("ai_batch_process url=%s batch=%s size=%s", url, i // batch_size + 1, len(batch))
            
            # Clean just this batch
            batch_text = "<html><body>" + "\n".join(batch) + "</body></html>"
            cleaned_batch = clean_html_for_ai(batch_text, url)
            
            if cleaned_batch:
                batch_results = _query_ai(cleaned_batch)
                if batch_results is None:
                    return None # Propagate API error
                final_articles.extend(batch_results)
                
    else:
        # Standard Single-Pass Logic
        cleaned_text = clean_html_for_ai(html, url)
        if cleaned_text:
            logger.info("ai_extract_start url=%s mode=%s content_len=%s", url, mode, len(cleaned_text))
            batch_results = _query_ai(cleaned_text)
            if batch_results is None:
                return None # Propagate API error
            final_articles = batch_results

    # --- POST PROCESSING & VALIDATION ---
    valid_articles = []
    
    for art in final_articles:
        # 确保有标题和链接
        if art.get('title') and art.get('link'):
            
            # STRICT CHECK: Only for Arxiv papers
            # If Arxiv paper claims release but has no code_url, reset is_tech_release
            if mode == "paper" and "arxiv.org" in url:
                code_url = art.get('code_url')
                if art.get('is_tech_release') and (not code_url or str(code_url).lower() in ["none", "null", ""]):
                    art['is_tech_release'] = False
                    art['code_url'] = None
                    if "score_reason" in art:
                        art['score_reason'] += " (Arxiv: Code link missing, boost removed)"
            
            # 补全来源
            art['source_domain'] = url.split('/')[2]
            
            # RE-CALCULATE IMPACT SCORE using Python Logic (Authoritative)
            # Trust the hardcoded list/IF values over LLM's guess if venue is recognized
            raw_venue = art.get('venue', '')
            python_score = get_venue_score(raw_venue)
            try:
                ai_score_val = int(art.get('impact_score', 0))
            except:
                ai_score_val = 0
            
            if python_score > ai_score_val:
                logger.info(
                    "impact_score_boosted title=%s old=%s new=%s venue=%s",
                    art["title"],
                    ai_score_val,
                    python_score,
                    raw_venue,
                )
                art['impact_score'] = python_score
                if "score_reason" in art:
                    art['score_reason'] += f" [Impact Boosted by Verified Venue/IF: {raw_venue}]"

            valid_articles.append(art)
            
    return valid_articles


async def extract_news_with_ai(
    html: str,
    url: str,
    mode: str = "news",
    user_interests: List[str] = None,
    raise_on_error: bool = False,
) -> List[Dict[str, Any]]:
    last_error = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            result = await _extract_news_with_ai_once(html, url, mode=mode, user_interests=user_interests)
            if result is not None:
                return result
            last_error = ScraperError(
                "AI extraction returned no result",
                stage="ai_extract",
                error_type="ai_empty_result",
                retryable=True,
                attempts=attempt,
                url=url,
            )
        except ScraperError as e:
            last_error = e
        except Exception as e:
            error_type, retryable = _classify_exception(e)
            last_error = ScraperError(
                str(e),
                stage="ai_extract",
                error_type=error_type,
                retryable=retryable,
                attempts=attempt,
                url=url,
            )

        if last_error and (not last_error.retryable or attempt >= AI_MAX_RETRIES):
            break

        logger.warning("ai_retry url=%s attempt=%s error_type=%s", url, attempt, last_error.error_type if last_error else "unknown")
        await asyncio.sleep(_backoff_delay(attempt))

    if raise_on_error:
        raise last_error or ScraperError(
            "AI extraction failed",
            stage="ai_extract",
            error_type="unknown_error",
            retryable=True,
            attempts=AI_MAX_RETRIES,
            url=url,
        )

    if last_error:
        logger.error(
            "ai_failed url=%s error_type=%s retryable=%s attempts=%s error=%s",
            url,
            last_error.error_type,
            last_error.retryable,
            last_error.attempts,
            last_error,
        )
    return None
