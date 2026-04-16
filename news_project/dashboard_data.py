import os
from typing import Any, Dict, Iterable, List, Tuple

from news_project.scraper.config import DATA_DIR
from news_project.scraper import sqlite_store as db


def data_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


def _file_name(file_path: str) -> str:
    return os.path.basename(file_path)


def _status_for_file(file_name: str) -> str:
    if file_name.startswith("latest_"):
        return "latest"
    if file_name.startswith("history_"):
        return "history"
    return "library"


def _arxiv_for_file(file_name: str):
    if "arxiv" in file_name:
        return True
    if "news" in file_name:
        return False
    return None


def load_data(file_path: str) -> List[Dict[str, Any]]:
    file_name = _file_name(file_path)
    conn = db.connect()
    try:
        if file_name == "favorites.json":
            return db.load_articles(conn, favorites=True)
        return db.load_articles(
            conn,
            inbox_status=_status_for_file(file_name),
            arxiv=_arxiv_for_file(file_name),
        )
    finally:
        conn.close()


def save_data(file_path: str, data: List[Dict[str, Any]]) -> None:
    file_name = _file_name(file_path)
    conn = db.connect()
    try:
        with conn:
            for item in data:
                if file_name == "favorites.json":
                    db.upsert_article(conn, item, inbox_status=item.get("inbox_status", "library"), is_favorite=True, origin_file=file_name)
                else:
                    db.upsert_article(
                        conn,
                        item,
                        inbox_status=_status_for_file(file_name),
                        fallback_type="paper" if _arxiv_for_file(file_name) else "news",
                        origin_file=file_name,
                    )
    finally:
        conn.close()


def archive_links(source_path: str, history_path: str, links: Iterable[str] = None) -> int:
    conn = db.connect()
    try:
        with conn:
            return db.archive_links(conn, arxiv=_arxiv_for_file(_file_name(source_path)), links=links)
    finally:
        conn.close()


def archive_all_latest() -> Dict[str, int]:
    conn = db.connect()
    try:
        with conn:
            return {
                "news": db.archive_links(conn, arxiv=False),
                "papers": db.archive_links(conn, arxiv=True),
            }
    finally:
        conn.close()


def delete_by_links(file_path: str, links: Iterable[str]) -> int:
    conn = db.connect()
    try:
        with conn:
            return db.delete_favorites(conn, links)
    finally:
        conn.close()


def update_comments(file_path: str, comments_by_link: Dict[str, str]) -> int:
    conn = db.connect()
    try:
        with conn:
            return db.update_comments(conn, comments_by_link)
    finally:
        conn.close()


def split_favorites(favorites: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    papers = [item for item in favorites if "arxiv.org" in item.get("link", "").lower()]
    news = [item for item in favorites if "arxiv.org" not in item.get("link", "").lower()]
    return news, papers


def source_health_rows(source_health: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for url, entry in sorted(source_health.items()):
        rows.append(
            {
                "score": entry.get("health_score", 100),
                "domain": entry.get("domain", ""),
                "url": url,
                "last_success": entry.get("last_success_at", ""),
                "last_failure": entry.get("last_failure_at", ""),
                "last_error_type": entry.get("last_error_type", ""),
                "consecutive_failures": entry.get("consecutive_failures", 0),
                "last_articles": entry.get("last_article_count", 0),
                "last_new": entry.get("last_new_article_count", 0),
                "empty_extracts": entry.get("empty_extract_count", 0),
                "unchanged_count": entry.get("unchanged_count", 0),
                "last_error": entry.get("last_error", ""),
            }
        )
    return rows
