import asyncio
import sys
import json
import os
import hashlib

# Add the current directory to sys.path to allow imports
# 当我们运行 python news_project/main.py 时，我们需要让 Python 知道当前目录是包的一部分
# 或者简单地把当前文件所在目录加入 path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.config import TARGET_URLS, DATA_DIR
from scraper.core import fetch_webpage, extract_news_with_ai
from scraper.storage import Storage
from scraper.utils import clean_html_for_ai 
from scraper.rankings import get_venue_score 
from scraper.personalization import extract_user_interests

async def monitor_news():
    """核心监控逻辑 (Async)"""
    print("=" * 60)
    print("🌍 AI Multi-Site News Monitor (Optimized)")
    print("=" * 60)
    
    # 0. Load User Interests
    user_interests = extract_user_interests(os.path.join(DATA_DIR, "favorites.json"))
    if user_interests:
        print(f"👤 Personalization Active. Interests: {user_interests[:5]}...")
    
    # 初始化存储
    storage = Storage()
    all_new_articles = []
    
    for url in TARGET_URLS:
        html = await fetch_webpage(url)
        if html:
            # 1. 计算内容指纹 (MD5)
            # 为了确保准确性，我们使用 clean_html_for_ai 处理后的文本进行 Hash
            # 这样可以忽略非内容的变动（如广告ID变化、时间戳等）
            cleaned_text = clean_html_for_ai(html, url)
            if not cleaned_text:
                print(f"⚠ Empty content from {url}")
                continue
                
            content_hash = hashlib.md5(cleaned_text.encode('utf-8')).hexdigest()
            stored_hash = storage.get_page_hash(url)
            
            # 2. 对比 Hash
            if content_hash == stored_hash:
                print(f"⏩ [Skipped] Content unchanged for {url}")
                print(f"   (Hash: {content_hash[:8]}...)")
                continue
            
            print(f"📝 Content changed or new. Processing {url}...")
            
            # 4. 判断类型 (News vs Paper) 并调用 AI
            mode = "news"
            # Simple heuristic for Paper/Research
            if any(ky in url for ky in ["arxiv.org", ".edu", "publication", "research", "deepmind"]):
                mode = "paper"
            if "openai.com/index" in url: # OpenAI blog often technical but mix.
                mode = "news" # Keep OpenAI as news/product unless strictly research
            
            # extract_news_with_ai 内部会重新 cleaning，我们传 mode 进去
            articles = await extract_news_with_ai(html, url, mode=mode, user_interests=user_interests)
            
            if articles is None:
                print(f"⚠ API Unavailable/Error for {url}. Skipping hash update so we can retry later.")
                continue
            
            # 更新 Hash (只有在 API 成功返回结果后，才更新 hash，避免浪费额度后页面被永久跳过)
            storage.save_page_hash(url, content_hash)
            
            if articles:
                # 过滤新文章
                new_articles = storage.filter_new_articles(articles)
                
                if new_articles:
                    print(f"✨ Found {len(new_articles)} NEW articles from {url} [{mode.upper()}]")
                    # 标记类型
                    for art in new_articles:
                        art['type'] = mode 
                    
                    all_new_articles.extend(new_articles)
                    
                    # 更新状态
                    for art in new_articles:
                        storage.add_seen(art['link'])
                else:
                    print(f"💤 No new articles from {url} (found {len(articles)} old ones)")
            else:
                print(f"⚠ No articles found from {url}")
        print("-" * 40)
        
    # --- 排序逻辑 (Sorting) ---
    def calculate_final_score(article):
        try:
            # 1. Semantic Score (0-100) - AI's relevance judgment
            semantic = int(article.get('ai_score', 0))
            
            # 2. Impact Score (0-10) - Academic/Industry status
            # Weight x 2 (Max +20 for CCF A / Major Release)
            impact = int(article.get('impact_score', 0))
            
            # 3. Personal Boost (0-100)
            personal = int(article.get('personal_score', 0))
            
            # 4. Tech Release Boost (+200)
            is_paper = article.get('type') == 'paper'
            has_code = bool(article.get('code_url'))
            is_release = article.get('is_tech_release')
            
            if is_paper:
                tech_boost = 200 if has_code else 0
            else:
                tech_boost = 200 if (is_release or has_code) else 0
            
            return semantic + impact + personal + tech_boost
        except:
            return 0

    # Sort all new articles
    for art in all_new_articles:
        art['score'] = calculate_final_score(art)
        # AI returns 'score_reason', use it.
        if 'score_reason' not in art:
             art['score_reason'] = "AI scoring unavailable"
        
    all_new_articles.sort(key=lambda x: x['score'], reverse=True)

    # Split into two lists for display
    news_list = [a for a in all_new_articles if a.get('type') == 'news']
    paper_list = [a for a in all_new_articles if a.get('type') == 'paper']

    # 处理结果
    result_message = "No new articles found."
    
    if all_new_articles:
        result_message = f"Found {len(all_new_articles)} new articles."
        print(f"\n🎉 {result_message}")
        
        if not os.getenv("NEWS_BUCKET_NAME"): # 本地模式才写文件
            
            def save_to_json_files(articles: list, latest_file: str, history_file: str):
                if not articles:
                    return
                
                latest_path = os.path.join(DATA_DIR, latest_file)
                
                # 1. Load existing Latest (to append, not overwrite)
                existing_latest = []
                if os.path.exists(latest_path):
                    try:
                        with open(latest_path, "r", encoding="utf-8") as f:
                            existing_latest = json.load(f)
                    except:
                        pass
                
                # Merge new articles (avoid duplicates just in case)
                existing_links_latest = {item['link'] for item in existing_latest}
                for art in reversed(articles): # Add new ones at top? No, reversed usually means old->new. 
                     # We want New ones at TOP. "articles" is usually ordered Top=Newest?
                     # Let's assume 'articles' list is Newest First.
                     if art['link'] not in existing_links_latest:
                         existing_latest.insert(0, art)
                
                # Save to Latest
                with open(latest_path, "w", encoding="utf-8") as f:
                    json.dump(existing_latest, f, ensure_ascii=False, indent=2)
                print(f"💾 Updated {latest_file} (Total: {len(existing_latest)} items)")
                
                # NOTE: We DO NOT auto-archive to history anymore.
                # The Dashboard will handle that when user clicks "Archive".
                pass

            # Save News (Non-Arxiv)
            # User request: "Only separate Arxiv... others follow original logic"
            # So we split specifically by Domain (arxiv.org) vs Others
            
            arxiv_articles = [a for a in all_new_articles if "arxiv.org" in a.get('link', '')]
            other_articles = [a for a in all_new_articles if "arxiv.org" not in a.get('link', '')]

            # Save Others (News + Non-Arxiv Papers) to standard 'news' file
            save_to_json_files(other_articles, "latest_news.json", "history_news.json")
            
            # Save Arxiv to dedicated 'arxiv' file
            save_to_json_files(arxiv_articles, "latest_arxiv.json", "history_arxiv.json")
            
        # 打印预览 (分栏)
        print("\n" + "="*40)
        print("📰 INDUSTRY NEWS & UPDATES (Recommended)")
        print("="*40)
        for i, news in enumerate(news_list, 1):
            print(f"[N{i}] [Score:{news['score']}] {news['title']}")
            print(f"    ⭐ {news.get('score_reason', 'Base')}")
            print(f"   📅 {news.get('date', 'N/A')} | 🏢 {news.get('venue', news.get('source_domain', ''))}")
            print(f"   🔗 {news['link']}")
            if news.get('code_url'):
                print(f"   💻 Code: {news['code_url']}")
            print(f"   🇨🇳 {news['summary']}")
            print("-" * 20)

        print("\n" + "="*40)
        print("📜 ACADEMIC PAPERS & RESEARCH (Recommended)")
        print("="*40)
        for i, paper in enumerate(paper_list, 1):
            print(f"[P{i}] [Score:{paper['score']}] {paper['title']}")
            print(f"    ⭐ {paper.get('score_reason', 'Base')}")
            print(f"   📅 {paper.get('date', 'N/A')} | 🏛 {paper.get('venue', 'Arxiv')}")
            print(f"   🔗 {paper['link']}")
            if paper.get('code_url'):
                print(f"   💻 Code: {paper['code_url']}")
            print(f"   🇨🇳 {paper['summary']}")
            print("-" * 20)
        print("")
            
    else:
        print(f"\n💤 {result_message}")

    # 无论有无新文章，都要保存状态（包括 hashes）
    storage.save()
    print("✅ History updated (including content hashes).")

    # --- INTERACTIVE BOOKMARK MODE (Local Only) ---
    # Only run if not on Cloud or CI (Cloud doesn't have stdin)
    if not os.getenv("NEWS_BUCKET_NAME") and not os.getenv("GITHUB_ACTIONS"): 
        print("\n" + "="*40)
        print("⭐ BOOKMARK TIME (Interactive)")
        print("="*40)
        
        while True:
            selection = input("👉 Enter article numbers to bookmark (e.g. '1 3 5', or Enter to skip): ").strip()
            if not selection:
                break
                
            try:
                # Process Input:
                # "n1" -> news_list[0]
                # "p2" -> paper_list[1]
                
                parts = selection.split()
                saved_count = 0
                
                for item in parts:
                    prefix = item[0].lower()
                    if prefix not in ['n', 'p']:
                         print(f"⚠ Invalid format '{item}'. Use 'n1' for News #1, 'p2' for Paper #2.")
                         continue
                    
                    try:
                        idx = int(item[1:]) - 1 # 0-indexed
                        target_list = news_list if prefix == 'n' else paper_list
                        
                        if 0 <= idx < len(target_list):
                            storage.save_to_favorites(target_list[idx])
                            saved_count += 1
                        else:
                            print(f"⚠ Index {item} out of range.")
                    except ValueError:
                        print(f"⚠ Invalid number in '{item}'.")
                        
                if saved_count > 0:
                    print(f"✨ Successfully bookmarked {saved_count} articles!")
                    break # Exit after successful save? Or allow more? Let's loop.
                
            except Exception as e:
                print(f"Error processing input: {e}")

    return result_message

# Cloud Function Entry Point
def run_scraper(request):
    """
    HTTP Cloud Function Entry Point
    Accepts a request object (flask.Request) and returns text.
    """
    print("🚀 Cloud Function triggered!")
    
    # 在 Python 3.7+ 的 cloud function 环境中运行 async 代码
    try:
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(monitor_news())
        else:
            result = asyncio.run(monitor_news())
            
        return f"✅ Success: {result}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"

if __name__ == "__main__":
    # 本地直接运行
    print(run_scraper(None))
