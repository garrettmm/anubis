"""Integration hooks for auto-checkpointing with AI coding tools."""

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .core import Anubis, AnubisError
from .semantic import analyze_diff_semantics


def _setup_logger() -> logging.Logger:
    """Set up rotating file logger for hooks."""
    log_dir = Path.home() / ".anubis"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "hook.log"

    logger = logging.getLogger("anubis.hooks")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if function called multiple times
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,  # 1 MB
            backupCount=2,
        )
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = _setup_logger()


class HookConfig:
    """Configuration for Anubis hooks."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.config_path = repo_root / ".anubis" / "hooks.json"

    def load(self) -> dict[str, Any]:
        """Load hook configuration."""
        if not self.config_path.exists():
            return self._default_config()
        try:
            return json.loads(self.config_path.read_text())
        except (json.JSONDecodeError, OSError):
            return self._default_config()

    def save(self, config: dict[str, Any]) -> None:
        """Save hook configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2))

    def _default_config(self) -> dict[str, Any]:
        return {
            "auto_checkpoint": {
                "enabled": False,
                "on_tool_calls": ["Edit", "Write", "Bash"],
                "min_interval_seconds": 60,
                "include_reasoning": True,
            },
            "claude_code": {
                "enabled": False,
            },
        }


def generate_claude_code_hook() -> str:
    """Generate a Claude Code hook script for auto-checkpointing.

    This creates a hook that runs after certain tool calls to create
    automatic checkpoints with Claude's reasoning.
    """
    return '''#!/usr/bin/env python3
"""Claude Code hook for Anubis auto-checkpointing.

Install by adding to your Claude Code hooks configuration:
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Edit", "hooks": [{"type": "command", "command": "python3 -m anubis.hooks claude-code-post-tool"}]},
      {"matcher": "Write", "hooks": [{"type": "command", "command": "python3 -m anubis.hooks claude-code-post-tool"}]}
    ]
  }
}
"""

import json
import os
import sys
from pathlib import Path

def main():
    # Claude Code passes hook data via stdin as JSON
    try:
        input_json = sys.stdin.read()
        if not input_json.strip():
            return

        hook_data = json.loads(input_json)

        tool_name = hook_data.get("tool_name", "unknown")
        tool_input = hook_data.get("tool_input", {})
        thinking = hook_data.get("thinking", "")  # Claude's reasoning!
        cwd = hook_data.get("cwd")

        if cwd:
            os.chdir(cwd)

        from anubis.core import Anubis

        anubis = Anubis()
        if not anubis.is_initialized():
            return

        # Build meaningful message
        if isinstance(tool_input, dict) and "file_path" in tool_input:
            filename = Path(tool_input["file_path"]).name
            message = f"Auto: {tool_name} {filename}"
        else:
            message = f"Auto: {tool_name}"

        # Use Claude's thinking as reasoning
        reasoning = thinking if thinking else None

        anubis.checkpoint(
            message=message,
            reasoning=reasoning,
            capture_content=True,
            max_files=10,
        )

    except Exception:
        pass  # Silently fail

if __name__ == "__main__":
    main()
'''


def _get_old_content(anubis, git_wrapper, filepath: str, status: str) -> str | None:
    """Get old file content for semantic comparison.

    Checks last checkpoint first, then falls back to HEAD.
    This enables incremental change detection.

    Args:
        anubis: Anubis instance for checkpoint access
        git_wrapper: Git operations wrapper
        filepath: Path to file
        status: File status (added, modified, deleted, untracked)

    Returns:
        Old content from last checkpoint or HEAD, or None if file is new
    """
    if status in ("added", "untracked"):
        return None

    # Try to get content from last checkpoint first
    try:
        checkpoints = anubis.storage.list_checkpoints(limit=1)
        if checkpoints:
            last_checkpoint = checkpoints[0]
            # Find this file in last checkpoint's snapshots
            for snapshot in last_checkpoint.file_snapshots:
                if snapshot.path == filepath and snapshot.content:
                    logger.debug(f"Using content from checkpoint {last_checkpoint.id[:8]} for {filepath}")
                    return snapshot.content
    except Exception as e:
        logger.debug(f"Could not retrieve from last checkpoint: {e}")

    # Fallback to HEAD if no checkpoint or file not in checkpoint
    try:
        from git.exc import GitCommandError
        return git_wrapper.repo.git.show(f'HEAD:{filepath}')
    except Exception:
        return None


