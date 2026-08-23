"""SQLite storage for Anubis metadata."""

import json
import sqlite3
from pathlib import Path

from .models import Checkpoint, SemanticCommit

ANUBIS_DIR = ".anubis"
DB_NAME = "anubis.db"


def get_db_path(repo_root: Path) -> Path:
    """Get the path to the Anubis database."""
    return repo_root / ANUBIS_DIR / DB_NAME


def init_db(repo_root: Path) -> Path:
    """Initialize the Anubis database."""
    anubis_dir = repo_root / ANUBIS_DIR
    anubis_dir.mkdir(exist_ok=True)

    db_path = anubis_dir / DB_NAME
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            message TEXT NOT NULL,
            reasoning TEXT,
            git_ref TEXT,
            files_context TEXT,  -- JSON array
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS semantic_commits (
            id TEXT PRIMARY KEY,
            git_sha TEXT NOT NULL UNIQUE,
            timestamp TEXT NOT NULL,
            message TEXT NOT NULL,
            operations TEXT,  -- JSON array
            reasoning TEXT,
            checkpoint_id TEXT REFERENCES checkpoints(id)
        );

        CREATE INDEX IF NOT EXISTS idx_checkpoints_timestamp ON checkpoints(timestamp);
        CREATE INDEX IF NOT EXISTS idx_commits_timestamp ON semantic_commits(timestamp);
        CREATE INDEX IF NOT EXISTS idx_commits_git_sha ON semantic_commits(git_sha);
    """)

    conn.commit()
    conn.close()
    return db_path


class Storage:
    """Storage interface for Anubis metadata."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.db_path = get_db_path(repo_root)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint to the database."""
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO checkpoints (id, timestamp, message, reasoning, git_ref, files_context, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint.id,
                checkpoint.timestamp.isoformat(),
                checkpoint.message,
                checkpoint.reasoning,
                checkpoint.git_ref,
                json.dumps(checkpoint.files_context),
                checkpoint.summary,
            ),
        )
        conn.commit()
        conn.close()

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Get a checkpoint by ID (supports prefix matching)."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM checkpoints WHERE id LIKE ? ORDER BY timestamp DESC LIMIT 1",
            (f"{checkpoint_id}%",),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return Checkpoint.from_dict({
            "id": row[0],
            "timestamp": row[1],
            "message": row[2],
            "reasoning": row[3],
            "git_ref": row[4],
            "files_context": json.loads(row[5]) if row[5] else [],
            "summary": row[6],
        })

    def list_checkpoints(self, limit: int = 10) -> list[Checkpoint]:
        """List recent checkpoints."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM checkpoints ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            Checkpoint.from_dict({
                "id": row[0],
                "timestamp": row[1],
                "message": row[2],
                "reasoning": row[3],
                "git_ref": row[4],
                "files_context": json.loads(row[5]) if row[5] else [],
                "summary": row[6],
            })
            for row in rows
        ]

    def save_commit(self, commit: SemanticCommit) -> None:
        """Save a semantic commit to the database."""
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO semantic_commits
            (id, git_sha, timestamp, message, operations, reasoning, checkpoint_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commit.id,
                commit.git_sha,
                commit.timestamp.isoformat(),
                commit.message,
                json.dumps([op.to_dict() for op in commit.operations]),
                commit.reasoning,
                commit.checkpoint_id,
            ),
        )
        conn.commit()
        conn.close()

    def get_commit_by_sha(self, git_sha: str) -> SemanticCommit | None:
        """Get a semantic commit by git SHA."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM semantic_commits WHERE git_sha LIKE ?",
            (f"{git_sha}%",),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return SemanticCommit.from_dict({
            "id": row[0],
            "git_sha": row[1],
            "timestamp": row[2],
            "message": row[3],
            "operations": json.loads(row[4]) if row[4] else [],
            "reasoning": row[5],
            "checkpoint_id": row[6],
        })

    def list_commits(self, limit: int = 10) -> list[SemanticCommit]:
        """List recent semantic commits."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM semantic_commits ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            SemanticCommit.from_dict({
                "id": row[0],
                "git_sha": row[1],
                "timestamp": row[2],
                "message": row[3],
                "operations": json.loads(row[4]) if row[4] else [],
                "reasoning": row[5],
                "checkpoint_id": row[6],
            })
            for row in rows
        ]
