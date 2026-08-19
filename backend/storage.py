import sqlite3
from pathlib import Path

from state import ConversationState, utc_now


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def save(self, state: ConversationState) -> None:
        state.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversations (id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (state.id, state.model_dump_json(), state.created_at, state.updated_at),
            )

    def get(self, conversation_id: str) -> ConversationState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return ConversationState.model_validate_json(row["state_json"]) if row else None
