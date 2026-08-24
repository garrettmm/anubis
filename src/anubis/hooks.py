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
    automatic checkpoints with Claude's reasoning.
    """
    return '''#!/usr/bin/env python3
"""Claude Code hook for Anubis auto-checkpointing.

Install by adding to your Claude Code hooks configuration:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {"tools": ["Edit", "Write"]},
        "hooks": [{"type": "command", "command": "python3 -m anubis.hooks claude-code-post-tool"}]
      }
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


def handle_claude_code_post_tool() -> None:
    """Handle post-tool-use hook from Claude Code.

    Claude Code passes hook data via stdin as JSON, not environment variables.
    The JSON includes a 'thinking' field with Claude's actual reasoning.
    """
    try:
        # Read JSON from stdin (Claude Code's hook protocol)
        input_json = sys.stdin.read()
        if not input_json.strip():
            return

        hook_data = json.loads(input_json)

        tool_name = hook_data.get("tool_name", "unknown")
        tool_input = hook_data.get("tool_input", {})
        thinking = hook_data.get("thinking", "")

        # Change to the working directory from hook data
        cwd = hook_data.get("cwd")
        if cwd:
            os.chdir(cwd)

        anubis = Anubis()
        if not anubis.is_initialized():
            return

        # Build a meaningful checkpoint message
        if isinstance(tool_input, dict) and "file_path" in tool_input:
            filename = Path(tool_input["file_path"]).name
            message = f"Auto: {tool_name} {filename}"
        elif isinstance(tool_input, dict) and "command" in tool_input:
            cmd = tool_input["command"][:50]
            message = f"Auto: {tool_name} `{cmd}`"
        else:
            message = f"Auto: {tool_name}"

        # Use Claude's thinking as the reasoning (the key fix!)
        reasoning = thinking if thinking else None

        anubis.checkpoint(
            message=message,
            reasoning=reasoning,
            capture_content=True,
            max_files=10,
        )

    except (json.JSONDecodeError, AnubisError, OSError):
        pass  # Silently fail - don't interrupt Claude Code


def setup_claude_code_hooks(repo_root: Path) -> dict[str, Any]:
    """Generate Claude Code hooks configuration.

    Returns a dict that can be merged into .claude/settings.json
    Uses the new matcher-based format required by Claude Code.
    """
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": {"tools": ["Edit", "Write"]},
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{sys.executable} -m anubis.hooks claude-code-post-tool",
                        }
                    ],
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
