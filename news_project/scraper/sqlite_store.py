import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:
    from .config import DATA_DIR
except ImportError:
    from scraper.config import DATA_DIR


DB_PATH = Path(os.getenv("NEWS_DB_PATH", os.path.join(DATA_DIR, "news_monitor.db")))

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    title TEXT,
    link TEXT NOT NULL UNIQUE,
    summary TEXT,
    date TEXT,
    venue TEXT,
    source_domain TEXT,
    type TEXT,
    ai_score INTEGER DEFAULT 0,
    impact_score INTEGER DEFAULT 0,
    personal_score INTEGER DEFAULT 0,
    negative_score INTEGER DEFAULT 0,
    score INTEGER DEFAULT 0,
    is_tech_release INTEGER DEFAULT 0,
    code_url TEXT,
    score_reason TEXT,
    inbox_status TEXT DEFAULT 'library',
    is_favorite INTEGER DEFAULT 0,
    comment TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (article_id, tag),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS article_origins (
    article_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    dataset_status TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (article_id, file_name),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS seen_links (
    link TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    domain TEXT,
    last_hash TEXT,
    health_score INTEGER DEFAULT 100,
    last_checked_at TEXT,
    last_success_at TEXT,
    last_failure_at TEXT,
    last_changed_at TEXT,
    last_error_stage TEXT,
    last_error_type TEXT,
    last_error TEXT,
    last_retryable INTEGER DEFAULT 0,
    last_attempts INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    total_successes INTEGER DEFAULT 0,
    total_failures INTEGER DEFAULT 0,
    empty_extract_count INTEGER DEFAULT 0,
    consecutive_empty_extracts INTEGER DEFAULT 0,
    unchanged_count INTEGER DEFAULT 0,
    last_article_count INTEGER DEFAULT 0,
    last_new_article_count INTEGER DEFAULT 0,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS source_failures (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    time TEXT,
    stage TEXT,
    error_type TEXT,
    message TEXT,
    retryable INTEGER,
    attempts INTEGER,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_articles_status_score ON articles(inbox_status, score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_favorite_score ON articles(is_favorite, score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag);
CREATE INDEX IF NOT EXISTS idx_sources_health ON sources(health_score, consecutive_failures);

DROP VIEW IF EXISTS v_latest_news;
DROP VIEW IF EXISTS v_latest_arxiv;
DROP VIEW IF EXISTS v_history_news;
DROP VIEW IF EXISTS v_history_arxiv;
DROP VIEW IF EXISTS v_favorites;

CREATE VIEW v_latest_news AS
    SELECT * FROM articles WHERE inbox_status = 'latest' AND link NOT LIKE '%arxiv.org%';
CREATE VIEW v_latest_arxiv AS
    SELECT * FROM articles WHERE inbox_status = 'latest' AND link LIKE '%arxiv.org%';
CREATE VIEW v_history_news AS
    SELECT * FROM articles WHERE inbox_status = 'history' AND link NOT LIKE '%arxiv.org%';
CREATE VIEW v_history_arxiv AS
    SELECT * FROM articles WHERE inbox_status = 'history' AND link LIKE '%arxiv.org%';
CREATE VIEW v_favorites AS
    SELECT * FROM articles WHERE is_favorite = 1;
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    ensure_runtime_columns(conn)
    return conn


def ensure_runtime_columns(conn: sqlite3.Connection) -> None:
    existing_source_cols = {row["name"] for row in conn.execute("PRAGMA table_info(sources)")}
    if "last_retryable" not in existing_source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN last_retryable INTEGER DEFAULT 0")
    if "last_attempts" not in existing_source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN last_attempts INTEGER DEFAULT 0")

    existing_origin_cols = {row["name"] for row in conn.execute("PRAGMA table_info(article_origins)")}
    if "occurrence_count" not in existing_origin_cols:
        conn.execute("ALTER TABLE article_origins ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1")
    conn.commit()


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def as_bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def clean_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return sorted({str(tag).strip() for tag in value if str(tag).strip()})
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def infer_type(article: Dict[str, Any], fallback_type: Optional[str] = None) -> str:
    if article.get("type"):
        return str(article["type"])
    if fallback_type:
        return fallback_type
    return "paper" if "arxiv.org" in article.get("link", "").lower() else "news"


def merge_status(existing: str, incoming: str) -> str:
    priority = {"latest": 3, "history": 2, "library": 1, None: 0, "": 0}
    return incoming if priority.get(incoming, 0) > priority.get(existing, 0) else existing


def article_payload(article: Dict[str, Any], inbox_status: str = "library", fallback_type: Optional[str] = None, is_favorite: bool = False) -> Dict[str, Any]:
    negative_score = article.get("negative_score", article.get("negtive_score", 0))
    link = str(article.get("link", ""))
    return {
        "title": article.get("title", ""),
        "link": link,
        "summary": article.get("summary", ""),
        "date": article.get("date", ""),
        "venue": article.get("venue", ""),
        "source_domain": article.get("source_domain", urlparse(link).netloc),
        "type": infer_type(article, fallback_type),
        "ai_score": as_int(article.get("ai_score")),
        "impact_score": as_int(article.get("impact_score")),
        "personal_score": as_int(article.get("personal_score")),
        "negative_score": as_int(negative_score),
        "score": as_int(article.get("score")),
        "is_tech_release": as_bool_int(article.get("is_tech_release")),
        "code_url": article.get("code_url"),
        "score_reason": article.get("score_reason", ""),
        "inbox_status": inbox_status,
        "is_favorite": 1 if is_favorite else 0,
        "comment": article.get("comment", ""),
        "raw_json": as_json(article),
    }


def _article_from_row(row: sqlite3.Row, tags: List[str]) -> Dict[str, Any]:
    article = dict(row)
    article["is_tech_release"] = bool(article.get("is_tech_release"))
    article["is_favorite"] = bool(article.get("is_favorite"))
    article["tags"] = tags
    return article


def _tags_for_articles(conn: sqlite3.Connection, article_ids: Iterable[int]) -> Dict[int, List[str]]:
    ids = [int(article_id) for article_id in article_ids]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT article_id, tag FROM article_tags WHERE article_id IN ({placeholders}) ORDER BY tag",
        ids,
    ).fetchall()
    tags: Dict[int, List[str]] = {article_id: [] for article_id in ids}
    for row in rows:
        tags.setdefault(int(row["article_id"]), []).append(row["tag"])
    return tags


def upsert_article(
    conn: sqlite3.Connection,
    article: Dict[str, Any],
    inbox_status: str = "library",
    fallback_type: Optional[str] = None,
    is_favorite: bool = False,
    origin_file: Optional[str] = None,
) -> Optional[int]:
    payload = article_payload(article, inbox_status, fallback_type, is_favorite)
    if not payload["link"]:
        return None

    existing = conn.execute("SELECT * FROM articles WHERE link = ?", (payload["link"],)).fetchone()
    timestamp = now_iso()
    if existing:
        merged = dict(existing)
        for key, value in payload.items():
            if key == "link":
                continue
            if key == "inbox_status":
                merged[key] = merge_status(merged.get(key), value)
            elif key == "is_favorite":
                merged[key] = max(as_int(merged.get(key)), as_int(value))
            elif key == "comment":
                merged[key] = value or merged.get(key, "")
            elif value not in (None, ""):
                merged[key] = value
        merged["updated_at"] = timestamp
        conn.execute(
            """
            UPDATE articles
            SET title = ?, summary = ?, date = ?, venue = ?, source_domain = ?, type = ?,
                ai_score = ?, impact_score = ?, personal_score = ?, negative_score = ?, score = ?,
                is_tech_release = ?, code_url = ?, score_reason = ?, inbox_status = ?,
                is_favorite = ?, comment = ?, raw_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["title"],
                merged["summary"],
                merged["date"],
                merged["venue"],
                merged["source_domain"],
                merged["type"],
                merged["ai_score"],
                merged["impact_score"],
                merged["personal_score"],
                merged["negative_score"],
                merged["score"],
                merged["is_tech_release"],
                merged["code_url"],
                merged["score_reason"],
                merged["inbox_status"],
                merged["is_favorite"],
                merged["comment"],
                merged["raw_json"],
                merged["updated_at"],
                merged["id"],
            ),
        )
        article_id = int(merged["id"])
    else:
        conn.execute(
            """
            INSERT INTO articles (
                title, link, summary, date, venue, source_domain, type,
                ai_score, impact_score, personal_score, negative_score, score,
                is_tech_release, code_url, score_reason, inbox_status, is_favorite,
                comment, raw_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"],
                payload["link"],
                payload["summary"],
                payload["date"],
                payload["venue"],
                payload["source_domain"],
                payload["type"],
                payload["ai_score"],
                payload["impact_score"],
                payload["personal_score"],
                payload["negative_score"],
                payload["score"],
                payload["is_tech_release"],
                payload["code_url"],
                payload["score_reason"],
                payload["inbox_status"],
                payload["is_favorite"],
                payload["comment"],
                payload["raw_json"],
                timestamp,
                timestamp,
            ),
        )
        article_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    if origin_file:
        conn.execute(
            """
            INSERT INTO article_origins(article_id, file_name, dataset_status, occurrence_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(article_id, file_name) DO UPDATE SET occurrence_count = occurrence_count + 1
            """,
            (article_id, origin_file, inbox_status),
        )

    for tag in clean_tags(article.get("tags")):
        conn.execute("INSERT OR IGNORE INTO article_tags(article_id, tag) VALUES (?, ?)", (article_id, tag))

    return article_id


def load_articles(conn: sqlite3.Connection, *, inbox_status: Optional[str] = None, arxiv: Optional[bool] = None, favorites: bool = False) -> List[Dict[str, Any]]:
    where = []
    params: List[Any] = []
    if inbox_status:
        where.append("inbox_status = ?")
        params.append(inbox_status)
    if arxiv is True:
        where.append("link LIKE '%arxiv.org%'")
    elif arxiv is False:
        where.append("link NOT LIKE '%arxiv.org%'")
    if favorites:
        where.append("is_favorite = 1")

    sql = "SELECT * FROM articles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, date DESC"

    rows = conn.execute(sql, params).fetchall()
    tag_map = _tags_for_articles(conn, [row["id"] for row in rows])
    return [_article_from_row(row, tag_map.get(int(row["id"]), [])) for row in rows]


def mark_seen(conn: sqlite3.Connection, link: str) -> None:
    if link:
        conn.execute("INSERT OR IGNORE INTO seen_links(link) VALUES (?)", (link,))


def is_seen(conn: sqlite3.Connection, link: str) -> bool:
    if not link:
        return True
    if conn.execute("SELECT 1 FROM seen_links WHERE link = ?", (link,)).fetchone():
        return True
    return conn.execute("SELECT 1 FROM articles WHERE link = ?", (link,)).fetchone() is not None


def latest_origin_for_article(article: Dict[str, Any]) -> str:
    return "latest_arxiv.json" if "arxiv.org" in article.get("link", "").lower() else "latest_news.json"


def add_latest_articles(conn: sqlite3.Connection, articles: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for article in articles:
        if not article.get("link"):
            continue
        upsert_article(conn, article, inbox_status="latest", fallback_type=article.get("type"), origin_file=latest_origin_for_article(article))
        mark_seen(conn, article["link"])
        count += 1
    return count


def archive_links(conn: sqlite3.Connection, *, arxiv: Optional[bool], links: Optional[Iterable[str]] = None) -> int:
    params: List[Any] = []
    where = ["inbox_status = 'latest'"]
    if arxiv is True:
        where.append("link LIKE '%arxiv.org%'")
    elif arxiv is False:
        where.append("link NOT LIKE '%arxiv.org%'")
    selected_links = list(links or [])
    if selected_links:
        where.append(f"link IN ({','.join('?' for _ in selected_links)})")
        params.extend(selected_links)
    sql = "UPDATE articles SET inbox_status = 'history', updated_at = ? WHERE " + " AND ".join(where)
    conn.execute(sql, [now_iso(), *params])
    return int(conn.execute("SELECT changes()").fetchone()[0])


def delete_favorites(conn: sqlite3.Connection, links: Iterable[str]) -> int:
    selected_links = [link for link in links if link]
    if not selected_links:
        return 0
    placeholders = ",".join("?" for _ in selected_links)
    conn.execute(
        f"UPDATE articles SET is_favorite = 0, updated_at = ? WHERE link IN ({placeholders})",
        [now_iso(), *selected_links],
    )
    return int(conn.execute("SELECT changes()").fetchone()[0])


def update_comments(conn: sqlite3.Connection, comments_by_link: Dict[str, str]) -> int:
    updated = 0
    timestamp = now_iso()
    for link, comment in comments_by_link.items():
        if not link:
            continue
        conn.execute("UPDATE articles SET comment = ?, updated_at = ? WHERE link = ?", (comment, timestamp, link))
        updated += int(conn.execute("SELECT changes()").fetchone()[0])
    return updated


def ensure_source(conn: sqlite3.Connection, url: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO sources(url, domain, raw_json) VALUES (?, ?, ?)",
        (url, urlparse(url).netloc, "{}"),
    )
    return int(conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()[0])


def get_page_hash(conn: sqlite3.Connection, url: str) -> str:
    row = conn.execute("SELECT last_hash FROM sources WHERE url = ?", (url,)).fetchone()
    return row["last_hash"] if row and row["last_hash"] else ""


def save_page_hash(conn: sqlite3.Connection, url: str, content_hash: str) -> None:
    ensure_source(conn, url)
    conn.execute("UPDATE sources SET last_hash = ?, raw_json = raw_json WHERE url = ?", (content_hash, url))


def compute_health_score(entry: Dict[str, Any]) -> int:
    score = 100
    score -= as_int(entry.get("consecutive_failures")) * 20
    score -= as_int(entry.get("consecutive_empty_extracts")) * 10
    score -= min(as_int(entry.get("unchanged_count")), 20)
    if entry.get("last_error_type") in {"access_denied", "client_error"}:
        score -= 15
    return max(0, min(100, score))


def source_entry(conn: sqlite3.Connection, url: str) -> Dict[str, Any]:
    ensure_source(conn, url)
    row = conn.execute("SELECT * FROM sources WHERE url = ?", (url,)).fetchone()
    return dict(row)


def update_source(conn: sqlite3.Connection, url: str, updates: Dict[str, Any]) -> None:
    ensure_source(conn, url)
    entry = source_entry(conn, url)
    entry.update(updates)
    entry["health_score"] = compute_health_score(entry)
    entry["raw_json"] = as_json(entry)
    conn.execute(
        """
        UPDATE sources
        SET domain = ?, last_hash = ?, health_score = ?, last_checked_at = ?, last_success_at = ?,
            last_failure_at = ?, last_changed_at = ?, last_error_stage = ?, last_error_type = ?,
            last_error = ?, last_retryable = ?, last_attempts = ?, consecutive_failures = ?,
            total_successes = ?, total_failures = ?, empty_extract_count = ?,
            consecutive_empty_extracts = ?, unchanged_count = ?, last_article_count = ?,
            last_new_article_count = ?, raw_json = ?
        WHERE url = ?
        """,
        (
            entry.get("domain", urlparse(url).netloc),
            entry.get("last_hash"),
            as_int(entry.get("health_score"), 100),
            entry.get("last_checked_at"),
            entry.get("last_success_at"),
            entry.get("last_failure_at"),
            entry.get("last_changed_at"),
            entry.get("last_error_stage"),
            entry.get("last_error_type"),
            entry.get("last_error"),
            as_bool_int(entry.get("last_retryable")),
            as_int(entry.get("last_attempts")),
            as_int(entry.get("consecutive_failures")),
            as_int(entry.get("total_successes")),
            as_int(entry.get("total_failures")),
            as_int(entry.get("empty_extract_count")),
            as_int(entry.get("consecutive_empty_extracts")),
            as_int(entry.get("unchanged_count")),
            as_int(entry.get("last_article_count")),
            as_int(entry.get("last_new_article_count")),
            entry.get("raw_json"),
            url,
        ),
    )


def record_failure(conn: sqlite3.Connection, url: str, stage: str, error_type: str, message: str, retryable: bool, attempts: int) -> None:
    now = now_iso()
    entry = source_entry(conn, url)
    source_id = int(entry["id"])
    conn.execute(
        """
        INSERT INTO source_failures(source_id, time, stage, error_type, message, retryable, attempts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (source_id, now, stage, error_type, str(message)[:500], as_bool_int(retryable), attempts),
    )
    update_source(
        conn,
        url,
        {
            "last_checked_at": now,
            "last_failure_at": now,
            "last_error_stage": stage,
            "last_error_type": error_type,
            "last_error": str(message)[:500],
            "last_retryable": as_bool_int(retryable),
            "last_attempts": attempts,
            "total_failures": as_int(entry.get("total_failures")) + 1,
            "consecutive_failures": as_int(entry.get("consecutive_failures")) + 1,
        },
    )


def load_source_health(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    rows = conn.execute("SELECT * FROM sources ORDER BY url").fetchall()
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        entry = dict(row)
        failures = conn.execute(
            """
            SELECT time, stage, error_type, message, retryable, attempts
            FROM source_failures
            WHERE source_id = ?
            ORDER BY id DESC
            LIMIT 25
            """,
            (entry["id"],),
        ).fetchall()
        entry["failure_queue"] = [dict(failure) for failure in failures]
        result[entry["url"]] = entry
    return result
