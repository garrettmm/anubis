"""CLI interface for Anubis."""

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
def resume(checkpoint_id: str):
    """Show checkpoint details for resuming work.

    CHECKPOINT_ID can be a prefix (e.g., 'abc' matches 'abc123def').
    """
    try:
        anubis = Anubis()
        cp = anubis.resume(checkpoint_id)

        click.echo(f"Checkpoint: {cp.id}")
        click.echo(f"Created: {cp.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Message: {cp.message}")

        if cp.reasoning:
            click.echo(f"\nReasoning:")
            click.echo(f"  {cp.reasoning}")

        if cp.summary:
            click.echo(f"\nContext Summary:")
            click.echo(f"  {cp.summary}")

        if cp.files_context:
            click.echo(f"\nFiles in context:")
            for f in cp.files_context:
                click.echo(f"  {f}")

        if cp.git_ref:
            click.echo(f"\nGit ref: {cp.git_ref}")

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


if __name__ == "__main__":
    main()
