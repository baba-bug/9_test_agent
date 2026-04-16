import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "news_monitor.db"

ARTICLE_FILES = [
    ("latest_news.json", "latest", "news", False),
    ("latest_arxiv.json", "latest", "paper", False),
    ("history_news.json", "history", "news", False),
    ("history_arxiv.json", "history", "paper", False),
    ("favorites.json", "library", None, True),
]


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

CREATE INDEX IF NOT EXISTS idx_articles_status_type_score ON articles(inbox_status, type, score DESC);
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


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def as_bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def clean_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return sorted({str(tag).strip() for tag in value if str(tag).strip()})
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def infer_type(article: Dict[str, Any], fallback_type: str = None) -> str:
    if article.get("type"):
        return str(article["type"])
    if fallback_type:
        return fallback_type
    return "paper" if "arxiv.org" in article.get("link", "").lower() else "news"


def merge_status(existing: str, incoming: str) -> str:
    priority = {"latest": 3, "history": 2, "library": 1, None: 0, "": 0}
    return incoming if priority.get(incoming, 0) > priority.get(existing, 0) else existing


def article_payload(article: Dict[str, Any], inbox_status: str, fallback_type: str, is_favorite: bool) -> Dict[str, Any]:
    negative_score = article.get("negative_score", article.get("negtive_score", 0))
    return {
        "title": article.get("title", ""),
        "link": article.get("link", ""),
        "summary": article.get("summary", ""),
        "date": article.get("date", ""),
        "venue": article.get("venue", ""),
        "source_domain": article.get("source_domain", urlparse(article.get("link", "")).netloc),
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
        "raw_json": json.dumps(article, ensure_ascii=False),
    }


def upsert_article(conn: sqlite3.Connection, payload: Dict[str, Any], tags: Iterable[str], file_name: str) -> int:
    existing = conn.execute("SELECT * FROM articles WHERE link = ?", (payload["link"],)).fetchone()
    timestamp = now_iso()

    if existing:
        merged = dict(existing)
        for key, value in payload.items():
            if key in {"link", "created_at"}:
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

    conn.execute(
        """
        INSERT INTO article_origins(article_id, file_name, dataset_status, occurrence_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(article_id, file_name) DO UPDATE SET
            occurrence_count = occurrence_count + 1
        """,
        (article_id, file_name, payload["inbox_status"]),
    )
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO article_tags(article_id, tag) VALUES (?, ?)", (article_id, tag))
    return article_id


