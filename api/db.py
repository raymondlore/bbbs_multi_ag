"""SQLite 연결과 스키마 초기화."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    deploy_url TEXT,
    repo_url TEXT,
    author TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    image_filename TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS project_tags (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_project_tags_tag ON project_tags(tag_id, project_id);
"""

_init_lock = threading.Lock()
_initialized: set[str] = set()


def get_data_dir() -> Path:
    """DATA_DIR 환경변수를 호출 시점에 읽는다(테스트에서 변경 가능)."""
    return Path(os.environ.get("DATA_DIR", "./data")).resolve()


def get_upload_dir() -> Path:
    return get_data_dir() / "uploads"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")


def init_db() -> None:
    """데이터 폴더와 테이블을 만든다(경로별로 1회)."""
    data_dir = get_data_dir()
    key = str(data_dir)
    with _init_lock:
        db_path = data_dir / "app.db"
        if key in _initialized and db_path.exists():
            return
        get_upload_dir().mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            _configure(conn)
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        _initialized.add(key)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """요청마다 새 연결을 만든다. 정상 종료 시 커밋, 예외 시 롤백."""
    init_db()
    conn = sqlite3.connect(get_data_dir() / "app.db")
    conn.row_factory = sqlite3.Row
    try:
        _configure(conn)
        with conn:
            yield conn
    finally:
        conn.close()
