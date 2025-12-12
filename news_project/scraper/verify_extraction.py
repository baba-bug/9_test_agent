import sys
import os
import asyncio
import json

# Ensure path is correct
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from news_project.scraper.core import fetch_webpage, extract_news_with_ai
from news_project.scraper.utils import clean_html_for_ai

def calculate_final_score(article):
    try:
        semantic = int(article.get('ai_score', 0))
        impact = int(article.get('impact_score', 0)) * 2
        is_paper = article.get('type') == 'paper'
        has_code = bool(article.get('code_url'))
        is_release = article.get('is_tech_release')
        
        if is_paper:
            tech_boost = 200 if has_code else 0
        else:
            tech_boost = 200 if (is_release or has_code) else 0

        return semantic + impact + tech_boost
    except:
        return 0

async def debug_one_url():
    url = "https://about.fb.com/news/"
    print(f"🔬 Debugging AI Scoring for: {url}")
    
    # 1. Fetch
    html = await fetch_webpage(url)
    if not html:
        print("❌ Failed to fetch HTML")
        return

    # 2. Extract with AI (this triggers the new Prompt)
    articles = await extract_news_with_ai(html, url, mode="news")
    
    if not articles:
        print("❌ No articles extracted.")
        return
        
    print(f"✨ Extracted {len(articles)} articles.")
    
    # 3. Calculate Score using Main logic
    print("\n📊 Scoring Results:")
    mock_paper_with_code = {
        'title': "Fake Paper with Code",
        'type': 'paper',
        'is_tech_release': True,
        'code_url': "https://github.com/fake",
        'ai_score': 50,
        'impact_score': 5
    }
    score2 = calculate_final_score(mock_paper_with_code)
    print(f"Paper (Release=True, Code=Yes) Score: {score2} (Expected ~260, boost)")

    mock_paper_no_code = {
        'title': "Fake Paper No Code",
        'type': 'paper',
        'is_tech_release': False,
        'code_url': None,
        'ai_score': 50,
        'impact_score': 5
    }
    score = calculate_final_score(mock_paper_no_code)
    print(f"Paper (Release=False, Code=No) Score: {score} (Expected ~60, no boost)")
    
    with open("mock_results.txt", "w") as f:
        f.write(f"Paper No Code Score: {score}\n")
        f.write(f"Paper With Code Score: {score2}\n")
    print("💾 Saved mock scores to mock_results.txt")

    for art in articles:
        art['type'] = 'news' # Simulate logic
        # Simulate main.py logic
        final_score = calculate_final_score(art)
        art['final_score'] = final_score
        
        print(f"\nTitle: {art.get('title')}")
        print(f"Date: {art.get('date')} (Expected YYYY-MM-DD)")
        print(f"AI Score: {art.get('ai_score')} | Tech Release: {art.get('is_tech_release')}")
        
        if art.get('code_url'):
            print(f"💻 Code URL: {art.get('code_url')}")
        else:
            print(f"💻 Code URL: None")
            
        print(f"Reason: {art.get('score_reason')}")
        print("-" * 30)
    
    with open("debug_verify.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print("💾 Saved to debug_verify.json")

if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(debug_one_url())
    else:
        asyncio.run(debug_one_url())
