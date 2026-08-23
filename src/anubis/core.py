"""Core business logic for Anubis."""

from pathlib import Path

from .git_wrapper import GitWrapper
from .models import Checkpoint, FileSnapshot, SemanticCommit
from .storage import Storage, init_db, ANUBIS_DIR


class AnubisError(Exception):
    """Base error for Anubis operations."""

    pass


class NotInitializedError(AnubisError):
    """Anubis is not initialized in this repository."""

    pass


class Anubis:
    """Main Anubis interface."""

    def __init__(self, repo_root: Path | None = None):
        if repo_root is None:
            repo_root = GitWrapper.find_repo_root()
            if repo_root is None:
                raise AnubisError("Not in a git repository")

        self.repo_root = repo_root
        self.git = GitWrapper(repo_root)
        self._storage: Storage | None = None

    @property
    def storage(self) -> Storage:
        """Lazy-load storage, ensuring Anubis is initialized."""
        if self._storage is None:
            if not self.is_initialized():
                raise NotInitializedError(
                    f"Anubis not initialized. Run 'anubis init' in {self.repo_root}"
                )
            self._storage = Storage(self.repo_root)
        return self._storage

    def is_initialized(self) -> bool:
        """Check if Anubis is initialized in this repo."""
        return (self.repo_root / ANUBIS_DIR).exists()

    def init(self) -> Path:
        """Initialize Anubis in the current repository."""
        if not self.git.is_valid_repo():
            raise AnubisError("Not a git repository. Run 'git init' first.")

        db_path = init_db(self.repo_root)
        self._storage = Storage(self.repo_root)

        # Add .anubis to .gitignore if not already there
        gitignore = self.repo_root / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            if ANUBIS_DIR not in content:
                with gitignore.open("a") as f:
                    f.write(f"\n# Anubis metadata\n{ANUBIS_DIR}/\n")
        else:
            gitignore.write_text(f"# Anubis metadata\n{ANUBIS_DIR}/\n")

        return db_path

    def checkpoint(
        self,
        message: str,
        reasoning: str | None = None,
        summary: str | None = None,
        stash: bool = True,
        capture_content: bool = True,
        max_files: int = 20,
    ) -> Checkpoint:
        """Create a checkpoint of current work."""
        files_context = self.git.get_changed_files()
        git_ref = self.git.get_current_sha()

        # Capture file snapshots (content + diffs) for changed files
        file_snapshots = []
        if capture_content:
            for filepath in files_context[:max_files]:
                status = self.git.get_file_status(filepath)
                diff = self.git.get_file_diff(filepath)
                content = self.git.get_file_content(filepath) if status != "deleted" else None

                file_snapshots.append(FileSnapshot(
                    path=filepath,
                    content=content,
                    diff=diff,
                    status=status,
                ))

        # Get overall diff
        full_diff = self.git.get_full_diff() if capture_content else None

        # Optionally stash changes to preserve exact state
        stash_ref = None
        if stash and self.git.has_changes():
            stash_ref = self.git.stash_create(f"anubis: {message}")
            if stash_ref:
                git_ref = stash_ref
                # Immediately restore working state
                self.git.stash_pop()

        checkpoint = Checkpoint(
            message=message,
            reasoning=reasoning,
            git_ref=git_ref,
            files_context=files_context,
            file_snapshots=file_snapshots,
            diff=full_diff,
            summary=summary,
        )

        self.storage.save_checkpoint(checkpoint)
        return checkpoint

    def resume(self, checkpoint_id: str) -> Checkpoint:
        """Resume from a checkpoint."""
        checkpoint = self.storage.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise AnubisError(f"Checkpoint not found: {checkpoint_id}")

        # If checkpoint has a stash ref, we could apply it
        # For now, just return the checkpoint info for display
        return checkpoint

    def status(self) -> dict:
        """Get current Anubis status."""
        recent = self.storage.list_checkpoints(limit=5)
        return {
            "repo_root": str(self.repo_root),
            "branch": self.git.get_current_branch(),
            "has_changes": self.git.has_changes(),
            "changed_files": self.git.get_changed_files(),
            "recent_checkpoints": recent,
        }

    def log(self, limit: int = 10) -> list[Checkpoint]:
        """Get checkpoint history."""
        return self.storage.list_checkpoints(limit=limit)

    def commit(
        self,
        message: str,
        reasoning: str | None = None,
        add_all: bool = True,
    ) -> SemanticCommit:
        """Create a semantic commit."""
        git_sha = self.git.commit(message, add_all=add_all)

        commit = SemanticCommit(
            message=message,
            git_sha=git_sha,
            reasoning=reasoning,
        )

        self.storage.save_commit(commit)
        return commit
