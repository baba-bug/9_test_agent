import json
import re
from httpx import AsyncClient
from openai import OpenAI
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

from .utils import clean_html_for_ai
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, SITE_COOKIES
from .rankings import get_ranking, CCF_RANKINGS, get_venue_score # Updated Import

from curl_cffi.requests import AsyncSession

# ... (fetch_webpage remains unchanged) ...



async def fetch_webpage(url: str) -> str:
    """
    Fetch webpage using curl_cffi to bypass bot detection (TLS fingerprinting).
    Handles TikTok's Remix JSON endpoint automatically.
    """
    # Special handling for TikTok: Use API endpoint to get JSON data
    if "newsroom.tiktok.com" in url and "_data" not in url:
        print(f"🔄 Switching to TikTok Data Endpoint for {url}")
        url = f"{url.split('?')[0]}?_data=routes%2F_app._index&lang=en"

    # Special handling for Arxiv (Use API for summaries)
    if "arxiv.org/list/" in url:
        try:
            print(f"🔄 Switching to Arxiv API for {url}...")
            # Extract category from URL: https://arxiv.org/list/cs.HC/recent -> cs.HC
            # or https://arxiv.org/list/cs.MA/recent
            import re
            # Extract category from URL: https://arxiv.org/list/cs.HC/recent -> cs.HC
            import re
            from datetime import datetime, timedelta, timezone
            
            match = re.search(r"list/([^/]+)", url)
            if match:
                category = match.group(1)
                
                # Pagination Logic: Fetch all papers from past 24 hours (or slightly more buffer)
                # Setting a safety cap of 100 papers or 5 pages to prevent infinite loops
                html_parts = [f"<html><body><h1>Arxiv {category} Recent Papers</h1>"]
                
                offset = 0
                max_results = 20 # Batch size per request
                fetched_count = 0
                cutoff_date = datetime.now(timezone.utc) - timedelta(hours=72) # 24h -> 3 days to cover weekends
                stop_fetching = False
                
                print(f"🔄 Arxiv Pagination: Fetching {category} papers since {cutoff_date.date()}...")

                async with AsyncSession(impersonate="chrome120") as s:
                    while not stop_fetching and fetched_count < 100:
                        api_url = f"http://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&start={offset}&max_results={max_results}"
                        
                        try:
                            response = await s.get(api_url)
                            if response.status_code != 200:
                                print(f"⚠ Arxiv API Error {response.status_code} at offset {offset}")
                                break
                                
                            root = ET.fromstring(response.content)
                            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                            
                            entries = root.findall("atom:entry", ns)
                            if not entries:
                                break # No more results
                                
                            batch_valid_count = 0
                            for entry in entries:
                                # Date Check
                                published_str = entry.find("atom:published", ns).text.strip()
                                # Format: 2025-12-11T14:30:00Z
                                try:
                                    pub_date = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                                except:
                                    # Fallback if format fails
                                    pub_date = datetime.now(timezone.utc)

                                if pub_date < cutoff_date:
                                    stop_fetching = True
                                    # Don't break immediately if mixed sort, but Arxiv is sorted by Date.
                                    # However, "submittedDate" isn't strictly "published" date? 
                                    # Arxiv API: sortBy=submittedDate is reliable for new papers.
                                    break 
                                
                                batch_valid_count += 1
                                fetched_count += 1
                                
                                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                                summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                                link = entry.find("atom:id", ns).text.strip()
                                
                                # Extract Venue Info
                                journal_ref = entry.find("arxiv:journal_ref", ns)
                                comment = entry.find("arxiv:comment", ns)
                                
                                venue_info = []
                                if journal_ref is not None:
                                    venue_info.append(f"Journal: {journal_ref.text}")
                                if comment is not None:
                                    venue_info.append(f"Comment: {comment.text}")
                                
                                venue_str = " | ".join(venue_info)
                                if venue_str:
                                    venue_str = get_ranking(venue_str)
                                
                                html_parts.append(f"<article>")
                                html_parts.append(f"<h2>{title}</h2>")
                                html_parts.append(f"<p>Date: {published_str}</p>")
                                html_parts.append(f"<p>Venue: {venue_str}</p>")
                                # Crucial: Expose Link as text because clean_html_for_ai strips tags/attributes
                                html_parts.append(f"<p>Link: {link}</p>") 
                                html_parts.append(f"<div>{summary}</div>")
                                html_parts.append(f"</article><hr/>")
                            
                            print(f"   🔹 Batch {offset}: Found {batch_valid_count} recent papers (Total: {fetched_count})")
                            
                            if batch_valid_count < len(entries):
                                # If we filtered out some papers in this batch due to date, stop.
                                stop_fetching = True
                            
                            offset += max_results
                            
                        except Exception as e:
                            print(f"⚠ Arxiv Loop Error: {e}")
                            break
                            
                html_parts.append("</body></html>")
                return "".join(html_parts)
                
        except Exception as e:
            print(f"⚠ Arxiv Logic Error: {e}")

    # Mimic Chrome 120
    async with AsyncSession(impersonate="chrome120") as s:
        print(f"📡 Fetching {url} (curl_cffi)...")
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        
        # 自动匹配 Cookie
        for domain, cookie in SITE_COOKIES.items():
            if domain in url and cookie:
                print(f"🔑 Injecting Cookie for {domain}")
                headers["Cookie"] = cookie
                break
            
        try:
            response = await s.get(
                url, 
                timeout=30,
                headers=headers
            )
            response.raise_for_status()
            
            # If it's a Remix JSON response (TikTok), extract the HTML content
            if "application/json" in response.headers.get("content-type", ""):
                try:
                    data = response.json()
                    # Try to find mainArticle content in TikTok structure
                    if "mainArticle" in data:
                        print("🧩 Parsed TikTok JSON structure.")
                        html_content = data["mainArticle"].get("content", "")
                        title = data["mainArticle"].get("title", "")
                        date = data["mainArticle"].get("publishedDate", "")
                        # Prepend title/date to help AI
                        return f"<h1>{title}</h1><p>Date: {date}</p><div>{html_content}</div>"
                except Exception as e:
                    print(f"⚠ Failed to parse TikTok JSON: {e}")
                    return response.text # Fallback
            
            return response.text
            
        except Exception as e:
            print(f"❌ Fetch Error: {e}")
            return ""

