"""Data models for Anubis."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class FileSnapshot:
    """Snapshot of a file's content at checkpoint time."""

    path: str
    content: str | None  # None if binary or too large
    diff: str | None  # diff from last commit
    status: str  # "added", "modified", "deleted", "untracked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "diff": self.diff,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileSnapshot":
        return cls(
            path=data["path"],
            content=data.get("content"),
            diff=data.get("diff"),
            status=data.get("status", "modified"),
        )


@dataclass
class Checkpoint:
    """A lightweight snapshot of work-in-progress with reasoning context."""

    message: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning: str | None = None
    git_ref: str | None = None  # commit sha or stash ref
    files_context: list[str] = field(default_factory=list)
    file_snapshots: list[FileSnapshot] = field(default_factory=list)
    diff: str | None = None  # overall diff summary
    summary: str | None = None  # context summary for resume

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "reasoning": self.reasoning,
            "git_ref": self.git_ref,
            "files_context": self.files_context,
            "file_snapshots": [f.to_dict() for f in self.file_snapshots],
            "diff": self.diff,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        snapshots = [FileSnapshot.from_dict(s) for s in data.get("file_snapshots", [])]
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data["message"],
            reasoning=data.get("reasoning"),
            git_ref=data.get("git_ref"),
            files_context=data.get("files_context", []),
            file_snapshots=snapshots,
            diff=data.get("diff"),
            summary=data.get("summary"),
        )

    def to_prompt(self) -> str:
        """Format checkpoint for AI prompt injection."""
        lines = [
            f"# Checkpoint: {self.id}",
            f"**Message:** {self.message}",
            f"**Created:** {self.timestamp.isoformat()}",
        ]

        if self.reasoning:
            lines.append(f"\n## Reasoning\n{self.reasoning}")

        if self.summary:
            lines.append(f"\n## Context Summary\n{self.summary}")

        if self.file_snapshots:
            lines.append("\n## Changed Files")
            for snap in self.file_snapshots:
                lines.append(f"\n### {snap.path} ({snap.status})")
                if snap.diff:
                    lines.append(f"```diff\n{snap.diff}\n```")
                elif snap.content and len(snap.content) < 5000:
                    ext = snap.path.split(".")[-1] if "." in snap.path else ""
                    lines.append(f"```{ext}\n{snap.content}\n```")
        elif self.files_context:
            lines.append(f"\n## Files in Context\n" + "\n".join(f"- {f}" for f in self.files_context))

        if self.diff and not self.file_snapshots:
            lines.append(f"\n## Diff Summary\n```\n{self.diff}\n```")

        return "\n".join(lines)


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
