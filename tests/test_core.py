"""Tests for Anubis core functionality."""

import tempfile
from pathlib import Path

import pytest

from anubis.core import Anubis, AnubisError, NotInitializedError
from anubis.git_wrapper import GitWrapper


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        GitWrapper.init_repo(repo_path)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo")
        git = GitWrapper(repo_path)
        git.commit("Initial commit", add_all=True)

        yield repo_path


def test_init_creates_anubis_dir(temp_git_repo):
    """Test that init creates .anubis directory."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    assert (temp_git_repo / ".anubis").exists()
    assert (temp_git_repo / ".anubis" / "anubis.db").exists()


def test_init_adds_to_gitignore(temp_git_repo):
    """Test that init adds .anubis to .gitignore."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    gitignore = temp_git_repo / ".gitignore"
    assert gitignore.exists()
    assert ".anubis" in gitignore.read_text()


def test_checkpoint_saves_and_retrieves(temp_git_repo):
    """Test creating and retrieving checkpoints."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    # Create a file change
    (temp_git_repo / "test.py").write_text("print('hello')")

    cp = anubis.checkpoint(
        "Working on feature X",
        reasoning="Trying approach A",
        summary="Context summary here",
    )

    assert cp.id is not None
    assert cp.message == "Working on feature X"
    assert cp.reasoning == "Trying approach A"
    assert "test.py" in cp.files_context

    # Retrieve it
    retrieved = anubis.resume(cp.id)
    assert retrieved.message == cp.message
    assert retrieved.reasoning == cp.reasoning


def test_checkpoint_prefix_match(temp_git_repo):
    """Test that checkpoint lookup works with ID prefix."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    cp = anubis.checkpoint("Test checkpoint")

    # Should work with first 4 chars
    retrieved = anubis.resume(cp.id[:4])
    assert retrieved.id == cp.id


def test_log_returns_checkpoints(temp_git_repo):
    """Test that log returns checkpoints in order."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    anubis.checkpoint("First")
    anubis.checkpoint("Second")
    anubis.checkpoint("Third")

    log = anubis.log(limit=10)
    assert len(log) == 3
    assert log[0].message == "Third"  # Most recent first
    assert log[2].message == "First"


def test_not_initialized_error(temp_git_repo):
    """Test that operations fail if not initialized."""
    anubis = Anubis(temp_git_repo)

    with pytest.raises(NotInitializedError):
        anubis.checkpoint("Test")


def test_status_includes_recent_checkpoints(temp_git_repo):
    """Test that status includes recent checkpoints."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    anubis.checkpoint("Checkpoint 1")
    anubis.checkpoint("Checkpoint 2")

    status = anubis.status()
    assert len(status["recent_checkpoints"]) == 2


def test_checkpoint_captures_file_snapshots(temp_git_repo):
    """Test that checkpoints capture file content and diffs."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    # Create a Python file
    test_file = temp_git_repo / "app.py"
    test_file.write_text("def hello():\n    print('hello')\n")

    cp = anubis.checkpoint("Adding hello function", capture_content=True)

    assert len(cp.file_snapshots) > 0
    snapshot = next((s for s in cp.file_snapshots if s.path == "app.py"), None)
    assert snapshot is not None
    assert snapshot.status == "untracked"
    assert "def hello" in (snapshot.content or "")


def test_checkpoint_to_prompt_format(temp_git_repo):
    """Test that checkpoints can be formatted for AI prompts."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    (temp_git_repo / "test.py").write_text("x = 1")

    cp = anubis.checkpoint(
        "Test message",
        reasoning="Test reasoning",
        summary="Test summary",
    )

    prompt = cp.to_prompt()

    assert "# Checkpoint:" in prompt
    assert "Test message" in prompt
    assert "Test reasoning" in prompt
    assert "Test summary" in prompt


def test_checkpoint_to_dict_includes_snapshots(temp_git_repo):
    """Test that to_dict includes file snapshots."""
    anubis = Anubis(temp_git_repo)
    anubis.init()

    (temp_git_repo / "test.py").write_text("x = 1")
    cp = anubis.checkpoint("Test")

    data = cp.to_dict()

    assert "file_snapshots" in data
    assert "diff" in data
    assert isinstance(data["file_snapshots"], list)