async def extract_news_with_ai(html: str, url: str, mode: str = "news") -> List[Dict[str, Any]]:
    """
    使用 AI 智能提取信息
    mode: "news" (默认新闻) 或 "paper" (科研论文)
    """
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    
    # 获取今天日期
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")

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
   - `impact_score` (0-50): 学术影响力。发表在 CCF A (如 CVPR, CHI, NeurIPS) 或 Top Journal (Nature/Science) 得 50 分；CCF B 得 25 分；一般会议 10 分；Arxiv 预印本 5 分。
   - `is_tech_release` (bool): 论文是否伴随代码发布(GitHub)、模型权重发布(HuggingFace)或 Demo 发布。
   - `code_url` (str): 如果 `is_tech_release` 为真，提取具体的开源链接 (GitHub/HuggingFace), 否则为 null.
   - `score_reason` (str): 一句话解释打分理由 (e.g., "Agent领域CCF A类论文，且开源代码").
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
        "is_tech_release": true,
        "code_url": "https://github.com/...",
        "score_reason": "High interest Agent paper in CVPR with Code."
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
   - `impact_score` (0-50): 行业影响力。重磅可穿戴产品发布(GPT-5, Vision Pro 2) 或 重大技术突破(Sora) 得 50 分；普通更新 10-20 分。
   - `is_tech_release` (bool): 是否有**即刻可用**的技术发布 (Open Source, Model Weights, Public Beta)。
   - `code_url` (str): 如果 `is_tech_release` 为真，提取具体的开源链接 (GitHub/HuggingFace), 否则为 null.
   - `score_reason` (str): 一句话解释打分理由 (e.g., "重磅模型 GPT-5 发布").
   - 'negtive score'(-100-0): 不关心监管政策、法律还有CPU和显卡的基础设施硬件消息, 出现给负分。
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
        "is_tech_release": true,
        "score_reason": "Major model release."
    }}
]
"""
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
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
            
            # DEBUG
            print(f"🔍 DEBUG AI RESULT: {result_text[:500]}")
                
            data = json.loads(result_text)
            return data if isinstance(data, list) else []
            
        except Exception as e:
            print(f"❌ AI Extraction Inner Error: {e}")
            print(f"🔍 DEBUG ERROR OUTPUT: {result_text if 'result_text' in locals() else 'N/A'}")
            return []

    # --- MAIN EXTRACTION LOGIC ---
    
    final_articles = []
    
    # Check for Arxiv Batching Strategy
    if mode == "paper" and "arxiv.org" in url and "<h1>Arxiv" in html:
        print("📦 Batching Arxiv papers for AI extraction...")
        # Split raw HTML by article tag
        raw_articles = re.findall(r"<article>.*?</article>", html, re.DOTALL)
        
        # Batch size of 8 is safe for DeepSeek output limits (4k tokens)
        batch_size = 8
        
        for i in range(0, len(raw_articles), batch_size):
            batch = raw_articles[i : i+batch_size]
            print(f"   🤖 AI Processing Batch {i//batch_size + 1} ({len(batch)} items)...")
            
            # Clean just this batch
            batch_text = "<html><body>" + "\n".join(batch) + "</body></html>"
            cleaned_batch = clean_html_for_ai(batch_text, url)
            
            if cleaned_batch:
                # print(f"   📄 Cleaned Batch Len: {len(cleaned_batch)}")
                batch_results = _query_ai(cleaned_batch)
                final_articles.extend(batch_results)
                
    else:
        # Standard Single-Pass Logic
        cleaned_text = clean_html_for_ai(html, url)
        if cleaned_text:
            print(f"📝 Processing {url} as [{mode.upper()}] (Content len: {len(cleaned_text)})")
            final_articles = _query_ai(cleaned_text)

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
                    # print(f"⚠️ Strict Check (Arxiv): '{art['title']}' claimed release but no URL. Resetting to False.")
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
                print(f"📈 Boosting Impact Score for '{art['title']}': {ai_score_val} -> {python_score} (Venue: {raw_venue})")
                art['impact_score'] = python_score
                if "score_reason" in art:
                    art['score_reason'] += f" [Impact Boosted by Verified Venue/IF: {raw_venue}]"

            valid_articles.append(art)
            
    return valid_articles
