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
                    owner_user_id INTEGER,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def save(self, state: ConversationState) -> None:
        state.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversations (id, owner_user_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET owner_user_id=excluded.owner_user_id, state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (state.id, state.owner_user_id, state.model_dump_json(), state.created_at, state.updated_at),
            )

    def get(self, conversation_id: str) -> ConversationState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return ConversationState.model_validate_json(row["state_json"]) if row else None

    def list_for_owner(self, owner_user_id: int | None) -> list[ConversationState]:
        query = "SELECT state_json FROM conversations"
        parameters = ()
        if owner_user_id is not None:
            query += " WHERE owner_user_id = ?"
            parameters = (owner_user_id,)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [ConversationState.model_validate_json(row["state_json"]) for row in rows]