def initialize_database(db_path: Path, recreate: bool) -> None:
    if db_path.exists() and recreate:
        backup_path = db_path.with_suffix(db_path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(db_path, backup_path)
        db_path.unlink()
        print(f"Existing database backed up to {backup_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)


def import_articles(conn: sqlite3.Connection) -> Dict[str, int]:
    counts = {}
    skipped = {}
    for file_name, inbox_status, fallback_type, is_favorite in ARTICLE_FILES:
        path = ROOT_DIR / file_name
        rows = load_json(path, [])
        counts[file_name] = len(rows)
        skipped[file_name] = 0
        for article in rows:
            if not isinstance(article, dict) or not article.get("link"):
                skipped[file_name] += 1
                continue
            payload = article_payload(article, inbox_status, fallback_type, is_favorite)
            upsert_article(conn, payload, clean_tags(article.get("tags")), file_name)
    return {**{f"json_{k}": v for k, v in counts.items()}, **{f"skipped_{k}": v for k, v in skipped.items()}}


def import_state(conn: sqlite3.Connection) -> Dict[str, int]:
    state = load_json(ROOT_DIR / "news_state.json", {})
    seen_links = state.get("seen_links", [])
    page_hashes = state.get("page_hashes", {})
    source_health = state.get("source_health", {})

    for link in seen_links:
        if link:
            conn.execute("INSERT OR IGNORE INTO seen_links(link) VALUES (?)", (link,))

    for url, page_hash in page_hashes.items():
        entry = source_health.get(url, {})
        source_id = upsert_source(conn, url, page_hash, entry)
        for failure in entry.get("failure_queue", []):
            conn.execute(
                """
                INSERT INTO source_failures(source_id, time, stage, error_type, message, retryable, attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    failure.get("time"),
                    failure.get("stage"),
                    failure.get("error_type"),
                    failure.get("message"),
                    as_bool_int(failure.get("retryable")),
                    as_int(failure.get("attempts"), 1),
                ),
            )

    for url, entry in source_health.items():
        if url not in page_hashes:
            upsert_source(conn, url, entry.get("last_hash", ""), entry)

    return {
        "seen_links": len(seen_links),
        "page_hashes": len(page_hashes),
        "source_health": len(source_health),
    }


def upsert_source(conn: sqlite3.Connection, url: str, page_hash: str, entry: Dict[str, Any]) -> int:
    conn.execute(
        """
        INSERT INTO sources (
            url, domain, last_hash, health_score, last_checked_at, last_success_at,
            last_failure_at, last_changed_at, last_error_stage, last_error_type,
            last_error, last_retryable, last_attempts, consecutive_failures, total_successes, total_failures,
            empty_extract_count, consecutive_empty_extracts, unchanged_count,
            last_article_count, last_new_article_count, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            domain = excluded.domain,
            last_hash = excluded.last_hash,
            health_score = excluded.health_score,
            last_checked_at = excluded.last_checked_at,
            last_success_at = excluded.last_success_at,
            last_failure_at = excluded.last_failure_at,
            last_changed_at = excluded.last_changed_at,
            last_error_stage = excluded.last_error_stage,
            last_error_type = excluded.last_error_type,
            last_error = excluded.last_error,
            last_retryable = excluded.last_retryable,
            last_attempts = excluded.last_attempts,
            consecutive_failures = excluded.consecutive_failures,
            total_successes = excluded.total_successes,
            total_failures = excluded.total_failures,
            empty_extract_count = excluded.empty_extract_count,
            consecutive_empty_extracts = excluded.consecutive_empty_extracts,
            unchanged_count = excluded.unchanged_count,
            last_article_count = excluded.last_article_count,
            last_new_article_count = excluded.last_new_article_count,
            raw_json = excluded.raw_json
        """,
        (
            url,
            entry.get("domain", urlparse(url).netloc),
            entry.get("last_hash", page_hash),
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
            json.dumps(entry, ensure_ascii=False),
        ),
    )
    return int(conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()[0])


def migrate(db_path: Path, recreate: bool) -> Dict[str, int]:
    initialize_database(db_path, recreate=recreate)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
            ensure_runtime_columns(conn)
            article_counts = import_articles(conn)
            state_counts = import_state(conn)
        return {**article_counts, **state_counts, **validate(db_path)}
    finally:
        conn.close()


def ensure_runtime_columns(conn: sqlite3.Connection) -> None:
    source_cols = {row["name"] for row in conn.execute("PRAGMA table_info(sources)")}
    if "last_retryable" not in source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN last_retryable INTEGER DEFAULT 0")
    if "last_attempts" not in source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN last_attempts INTEGER DEFAULT 0")

    origin_cols = {row["name"] for row in conn.execute("PRAGMA table_info(article_origins)")}
    if "occurrence_count" not in origin_cols:
        conn.execute("ALTER TABLE article_origins ADD COLUMN occurrence_count INTEGER NOT NULL DEFAULT 1")


def scalar(conn: sqlite3.Connection, query: str, params: Tuple[Any, ...] = ()) -> int:
    return int(conn.execute(query, params).fetchone()[0])


def validate(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        result = {
            "sqlite_articles": scalar(conn, "SELECT COUNT(*) FROM articles"),
            "sqlite_latest": scalar(conn, "SELECT COUNT(*) FROM articles WHERE inbox_status = 'latest'"),
            "sqlite_history": scalar(conn, "SELECT COUNT(*) FROM articles WHERE inbox_status = 'history'"),
            "sqlite_favorites": scalar(conn, "SELECT COUNT(*) FROM articles WHERE is_favorite = 1"),
            "sqlite_tags": scalar(conn, "SELECT COUNT(*) FROM article_tags"),
            "sqlite_sources": scalar(conn, "SELECT COUNT(*) FROM sources"),
            "sqlite_seen_links": scalar(conn, "SELECT COUNT(*) FROM seen_links"),
        }
        for file_name, _, _, _ in ARTICLE_FILES:
            result[f"origin_unique_{file_name}"] = scalar(
                conn,
                "SELECT COUNT(*) FROM article_origins WHERE file_name = ?",
                (file_name,),
            )
            result[f"origin_rows_{file_name}"] = scalar(
                conn,
                "SELECT COALESCE(SUM(occurrence_count), 0) FROM article_origins WHERE file_name = ?",
                (file_name,),
            )
        return result
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate current JSON news monitor data into a SQLite sidecar database.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path.")
    parser.add_argument("--recreate", action="store_true", help="Back up and recreate an existing SQLite database.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    result = migrate(db_path, recreate=args.recreate)
    print(f"SQLite database ready: {db_path}")
    for key in sorted(result):
        print(f"{key}: {result[key]}")


if __name__ == "__main__":
    main()
