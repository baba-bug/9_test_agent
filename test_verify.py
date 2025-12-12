import sys
import os
import asyncio

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Patch URL list to be single and fast
import news_project.scraper.config as config
config.TARGET_URLS = ["https://about.fb.com/news/"]

from news_project.main import monitor_news

if __name__ == "__main__":
    # Force delete storage to ensure it runs
    if os.path.exists("news_state.json"):
        os.remove("news_state.json")
        
    print("🚀 Running Quick Verification on FB News...")
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitor_news())
    else:
        asyncio.run(monitor_news())
