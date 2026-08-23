"""Data models for Anubis."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class Checkpoint:
    """A lightweight snapshot of work-in-progress with reasoning context."""

    message: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning: str | None = None
    git_ref: str | None = None  # commit sha or stash ref
    files_context: list[str] = field(default_factory=list)
    summary: str | None = None  # context summary for resume

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "reasoning": self.reasoning,
            "git_ref": self.git_ref,
            "files_context": self.files_context,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data["message"],
            reasoning=data.get("reasoning"),
            git_ref=data.get("git_ref"),
            files_context=data.get("files_context", []),
            summary=data.get("summary"),
        )


@dataclass
class SemanticOperation:
    """A semantic description of a code change."""

    op_type: str  # e.g., "rename", "extract_function", "add_function", "modify"
    target: str  # e.g., "auth.py:login" or "AuthHandler"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.op_type,
            "target": self.target,
            **self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticOperation":
        op_type = data.pop("type")
        target = data.pop("target")
        return cls(op_type=op_type, target=target, details=data)


@dataclass
class SemanticCommit:
    """A git commit enriched with semantic metadata."""

    message: str
    git_sha: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    operations: list[SemanticOperation] = field(default_factory=list)
    reasoning: str | None = None
    checkpoint_id: str | None = None  # link to checkpoint if created from one

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "git_sha": self.git_sha,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "operations": [op.to_dict() for op in self.operations],
            "reasoning": self.reasoning,
            "checkpoint_id": self.checkpoint_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticCommit":
        operations = [SemanticOperation.from_dict(op) for op in data.get("operations", [])]
        return cls(
            id=data["id"],
            git_sha=data["git_sha"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data["message"],
            operations=operations,
            reasoning=data.get("reasoning"),
            checkpoint_id=data.get("checkpoint_id"),
        )
