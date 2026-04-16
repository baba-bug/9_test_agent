import asyncio
import hashlib
import os
import sys
from typing import Any, Dict, List

# Allow `python news_project/main.py` to import the scraper package.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.observability import get_logger, setup_logging


setup_logging()

from scraper.config import DATA_DIR, TARGET_URLS
from scraper.core import ScraperError, extract_news_with_ai, fetch_webpage
from scraper.personalization import extract_user_interests
from scraper.storage import Storage
from scraper.utils import clean_html_for_ai


logger = get_logger(__name__)


def infer_mode(url: str) -> str:
    mode = "news"
    if any(key in url for key in ["arxiv.org", ".edu", "publication", "research", "deepmind"]):
        mode = "paper"
    if "openai.com/index" in url:
        mode = "news"
    return mode


def calculate_final_score(article: Dict[str, Any]) -> int:
    try:
        semantic = int(article.get("ai_score", 0))
        impact = int(article.get("impact_score", 0))
        personal = int(article.get("personal_score", 0))
        is_paper = article.get("type") == "paper"
        has_code = bool(article.get("code_url"))
        is_release = article.get("is_tech_release")

        if is_paper:
            tech_boost = 200 if has_code else 0
        else:
            tech_boost = 200 if (is_release or has_code) else 0

        return semantic + impact + personal + tech_boost
    except Exception:
        return 0


def log_preview(news_list: List[Dict[str, Any]], paper_list: List[Dict[str, Any]]) -> None:
    logger.info("preview_news count=%s", len(news_list))
    for i, article in enumerate(news_list, 1):
        logger.info(
            "preview_item category=news rank=%s score=%s title=%s date=%s source=%s link=%s",
            i,
            article.get("score"),
            article.get("title"),
            article.get("date", "N/A"),
            article.get("venue", article.get("source_domain", "")),
            article.get("link"),
        )

    logger.info("preview_papers count=%s", len(paper_list))
    for i, article in enumerate(paper_list, 1):
        logger.info(
            "preview_item category=paper rank=%s score=%s title=%s date=%s source=%s link=%s",
            i,
            article.get("score"),
            article.get("title"),
            article.get("date", "N/A"),
            article.get("venue", "Arxiv"),
            article.get("link"),
        )


def prompt_for_bookmarks(storage: Storage, news_list: List[Dict[str, Any]], paper_list: List[Dict[str, Any]]) -> None:
    if os.getenv("NEWS_BUCKET_NAME") or os.getenv("GITHUB_ACTIONS") or not sys.stdin.isatty():
        return
    if not news_list and not paper_list:
        return

    print("\nBookmark mode")
    print("Enter article numbers to bookmark, for example: n1 p2. Press Enter to skip.")

    while True:
        selection = input("> ").strip()
        if not selection:
            return

        saved_count = 0
        for item in selection.split():
            prefix = item[0].lower()
            if prefix not in {"n", "p"}:
                print(f"Invalid item '{item}'. Use n1 for news or p1 for papers.")
                continue

            try:
                idx = int(item[1:]) - 1
            except ValueError:
                print(f"Invalid number in '{item}'.")
                continue

            target_list = news_list if prefix == "n" else paper_list
            if 0 <= idx < len(target_list):
                storage.save_to_favorites(target_list[idx])
                saved_count += 1
            else:
                print(f"Index out of range: {item}")

        if saved_count:
            print(f"Saved {saved_count} item(s).")
            return


async def process_source(url: str, storage: Storage, user_interests: List[str]) -> List[Dict[str, Any]]:
    logger.info("source_start url=%s", url)

    try:
        html = await fetch_webpage(url, raise_on_error=True)
    except ScraperError as e:
        storage.record_source_failure(url, e.stage, e.error_type, str(e), e.retryable, e.attempts)
        return []

    if not html:
        storage.record_source_failure(url, "fetch", "empty_response", "fetch returned empty content", True, 1)
        return []

    cleaned_text = clean_html_for_ai(html, url)
    if not cleaned_text:
        storage.record_source_failure(url, "clean", "empty_content", "cleaned content was empty", False, 1)
        return []

    content_hash = hashlib.md5(cleaned_text.encode("utf-8")).hexdigest()
    stored_hash = storage.get_page_hash(url)
    if content_hash == stored_hash:
        storage.record_content_unchanged(url, content_hash)
        logger.info("source_unchanged url=%s hash=%s", url, content_hash[:8])
        return []

    storage.record_content_changed(url, content_hash)
    mode = infer_mode(url)
    logger.info("source_changed url=%s mode=%s hash=%s", url, mode, content_hash[:8])

    try:
        articles = await extract_news_with_ai(html, url, mode=mode, user_interests=user_interests, raise_on_error=True)
    except ScraperError as e:
        storage.record_source_failure(url, e.stage, e.error_type, str(e), e.retryable, e.attempts)
        return []

    storage.save_page_hash(url, content_hash)
    articles = articles or []
    new_articles = storage.filter_new_articles(articles)

    for article in new_articles:
        article["type"] = mode
        storage.add_seen(article["link"])

    storage.record_extraction_result(url, len(articles), len(new_articles))
    storage.record_source_success(url, stage="extract")
    logger.info("source_done url=%s extracted=%s new=%s", url, len(articles), len(new_articles))
    return new_articles


async def monitor_news() -> str:
    logger.info("monitor_start target_count=%s", len(TARGET_URLS))

    user_interests = extract_user_interests(os.path.join(DATA_DIR, "favorites.json"))
    if user_interests:
        logger.info("personalization_active top_interests=%s", user_interests[:5])

    storage = Storage()
    all_new_articles: List[Dict[str, Any]] = []

    try:
        for url in TARGET_URLS:
            all_new_articles.extend(await process_source(url, storage, user_interests))

        for article in all_new_articles:
            article["score"] = calculate_final_score(article)
            article.setdefault("score_reason", "AI scoring unavailable")

        all_new_articles.sort(key=lambda item: item.get("score", 0), reverse=True)

        news_list = [a for a in all_new_articles if a.get("type") == "news"]
        paper_list = [a for a in all_new_articles if a.get("type") == "paper"]

        if all_new_articles:
            storage.save_latest_articles(all_new_articles)

        log_preview(news_list, paper_list)
        prompt_for_bookmarks(storage, news_list, paper_list)
        result_message = f"Found {len(all_new_articles)} new articles." if all_new_articles else "No new articles found."
        logger.info("monitor_done result=%s", result_message)
        return result_message
    finally:
        storage.save()
        logger.info("state_saved")


def run_scraper(request):
    logger.info("cloud_function_triggered")
    try:
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(monitor_news())
        else:
            result = asyncio.run(monitor_news())
        return f"Success: {result}"
    except Exception as e:
        logger.exception("scraper_run_failed")
        return f"Error: {e}"


if __name__ == "__main__":
    print(run_scraper(None))
