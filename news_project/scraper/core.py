import json
import re
from httpx import AsyncClient
from openai import OpenAI
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

from .utils import clean_html_for_ai
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, SITE_COOKIES
from .rankings import get_ranking, CCF_RANKINGS # Import CCF_RANKINGS

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
            match = re.search(r"list/([^/]+)", url)
            if match:
                category = match.group(1)
                # Query the last 15 papers to save tokens
                api_url = f"http://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&max_results=15"
                
                async with AsyncSession(impersonate="chrome120") as s:
                    response = await s.get(api_url)
                    
                    if response.status_code == 200:
                        root = ET.fromstring(response.content)
                        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                        
                        html_parts = [f"<html><body><h1>Arxiv {category} Recent Papers</h1>"]
                        
                        for entry in root.findall("atom:entry", ns):
                            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                            link = entry.find("atom:id", ns).text.strip()
                            published = entry.find("atom:published", ns).text.strip()
                        
                        # Extract Venue Info
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
                                # Use RAG/Lookup to get rating
                                venue_str = get_ranking(venue_str)
                            
                            html_parts.append(f"<article>")
                            html_parts.append(f"<h2>{title}</h2>")
                            html_parts.append(f"<p>Date: {published}</p>")
                            html_parts.append(f"<p>Venue: {venue_str}</p>")
                            html_parts.append(f"<a href='{link}'>Paper Link</a>")
                            html_parts.append(f"<div>{summary}</div>")
                            html_parts.append(f"</article><hr/>")
                            
                        html_parts.append("</body></html>")
                        return "".join(html_parts)
                    else:
                        print(f"⚠ Arxiv API Failed: {response.status_code}")
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
    
    cleaned_text = clean_html_for_ai(html, url)
    
    if not cleaned_text:
        return []

    print(f"📝 Processing {url} as [{mode.upper()}] (Content len: {len(cleaned_text)})")
    
    # 构造 CCF 上下文简表 (减少 token，只列出 A 类和常见 B 类)
    ccf_context = "CCF/Top Venue Reference (Class A=10, B=5, C=2):\n"
    top_venues = [k for k, v in CCF_RANKINGS.items() if v == "CCF A"][:30] # Top 30 A-class
    ccf_context += ", ".join(top_venues)
    
    # --- PROMPT DESIGN ---
    if mode == "paper":
        prompt = f"""你是一个顶尖科研论文鉴赏专家。请从网页文本中提取论文列表，并进行深度评分。
任务要求：
1. 提取论文信息：
   - 标题 (title): 英文原题
   - 链接 (link): 必须是绝对路径。
   - 摘要 (summary): **中文总结**，侧重研究方法、贡献和创新点。
   - 日期 (date): 发表或上传日期。
   - 发表处 (venue): 期刊/会议名称。
2. **深度评分 (Scoring)**：
   - `ai_score` (0-100): 语义相关性打分。用户兴趣点：**AI, Agent, HCI, XR/Spatial, Generation**. 相关度越高分数越高。
   - `impact_score` (0-10): 学术影响力。发表在 CCF A (如 CVPR, CHI, NeurIPS) 或 Top Journal (Nature/Science) 得 10 分；CCF B 得 5 分；一般会议 2 分；Arxiv 预印本 1 分。
   - `is_tech_release` (bool): 论文是否伴随代码发布(GitHub)、模型权重发布(HuggingFace)或 Demo 发布。
   - `score_reason` (str): 一句话解释打分理由 (e.g., "Agent领域CCF A类论文，且开源代码").
3. 过滤非论文内容。只返回 JSON 数组。

参考：
{ccf_context}

网页内容：
{cleaned_text[:50000]}

返回 JSON 格式：
[
    {{
        "title": "Paper Title",
        "link": "https://...",
        "summary": "中文技术总结...",
        "date": "2025-12-10",
        "venue": "CVPR 2025",
        "ai_score": 95,
        "impact_score": 10,
        "is_tech_release": true,
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
   - 日期 (date): 具体日期。
   - 来源 (venue): 新闻来源名称。
2. **深度评分 (Scoring)**：
   - `ai_score` (0-100): 语义相关性打分。用户兴趣点：**AI, Agent, HCI, XR/Spatial, Generation**.
   - `impact_score` (0-10): 行业影响力。重磅产品发布(GPT-5, Vision Pro 2) 或 重大技术突破(Sora) 得 10 分；普通更新 3-5 分。
   - `is_tech_release` (bool): 是否有**即刻可用**的技术发布 (Open Source, Model Weights, Public Beta)。
   - `score_reason` (str): 一句话解释打分理由 (e.g., "重磅模型 GPT-5 发布").
3. 过滤非新闻内容。只返回 JSON 数组。

网页内容：
{cleaned_text[:50000]}

返回 JSON 格式：
[
    {{
        "title": "News Title",
        "link": "https://...",
        "summary": "中文新闻摘要...",
        "date": "2025-12-10",
        "venue": "The Verge",
        "ai_score": 85,
        "impact_score": 10,
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
        
        # 清理 Markdown 标记
        if result_text.startswith("```"):
            result_text = re.sub(r"^```(json)?|```$", "", result_text, flags=re.MULTILINE).strip()
            
        articles = json.loads(result_text)
        
        # 后处理和验证
        valid_articles = []
        if isinstance(articles, list):
            for art in articles:
                # 确保有标题和链接
                if art.get('title') and art.get('link'):
                    # 补全来源
                    art['source_domain'] = url.split('/')[2]
                    valid_articles.append(art)
                    
        return valid_articles

    except Exception as e:
        print(f"❌ AI Extraction failed for {url}: {e}")
        return []