def _analyze_changed_files(anubis, git_wrapper, changed_files: list[str]) -> list:
    """Run semantic analysis on changed files.

    Args:
        anubis: Anubis instance for checkpoint access
        git_wrapper: Git operations wrapper
        changed_files: List of file paths

    Returns:
        List of semantic operations detected
    """
    file_data = []

    for filepath in changed_files[:10]:  # Limit to first 10 files for performance
        try:
            status = git_wrapper.get_file_status(filepath)
            old_content = _get_old_content(anubis, git_wrapper, filepath, status)
            new_content = git_wrapper.get_file_content(filepath) if status != "deleted" else None

            file_data.append((filepath, old_content, new_content))
        except Exception as e:
            logger.warning(f"Failed to get content for {filepath}: {e}")
            continue

    if not file_data:
        return []

    try:
        return analyze_diff_semantics(file_data)
    except Exception as e:
        logger.error(f"Semantic analysis failed: {e}")
        return []


def _format_semantic_message(tool_name: str, filepath: str | None, operations: list) -> str:
    """Generate checkpoint message from semantic operations.

    Args:
        tool_name: Name of tool that triggered hook
        filepath: Primary file path (if available)
        operations: Semantic operations detected

    Returns:
        Human-readable checkpoint message
    """
    if not operations:
        # Fallback to generic message
        if filepath:
            return f"Auto: {tool_name} {Path(filepath).name}"
        return f"Auto: {tool_name}"

    # Group operations by type
    by_type = {}
    for op in operations:
        by_type.setdefault(op.op_type, []).append(op)

    parts = []

    # Format each operation type
    for op_type in sorted(by_type.keys()):
        ops = by_type[op_type]
        kind = op_type.replace("add_", "").replace("modify_", "").replace("delete_", "")
        names = [op.target.split(":")[-1] for op in ops[:3]]

        if op_type.startswith("add_"):
            plural_kind = f"{kind}es" if kind.endswith("s") else f"{kind}s"
            if len(ops) == 1:
                parts.append(f"Add {kind}: {names[0]}")
            else:
                name_str = ", ".join(names)
                if len(ops) > 3:
                    name_str += f" +{len(ops) - 3} more"
                parts.append(f"Add {len(ops)} {plural_kind}: {name_str}")
        elif op_type.startswith("modify_"):
            if len(ops) == 1:
                parts.append(f"Update {kind}: {names[0]}")
            else:
                parts.append(f"Update {len(ops)} {kind}s")
        elif op_type.startswith("delete_"):
            if len(ops) == 1:
                parts.append(f"Remove {kind}: {names[0]}")
            else:
                parts.append(f"Remove {len(ops)} {kind}s")
        elif op_type == "rename":
            old_name = ops[0].details.get("old_name", "?")
            new_name = ops[0].details.get("new_name", "?")
            parts.append(f"Rename {kind}: {old_name} → {new_name}")

    message = "; ".join(parts[:3])  # Limit to 3 operation types

    # Truncate if too long
    if len(message) > 120:
        message = message[:117] + "..."

    return message


def _generate_reasoning_from_operations(operations: list) -> str | None:
    """Generate reasoning text from semantic operations.

    Args:
        operations: Semantic operations detected

    Returns:
        Human-readable reasoning, or None if no operations
    """
    if not operations:
        return None

    # Group by operation type for better narrative
    by_type = {}
    for op in operations:
        by_type.setdefault(op.op_type, []).append(op)

    sentences = []

    for op_type, ops in by_type.items():
        kind = op_type.replace("add_", "").replace("modify_", "").replace("delete_", "")
        names = [op.target.split(":")[-1] for op in ops[:3]]

        if op_type.startswith("add_"):
            plural_kind = f"{kind}es" if kind.endswith("s") else f"{kind}s"
            if len(ops) == 1:
                sig = ops[0].details.get("signature", "")
                if sig:
                    sentences.append(f"Adding {kind} '{names[0]}': {sig}")
                else:
                    sentences.append(f"Adding {kind} '{names[0]}'")
            else:
                name_list = ", ".join(names)
                if len(ops) > 3:
                    name_list += f" and {len(ops) - 3} more"
                sentences.append(f"Adding {len(ops)} {plural_kind}: {name_list}")

        elif op_type.startswith("modify_"):
            if len(ops) == 1:
                sentences.append(f"Modifying {kind} '{names[0]}'")
                # Include signature change if available
                old_sig = ops[0].details.get("old_signature")
                new_sig = ops[0].details.get("new_signature")
                if old_sig and new_sig:
                    sentences.append(f"Signature changed from '{old_sig}' to '{new_sig}'")
            else:
                sentences.append(f"Updating {len(ops)} {kind}s")

        elif op_type.startswith("delete_"):
            if len(ops) == 1:
                sentences.append(f"Removing {kind} '{names[0]}'")
            else:
                sentences.append(f"Removing {len(ops)} {kind}s: {', '.join(names)}")

        elif op_type == "rename":
            old_name = ops[0].details.get("old_name", "?")
            new_name = ops[0].details.get("new_name", "?")
            sentences.append(f"Renaming {kind} from '{old_name}' to '{new_name}'")

    reasoning = ". ".join(sentences)

    # Truncate if too long
    if len(reasoning) > 500:
        reasoning = reasoning[:497] + "..."

    return reasoning


