import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
create table if not exists datasets (
  id text primary key,
  created_at text not null,
  lang text,
  tolerances_json text not null default '{}'
);
create table if not exists dataset_files (
  dataset_id text not null,
  kind text not null,
  table_name text not null,
  filename text not null,
  rows integer not null,
  sha256 text not null,
  path text not null,
  seq integer not null default 0,
  primary key (dataset_id, kind, table_name)
);
create table if not exists runs (
  id text primary key,
  created_at text not null,
  updated_at text not null,
  lang text not null,
  filename text not null,
  status text not null,
  source text not null,
  source_sha256 text not null,
  dataset_id text not null,
  translation_source text,
  model text,
  accepted integer not null default 0,
  risky_source_json text not null default '[]',
  error_json text
);
create table if not exists revisions (
  run_id text not null,
  idx integer not null,
  label text not null,
  python text not null,
  python_sha256 text not null,
  risky_python_json text not null default '[]',
  changed_lines_json text not null default '[]',
  checks_json text not null default '[]',
  summary_json text not null default '{}',
  explanation_json text,
  patch_json text,
  created_at text not null,
  primary key (run_id, idx)
);
"""


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id():
    return uuid.uuid4().hex[:12]


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


def loads(text, default=None):
    if text is None:
        return default
    return json.loads(text)


@contextmanager
def session():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=wal")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    with session() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "update runs set status = 'failed', error_json = ?, updated_at = ? where status = 'running'",
            (
                dumps(
                    {
                        "step": "run",
                        "message": "The server restarted during this run.",
                        "stderr": "",
                    }
                ),
                now_iso(),
            ),
        )
