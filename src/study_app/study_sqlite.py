from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class StudySQLiteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS progress (
                    topic_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS card_reviews (
                    item_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS question_attempts (
                    item_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS daily_sessions (
                    session_date TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS mock_exams (
                    mock_exam_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS attempt_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS json_state (
                    state_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            conn.commit()

    def load_mapping(self, table: str, key_column: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {key_column}, payload_json FROM {table}"
            ).fetchall()
        return {
            str(row[key_column]): _json_loads(row["payload_json"], {}) for row in rows
        }

    def save_mapping(
        self, table: str, key_column: str, payload: dict[str, Any]
    ) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {table}")
            for key, value in payload.items():
                conn.execute(
                    f"INSERT INTO {table} ({key_column}, payload_json) VALUES (?, ?)",
                    (key, _json_dumps(value)),
                )
            conn.commit()

    def load_list(self, table: str, order_by: str = "id") -> list[Any]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload_json FROM {table} ORDER BY {order_by}"
            ).fetchall()
        return [_json_loads(row["payload_json"], {}) for row in rows]

    def save_list(self, table: str, payload: list[Any]) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {table}")
            for value in payload:
                conn.execute(
                    f"INSERT INTO {table} (payload_json) VALUES (?)",
                    (_json_dumps(value),),
                )
            conn.commit()

    def load_named_json(self, state_key: str, default: Any) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM json_state WHERE state_key = ?",
                (state_key,),
            ).fetchone()
        return _json_loads(row["payload_json"], default) if row else default

    def save_named_json(self, state_key: str, payload: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "REPLACE INTO json_state (state_key, payload_json) VALUES (?, ?)",
                (state_key, _json_dumps(payload)),
            )
            conn.commit()


def get_study_db_path(state_dir: Path) -> Path:
    return state_dir / "study_state.db"


def get_study_store(state_dir: Path) -> StudySQLiteStore:
    return StudySQLiteStore(get_study_db_path(state_dir))
