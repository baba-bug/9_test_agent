import asyncio
import sys
import json
import os
import hashlib

# Add the current directory to sys.path to allow imports
# 当我们运行 python news_project/main.py 时，我们需要让 Python 知道当前目录是包的一部分
# 或者简单地把当前文件所在目录加入 path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.config import TARGET_URLS
from scraper.core import fetch_webpage, extract_news_with_ai
from scraper.storage import Storage
from scraper.utils import clean_html_for_ai 
from scraper.rankings import get_venue_score # Added import

async def monitor_news():
    """核心监控逻辑 (Async)"""
    print("=" * 60)
    print("🌍 AI Multi-Site News Monitor (Optimized)")
    print("=" * 60)
    
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
            articles = await extract_news_with_ai(html, url, mode=mode)
            
            # 更新 Hash (无论是否提取到文章，只要内容变了就更新，避免重复尝试)
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
            # User wanted Nature=20, CCF A=10. 
            # If AI returns 10 for CCF A, then x1 is 10. x2 is 20.
            # Let's use x2 to make Impact very visible.
            impact = int(article.get('impact_score', 0)) * 2
            
            # 3. Tech Release Boost (+20)
            tech_boost = 20 if article.get('is_tech_release') else 0
            
            return semantic + impact + tech_boost
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
            output_file = "latest_new_articles.json"
            history_file = "history_news.json"
            
            # 1. 保存本次新文章 (Sorted with Score)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_new_articles, f, ensure_ascii=False, indent=2)
            print(f"💾 Saved latest articles to {output_file}")
            
            # 2. 追加到历史档案 (History Persistence)
            history_data = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                except Exception as e:
                    print(f"⚠ Failed to load history file: {e}")
            
            # 合并新数据
            existing_links = {item['link'] for item in history_data}
            added_count = 0
            # 稍微逆序插入，保持最新的在最前 (但我们要保持高分在前？)
            # 策略：历史记录按时间倒序。本次更新按分数排序。
            # 简单追加：
            for art in reversed(all_new_articles): 
                if art['link'] not in existing_links:
                    history_data.insert(0, art)
                    added_count += 1
            
            if added_count > 0:
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, ensure_ascii=False, indent=2)
                print(f"📚 Appended {added_count} articles to {history_file}")
            
        # 打印预览 (分栏)
        print("\n" + "="*40)
        print("📰 INDUSTRY NEWS & UPDATES (Recommended)")
        print("="*40)
        for i, news in enumerate(news_list, 1):
            print(f"{i}. [Score:{news['score']}] {news['title']}")
            print(f"    ⭐ {news.get('score_reason', 'Base')}")
            print(f"   📅 {news.get('date', 'N/A')} | 🏢 {news.get('venue', news.get('source_domain', ''))}")
            print(f"   🔗 {news['link']}")
            print(f"   🇨🇳 {news['summary']}")
            print("-" * 20)

        print("\n" + "="*40)
        print("📜 ACADEMIC PAPERS & RESEARCH (Recommended)")
        print("="*40)
        for i, paper in enumerate(paper_list, 1):
            print(f"{i}. [Score:{paper['score']}] {paper['title']}")
            print(f"    ⭐ {paper.get('score_reason', 'Base')}")
            print(f"   📅 {paper.get('date', 'N/A')} | 🏛 {paper.get('venue', 'Arxiv')}")
            print(f"   🔗 {paper['link']}")
            print(f"   🇨🇳 {paper['summary']}")
            print("-" * 20)
        print("")
            
    else:
        print(f"\n💤 {result_message}")

    # 无论有无新文章，都要保存状态（包括 hashes）
    storage.save()
    print("✅ History updated (including content hashes).")

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
