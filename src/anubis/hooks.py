"""Integration hooks for auto-checkpointing with AI coding tools."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from .core import Anubis, AnubisError


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
    automatic checkpoints.
    """
    return '''#!/usr/bin/env python3
"""Claude Code hook for Anubis auto-checkpointing.

Install by adding to your Claude Code hooks configuration:
{
  "hooks": {
    "PostToolUse": [
      {
        "command": "python3 -m anubis.hooks claude-code-post-tool",
        "tools": ["Edit", "Write", "Bash"]
      }
    ]
  }
}
"""

import json
import os
import sys
from datetime import datetime, timezone

def main():
    # Read tool use info from environment or stdin
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "unknown")
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "{}")

    try:
        from anubis.core import Anubis

        anubis = Anubis()
        if not anubis.is_initialized():
            return

        # Create auto-checkpoint
        message = f"Auto: after {tool_name}"

        # Extract reasoning from tool input if available
        reasoning = None
        try:
            input_data = json.loads(tool_input)
            if "file_path" in input_data:
                reasoning = f"Modified {input_data['file_path']}"
            elif "command" in input_data:
                cmd = input_data["command"][:100]
                reasoning = f"Ran: {cmd}"
        except (json.JSONDecodeError, KeyError):
            pass

        anubis.checkpoint(
            message=message,
            reasoning=reasoning,
            capture_content=True,
            max_files=10,
        )

    except Exception as e:
        # Silently fail - don't interrupt Claude Code
        pass

if __name__ == "__main__":
    main()
'''


def handle_claude_code_post_tool() -> None:
    """Handle post-tool-use hook from Claude Code."""
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "unknown")
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "{}")

    try:
        anubis = Anubis()
        if not anubis.is_initialized():
            return

        # Create auto-checkpoint
        message = f"Auto: after {tool_name}"

        # Extract reasoning from tool input if available
        reasoning = None
        try:
            input_data = json.loads(tool_input)
            if "file_path" in input_data:
                reasoning = f"Modified {input_data['file_path']}"
            elif "command" in input_data:
                cmd = input_data["command"][:100]
                reasoning = f"Ran: {cmd}"
        except (json.JSONDecodeError, KeyError):
            pass

        anubis.checkpoint(
            message=message,
            reasoning=reasoning,
            capture_content=True,
            max_files=10,
        )

    except AnubisError:
        pass  # Silently fail


def setup_claude_code_hooks(repo_root: Path) -> dict[str, Any]:
    """Generate Claude Code hooks configuration.

    Returns a dict that can be merged into .claude/settings.json
    """
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "command": f"{sys.executable} -m anubis.hooks claude-code-post-tool",
                    "tools": ["Edit", "Write"],
                }
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