def handle_claude_code_post_tool() -> None:
    """Handle post-tool-use hook from Claude Code.

    Claude Code passes hook data via stdin as JSON, not environment variables.
    The JSON includes a 'thinking' field with Claude's actual reasoning.
    """
    try:
        # Read JSON from stdin (Claude Code's hook protocol)
        input_json = sys.stdin.read()
        if not input_json.strip():
            logger.info("Empty stdin, skipping hook")
            return

        hook_data = json.loads(input_json)

        tool_name = hook_data.get("tool_name", "unknown")
        tool_input = hook_data.get("tool_input", {})
        thinking = hook_data.get("thinking", "")

        # Log hook invocation
        thinking_length = len(thinking) if thinking else 0
        logger.info(
            f"Tool: {tool_name} | Thinking present: {bool(thinking)} ({thinking_length} chars)"
        )

        # Change to the working directory from hook data
        cwd = hook_data.get("cwd")
        if cwd:
            os.chdir(cwd)
            logger.debug(f"Changed directory to: {cwd}")

        anubis = Anubis()
        if not anubis.is_initialized():
            logger.info("Anubis not initialized, skipping checkpoint")
            return

        # Get changed files for semantic analysis
        changed_files = anubis.git.get_changed_files()

        if not changed_files:
            logger.info("No changed files, skipping checkpoint")
            return

        logger.info(f"Changed files: {len(changed_files)}")

        # Run semantic analysis
        operations = _analyze_changed_files(anubis, anubis.git, changed_files)

        logger.info(f"Semantic analysis: {len(operations)} operations")

        if operations:
            op_types = [op.op_type for op in operations]
            logger.debug(f"Operation types: {', '.join(set(op_types))}")

        # Generate message from semantic operations
        primary_file = None
        if isinstance(tool_input, dict) and "file_path" in tool_input:
            primary_file = tool_input["file_path"]

        message = _format_semantic_message(tool_name, primary_file, operations)
        logger.info(f"Generated message: {message}")

        # Determine reasoning: use thinking if available, otherwise generate from operations
        if thinking and thinking.strip() and len(thinking.strip()) >= 10:
            reasoning = thinking
            logger.info("Using Claude's thinking as reasoning")
        else:
            reasoning = _generate_reasoning_from_operations(operations)
            if reasoning:
                logger.info("Generated reasoning from semantic operations")
            else:
                # Fallback reasoning
                reasoning = f"Automated checkpoint after {tool_name} operation on {len(changed_files)} file(s)."
                logger.info("Using fallback reasoning")

        # Create checkpoint
        checkpoint = anubis.checkpoint(
            message=message,
            reasoning=reasoning,
            capture_content=True,
            max_files=10,
        )

        logger.info(f"Checkpoint created: {checkpoint.id}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hook JSON: {e}")
    except AnubisError as e:
        logger.error(f"Anubis error: {e}")
    except OSError as e:
        logger.error(f"OS error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in hook: {e}")
        # Still fail silently to not interrupt Claude Code


def setup_claude_code_hooks(repo_root: Path) -> dict[str, Any]:
    """Generate Claude Code hooks configuration.

    Returns a dict that can be merged into .claude/settings.json
    Uses the new matcher-based format required by Claude Code.
    """
    command = f"{sys.executable} -m anubis.hooks claude-code-post-tool"
    hook_entry = {"type": "command", "command": command}

    return {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Edit", "hooks": [hook_entry]},
                {"matcher": "Write", "hooks": [hook_entry]},
            ]
        }
    }


def main() -> None:
    """CLI entry point for hooks."""
    if len(sys.argv) < 2:
        print("Usage: python -m anubis.hooks <command>")
        print("Commands:")
        print("  claude-code-post-tool  - Handle Claude Code post-tool hook")
        print("  generate-hook          - Print hook script")
        print("  setup-info             - Print setup instructions")
        sys.exit(1)

    command = sys.argv[1]

    if command == "claude-code-post-tool":
        handle_claude_code_post_tool()
    elif command == "generate-hook":
        print(generate_claude_code_hook())
    elif command == "setup-info":
        print("To enable auto-checkpointing with Claude Code:")
        print()
        print("1. Add to your ~/.claude/settings.json:")
        print(json.dumps(setup_claude_code_hooks(Path.cwd()), indent=2))
        print()
        print("2. Or run: anubis hooks setup")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
