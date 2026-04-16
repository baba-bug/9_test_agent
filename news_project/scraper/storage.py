from typing import Any, Dict, List, Set

try:
    from . import sqlite_store as db
    from .observability import get_logger
except ImportError:
    import scraper.sqlite_store as db
    from scraper.observability import get_logger


logger = get_logger(__name__)


class Storage:
    def __init__(self, file_path: str = "news_state.json"):
        self.file_name = file_path
        self.conn = db.connect()
        self.seen_links: Set[str] = set()
        self.page_hashes: Dict[str, str] = {}
        self.source_health: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        self.seen_links = {row["link"] for row in self.conn.execute("SELECT link FROM seen_links")}
        self.page_hashes = {
            row["url"]: row["last_hash"]
            for row in self.conn.execute("SELECT url, last_hash FROM sources WHERE last_hash IS NOT NULL")
        }
        self.source_health = db.load_source_health(self.conn)
        logger.info(
            "sqlite_state_loaded seen_links=%s page_hashes=%s sources=%s",
            len(self.seen_links),
            len(self.page_hashes),
            len(self.source_health),
        )

    def save(self) -> None:
        self.conn.commit()
        self.load()

    def is_new(self, link: str) -> bool:
        return not db.is_seen(self.conn, link)

    def add_seen(self, link: str) -> None:
        db.mark_seen(self.conn, link)
        self.seen_links.add(link)

    def get_page_hash(self, url: str) -> str:
        return db.get_page_hash(self.conn, url)

    def save_page_hash(self, url: str, content_hash: str) -> None:
        db.save_page_hash(self.conn, url, content_hash)
        self.page_hashes[url] = content_hash

    def filter_new_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [article for article in articles if article.get("link") and self.is_new(article["link"])]

    def save_latest_articles(self, articles: List[Dict[str, Any]]) -> int:
        count = db.add_latest_articles(self.conn, articles)
        self.conn.commit()
        self.load()
        logger.info("sqlite_latest_articles_saved count=%s", count)
        return count

    def load_favorites(self) -> List[Dict[str, Any]]:
        return db.load_articles(self.conn, favorites=True)

    def save_to_favorites(self, article: Dict[str, Any]) -> None:
        with self.conn:
            article_id = db.upsert_article(
                self.conn,
                article,
                inbox_status=article.get("inbox_status", "library"),
                fallback_type=article.get("type"),
                is_favorite=True,
                origin_file="favorites.json",
            )
        if article_id:
            logger.info("favorite_saved title=%s", article.get("title", ""))
        self.load()

    def record_source_failure(
        self,
        url: str,
        stage: str,
        error_type: str,
        message: str,
        retryable: bool = True,
        attempts: int = 1,
    ) -> None:
        db.record_failure(self.conn, url, stage, error_type, message, retryable, attempts)
        self.conn.commit()
        self.load()

    def record_source_success(self, url: str, stage: str = "run") -> None:
        entry = db.source_entry(self.conn, url)
        db.update_source(
            self.conn,
            url,
            {
                "last_checked_at": db.now_iso(),
                "last_success_at": db.now_iso(),
                "last_success_stage": stage,
                "total_successes": db.as_int(entry.get("total_successes")) + 1,
                "consecutive_failures": 0,
                "last_error": None,
                "last_error_type": None,
                "last_error_stage": None,
            },
        )
        self.conn.commit()
        self.load()

    def record_content_unchanged(self, url: str, content_hash: str) -> None:
        entry = db.source_entry(self.conn, url)
        db.update_source(
            self.conn,
            url,
            {
                "last_checked_at": db.now_iso(),
                "last_success_at": db.now_iso(),
                "last_hash": content_hash,
                "unchanged_count": db.as_int(entry.get("unchanged_count")) + 1,
                "consecutive_failures": 0,
            },
        )
        self.conn.commit()
        self.load()

    def record_content_changed(self, url: str, content_hash: str) -> None:
        db.update_source(
            self.conn,
            url,
            {
                "last_checked_at": db.now_iso(),
                "last_changed_at": db.now_iso(),
                "unchanged_count": 0,
                "consecutive_failures": 0,
            },
        )
        self.conn.commit()
        self.load()

    def record_extraction_result(self, url: str, article_count: int, new_article_count: int) -> None:
        entry = db.source_entry(self.conn, url)
        article_count = int(article_count)
        db.update_source(
            self.conn,
            url,
            {
                "last_checked_at": db.now_iso(),
                "last_success_at": db.now_iso(),
                "last_article_count": article_count,
                "last_new_article_count": int(new_article_count),
                "consecutive_failures": 0,
                "empty_extract_count": db.as_int(entry.get("empty_extract_count")) + (1 if article_count <= 0 else 0),
                "consecutive_empty_extracts": (
                    db.as_int(entry.get("consecutive_empty_extracts")) + 1 if article_count <= 0 else 0
                ),
            },
        )
        self.conn.commit()
        self.load()
