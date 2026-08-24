"""CLI interface for Anubis."""

import json

import click

from .core import Anubis, AnubisError, NotInitializedError


@click.group()
@click.version_option()
def main():
    """Anubis - AI-native version control.

    Semantic commits and reasoning traces on top of git.
    """
    pass


@main.command()
def init():
    """Initialize Anubis in the current git repository."""
    try:
        anubis = Anubis()
        db_path = anubis.init()
        click.echo(f"Initialized Anubis in {anubis.repo_root}")
        click.echo(f"Database: {db_path}")
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--no-mcp", is_flag=True, help="Skip MCP server setup")
@click.option("--no-hooks", is_flag=True, help="Skip hooks setup")
def setup(no_mcp: bool, no_hooks: bool):
    """One-command setup for Claude Code integration.

    This command:
    1. Initializes Anubis if not already initialized
    2. Adds the Anubis MCP server to Claude Code
    3. Installs the post-tool hook for auto-checkpointing

    After running this, Claude Code will have full access to Anubis
    checkpoints and will automatically capture reasoning on file changes.
    """
    import subprocess
    from pathlib import Path

    from .hooks import setup_claude_code_hooks

    try:
        anubis = Anubis()

        # Step 1: Initialize if needed
        if not anubis.is_initialized():
            anubis.init()
            click.echo(f"Initialized Anubis in {anubis.repo_root}")
        else:
            click.echo(f"Anubis already initialized in {anubis.repo_root}")

        # Step 2: Add MCP server to Claude Code
        if not no_mcp:
            click.echo("\nAdding MCP server to Claude Code...")
            try:
                result = subprocess.run(
                    ["claude", "mcp", "add", "anubis", "--", "anubis-mcp"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    click.echo(click.style("  MCP server added", fg="green"))
                else:
                    # May already be added
                    if "already exists" in result.stderr.lower():
                        click.echo("  MCP server already configured")
                    else:
                        click.echo(f"  Note: {result.stderr.strip()}")
            except FileNotFoundError:
                click.echo("  Skipped: 'claude' CLI not found")

        # Step 3: Install hooks
        if not no_hooks:
            click.echo("\nSetting up hooks...")
            settings_path = Path.home() / ".claude" / "settings.json"

            hook_config = setup_claude_code_hooks(anubis.repo_root)

            if settings_path.exists():
                try:
                    settings = json.loads(settings_path.read_text())
                except json.JSONDecodeError:
                    settings = {}
            else:
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                settings = {}

            # Merge hooks config
            if "hooks" not in settings:
                settings["hooks"] = {}

            # Add or update PostToolUse hooks
            post_tool_hooks = settings["hooks"].get("PostToolUse", [])

            # Check if anubis hook already exists
            anubis_hook = hook_config["hooks"]["PostToolUse"][0]
            hook_exists = any(
                "anubis" in h.get("command", "")
                for h in post_tool_hooks
            )

            if not hook_exists:
                post_tool_hooks.append(anubis_hook)
                settings["hooks"]["PostToolUse"] = post_tool_hooks
                settings_path.write_text(json.dumps(settings, indent=2))
                click.echo(click.style("  Hooks installed", fg="green"))
            else:
                click.echo("  Hooks already configured")

        # Done!
        click.echo(f"\n{click.style('Setup complete!', fg='green', bold=True)}")
        click.echo("\nClaude Code can now:")
        click.echo("  - Access checkpoints via MCP (anubis_list_checkpoints, anubis_resume)")
        click.echo("  - Auto-capture reasoning on file changes")
        click.echo("\nTry: anubis log")

    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("message")
@click.option("-r", "--reasoning", help="Explanation of current approach")
@click.option("-s", "--summary", help="Context summary for later resume")
def checkpoint(message: str, reasoning: str | None, summary: str | None):
    """Create a checkpoint with optional reasoning.

    MESSAGE is a short description of current work.
    """
    try:
        anubis = Anubis()
        cp = anubis.checkpoint(message, reasoning=reasoning, summary=summary)

        click.echo(f"Checkpoint created: {cp.id}")
        click.echo(f"  Message: {cp.message}")
        if cp.reasoning:
            click.echo(f"  Reasoning: {cp.reasoning}")
        if cp.files_context:
            click.echo(f"  Files: {', '.join(cp.files_context[:5])}")
            if len(cp.files_context) > 5:
                click.echo(f"         ... and {len(cp.files_context) - 5} more")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
def status():
    """Show current Anubis status."""
    try:
        anubis = Anubis()
        st = anubis.status()

        click.echo(f"Repository: {st['repo_root']}")
        click.echo(f"Branch: {st['branch'] or '(detached)'}")
        click.echo(f"Changes: {'yes' if st['has_changes'] else 'no'}")

        if st["changed_files"]:
            click.echo("\nChanged files:")
            for f in st["changed_files"][:10]:
                click.echo(f"  {f}")
            if len(st["changed_files"]) > 10:
                click.echo(f"  ... and {len(st['changed_files']) - 10} more")

        if st["recent_checkpoints"]:
            click.echo("\nRecent checkpoints:")
            for cp in st["recent_checkpoints"]:
                ts = cp.timestamp.strftime("%Y-%m-%d %H:%M")
                click.echo(f"  {cp.id} ({ts}): {cp.message}")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("-n", "--limit", default=10, help="Number of entries to show")
def log(limit: int):
    """Show checkpoint history."""
    try:
        anubis = Anubis()
        checkpoints = anubis.log(limit=limit)

        if not checkpoints:
            click.echo("No checkpoints yet.")
            return

        for cp in checkpoints:
            ts = cp.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            click.echo(f"\n{click.style(cp.id, fg='yellow')} - {ts}")
            click.echo(f"  {cp.message}")
            if cp.reasoning:
                click.echo(f"  Reasoning: {click.style(cp.reasoning, dim=True)}")
            if cp.files_context:
                files = ", ".join(cp.files_context[:3])
                if len(cp.files_context) > 3:
                    files += f" +{len(cp.files_context) - 3} more"
                click.echo(f"  Files: {files}")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("checkpoint_id")
@click.option(
    "-f", "--format",
    type=click.Choice(["human", "json", "prompt"]),
    default="human",
    help="Output format: human (default), json, or prompt (AI-optimized)"
)
def resume(checkpoint_id: str, format: str):
    """Show checkpoint details for resuming work.

    CHECKPOINT_ID can be a prefix (e.g., 'abc' matches 'abc123def').

    Use --format=prompt to get AI-optimized output for injecting into prompts.
    Use --format=json for machine-readable output.
    """
    try:
        anubis = Anubis()
        cp = anubis.resume(checkpoint_id)

        if format == "json":
            click.echo(json.dumps(cp.to_dict(), indent=2))
            return

        if format == "prompt":
            click.echo(cp.to_prompt())
            return

        # Human-readable format
        click.echo(f"Checkpoint: {cp.id}")
        click.echo(f"Created: {cp.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Message: {cp.message}")

        if cp.reasoning:
            click.echo("\nReasoning:")
            click.echo(f"  {cp.reasoning}")

        if cp.summary:
            click.echo("\nContext Summary:")
            click.echo(f"  {cp.summary}")

        if cp.file_snapshots:
            click.echo(f"\nFile snapshots ({len(cp.file_snapshots)} files):")
            for snap in cp.file_snapshots[:10]:
                status_color = {
                    "added": "green",
                    "modified": "yellow",
                    "deleted": "red",
                    "untracked": "cyan",
                }.get(snap.status, None)
                click.echo(f"  {click.style(snap.status, fg=status_color)}: {snap.path}")
            if len(cp.file_snapshots) > 10:
                click.echo(f"  ... and {len(cp.file_snapshots) - 10} more")
        elif cp.files_context:
            click.echo("\nFiles in context:")
            for f in cp.files_context[:15]:
                click.echo(f"  {f}")
            if len(cp.files_context) > 15:
                click.echo(f"  ... and {len(cp.files_context) - 15} more")

        if cp.git_ref:
            click.echo(f"\nGit ref: {cp.git_ref}")

        # Hint about prompt format
        click.echo(f"\n{click.style('Tip:', dim=True)} Use --format=prompt for AI-friendly output")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command("commit")
@click.argument("message")
@click.option("-r", "--reasoning", help="Explanation of why these changes were made")
@click.option("--no-add", is_flag=True, help="Don't automatically add all changes")
def semantic_commit(message: str, reasoning: str | None, no_add: bool):
    """Create a semantic commit (wraps git commit).

    MESSAGE is the commit message.
    """
    try:
        anubis = Anubis()
        commit = anubis.commit(message, reasoning=reasoning, add_all=not no_add)

        click.echo(f"Committed: {commit.git_sha[:8]}")
        click.echo(f"  {commit.message}")
        if commit.reasoning:
            click.echo(f"  Reasoning: {commit.reasoning}")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.group()
def hooks():
    """Manage integration hooks for auto-checkpointing."""
    pass


@hooks.command("setup")
@click.option("--print-only", is_flag=True, help="Print config without installing")
def hooks_setup(print_only: bool):
    """Set up Claude Code integration hooks."""
    from .hooks import setup_claude_code_hooks

    try:
        anubis = Anubis()
        if not anubis.is_initialized():
            click.echo("Error: Anubis not initialized. Run 'anubis init' first.", err=True)
            raise SystemExit(1)

        config = setup_claude_code_hooks(anubis.repo_root)

        if print_only:
            click.echo("Add this to your Claude Code settings (~/.claude/settings.json):")
            click.echo()
            click.echo(json.dumps(config, indent=2))
        else:
            click.echo("Claude Code hook configuration:")
            click.echo(json.dumps(config, indent=2))
            click.echo()
            click.echo("To enable, add the above to ~/.claude/settings.json")
            click.echo("Or use: anubis hooks setup --print-only | pbcopy")

    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@hooks.command("test")
def hooks_test():
    """Test hook by creating an auto-checkpoint."""
    import os

    try:
        # Simulate a tool call
        os.environ["CLAUDE_TOOL_NAME"] = "test"
        os.environ["CLAUDE_TOOL_INPUT"] = json.dumps({"test": True})

        anubis = Anubis()
        if not anubis.is_initialized():
            click.echo("Error: Anubis not initialized.", err=True)
            raise SystemExit(1)

        cp = anubis.checkpoint(
            message="Hook test checkpoint",
            reasoning="Testing hook integration",
        )
        click.echo(f"Test checkpoint created: {cp.id}")

    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command("analyze")
@click.argument("checkpoint_id", required=False)
def analyze(checkpoint_id: str | None):
    """Analyze semantic changes in checkpoint or working tree."""
    from .semantic import detect_semantic_operations

    try:
        anubis = Anubis()

        if checkpoint_id:
            cp = anubis.resume(checkpoint_id)
            snapshots = cp.file_snapshots
        else:
            # Analyze current working tree
            from .models import FileSnapshot
            files = anubis.git.get_changed_files()
            snapshots = []
            for f in files[:20]:
                snapshots.append(FileSnapshot(
                    path=f,
                    content=anubis.git.get_file_content(f),
                    diff=anubis.git.get_file_diff(f),
                    status=anubis.git.get_file_status(f),
                ))

        if not snapshots:
            click.echo("No changes to analyze.")
            return

        click.echo("Semantic analysis:")
        click.echo()

        for snap in snapshots:
            # For now, just show file-level operations
            # Full semantic analysis would compare old vs new content
            ops = detect_semantic_operations(
                snap.path,
                None,  # Would need old content from git
                snap.content,
            )

            if ops:
                click.echo(f"{snap.path}:")
                for op in ops:
                    click.echo(f"  {click.style(op.op_type, fg='cyan')}: {op.target}")
                    if op.details.get("signature"):
                        click.echo(f"    {click.style(op.details['signature'], dim=True)}")

        if not any(snap for snap in snapshots):
            click.echo("No semantic operations detected.")

    except NotInitializedError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except AnubisError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
