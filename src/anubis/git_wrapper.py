"""Git operations wrapper for Anubis."""

from pathlib import Path

from git import InvalidGitRepositoryError, Repo
from git.exc import GitCommandError


class GitError(Exception):
    """Git operation error."""

    pass


class GitWrapper:
    """Wrapper around git operations."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Lazy-load the git repo."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_root)
            except InvalidGitRepositoryError:
                raise GitError(f"Not a git repository: {self.repo_root}")
        return self._repo

    @classmethod
    def find_repo_root(cls, start_path: Path | None = None) -> Path | None:
        """Find the root of the git repository containing start_path."""
        if start_path is None:
            start_path = Path.cwd()

        current = start_path.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent

        if (current / ".git").exists():
            return current
        return None

    @classmethod
    def init_repo(cls, path: Path) -> "GitWrapper":
        """Initialize a new git repository."""
        Repo.init(path)
        return cls(path)

    def is_valid_repo(self) -> bool:
        """Check if this is a valid git repository."""
        try:
            _ = self.repo
            return True
        except GitError:
            return False

    def get_current_sha(self) -> str | None:
        """Get the current HEAD commit SHA."""
        try:
            return self.repo.head.commit.hexsha
        except (ValueError, TypeError):
            # No commits yet
            return None

    def get_current_branch(self) -> str | None:
        """Get the current branch name."""
        try:
            return self.repo.active_branch.name
        except TypeError:
            # Detached HEAD
            return None

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)

    def get_changed_files(self) -> list[str]:
        """Get list of changed files (staged + unstaged + untracked)."""
        changed = []

        # Staged changes
        if self.repo.head.is_valid():
            for diff in self.repo.index.diff(self.repo.head.commit):
                changed.append(diff.a_path or diff.b_path)

        # Unstaged changes
        for diff in self.repo.index.diff(None):
            path = diff.a_path or diff.b_path
            if path not in changed:
                changed.append(path)

        # Untracked files
        for path in self.repo.untracked_files:
            if path not in changed:
                changed.append(path)

        return changed

    def stash_create(self, message: str) -> str | None:
        """Create a stash and return its ref. Returns None if nothing to stash."""
        if not self.has_changes():
            return None

        try:
            # Include untracked files in stash
            self.repo.git.stash("push", "-u", "-m", message)
            # Get the stash ref
            return self.repo.git.rev_parse("stash@{0}")
        except GitCommandError:
            return None

    def stash_pop(self) -> bool:
        """Pop the most recent stash."""
        try:
            self.repo.git.stash("pop")
            return True
        except GitCommandError:
            return False

    def stash_apply(self, stash_ref: str) -> bool:
        """Apply a specific stash by ref."""
        try:
            self.repo.git.stash("apply", stash_ref)
            return True
        except GitCommandError:
            return False

    def checkout(self, ref: str) -> bool:
        """Checkout a specific ref (branch, tag, or commit)."""
        try:
            self.repo.git.checkout(ref)
            return True
        except GitCommandError:
            return False

    def commit(self, message: str, add_all: bool = False) -> str:
        """Create a commit and return its SHA."""
        if add_all:
            self.repo.git.add("-A")

        self.repo.index.commit(message)
        return self.repo.head.commit.hexsha

    def get_diff_summary(self, ref1: str | None = None, ref2: str | None = None) -> str:
        """Get a summary of changes between refs (or working tree if None)."""
        try:
            if ref1 and ref2:
                return self.repo.git.diff("--stat", ref1, ref2)
            elif ref1:
                return self.repo.git.diff("--stat", ref1)
            else:
                return self.repo.git.diff("--stat")
        except GitCommandError:
            return ""

    def get_file_diff(self, filepath: str) -> str | None:
        """Get the diff for a specific file."""
        try:
            # Try staged diff first, then unstaged
            diff = self.repo.git.diff("--cached", "--", filepath)
            if not diff:
                diff = self.repo.git.diff("--", filepath)
            return diff if diff else None
        except GitCommandError:
            return None

    def get_full_diff(self) -> str:
        """Get full diff of all changes (staged + unstaged)."""
        try:
            # Combine staged and unstaged diffs
            staged = self.repo.git.diff("--cached")
            unstaged = self.repo.git.diff()
            parts = []
            if staged:
                parts.append(staged)
            if unstaged:
                parts.append(unstaged)
            return "\n".join(parts)
        except GitCommandError:
            return ""

    def get_file_content(self, filepath: str, max_size: int = 100000) -> str | None:
        """Read file content, returning None if binary or too large."""
        full_path = self.repo_root / filepath
        if not full_path.exists():
            return None

        try:
            size = full_path.stat().st_size
            if size > max_size:
                return None

            content = full_path.read_text(encoding="utf-8")
            return content
        except (UnicodeDecodeError, OSError):
            return None  # Binary or unreadable

    def get_file_status(self, filepath: str) -> str:
        """Get the status of a file: added, modified, deleted, untracked."""
        if filepath in self.repo.untracked_files:
            return "untracked"

        try:
            # Check if file is staged
            if self.repo.head.is_valid():
                for diff in self.repo.index.diff(self.repo.head.commit):
                    if diff.a_path == filepath or diff.b_path == filepath:
                        if diff.new_file:
                            return "added"
                        elif diff.deleted_file:
                            return "deleted"
                        return "modified"

            # Check unstaged changes
            for diff in self.repo.index.diff(None):
                if diff.a_path == filepath or diff.b_path == filepath:
                    if diff.deleted_file:
                        return "deleted"
                    return "modified"

            return "modified"
        except Exception:
            return "unknown"
