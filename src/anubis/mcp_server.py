"""MCP server for Anubis - exposes checkpoints to Claude Code."""

from fastmcp import FastMCP

from .core import Anubis, AnubisError, NotInitializedError
from .semantic import analyze_diff_semantics

# Create MCP server
mcp = FastMCP("anubis")


def _get_anubis() -> Anubis:
    """Get Anubis instance for current directory."""
    return Anubis()


def _format_checkpoint_list(checkpoints: list) -> str:
    """Format checkpoints for display."""
    if not checkpoints:
        return "No checkpoints found."

    lines = []
    for cp in checkpoints:
        time_str = cp.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"- **{cp.id}** ({time_str}): {cp.message}")
        if cp.reasoning:
            lines.append(f"  Reasoning: {cp.reasoning}")
    return "\n".join(lines)


# ============================================================================
# Tools
# ============================================================================


@mcp.tool()
def anubis_list_checkpoints(limit: int = 10) -> str:
    """List recent Anubis checkpoints.

    Args:
        limit: Maximum number of checkpoints to return (default 10)

    Returns:
        Formatted list of checkpoints with IDs, messages, and reasoning
    """
    try:
        anubis = _get_anubis()
        checkpoints = anubis.log(limit=limit)
        return _format_checkpoint_list(checkpoints)
    except NotInitializedError:
        return "Anubis not initialized. Run 'anubis init' first."
    except AnubisError as e:
        return f"Error: {e}"


@mcp.tool()
def anubis_resume(checkpoint_id: str) -> str:
    """Get full checkpoint context for resuming work.

    Returns the checkpoint in AI-optimized format with reasoning,
    changed files, and diffs - ready for context injection.

    Args:
        checkpoint_id: The checkpoint ID (or prefix) to resume from

    Returns:
        Markdown-formatted checkpoint context for AI consumption
    """
    try:
        anubis = _get_anubis()
        checkpoint = anubis.resume(checkpoint_id)
        return checkpoint.to_prompt()
    except NotInitializedError:
        return "Anubis not initialized. Run 'anubis init' first."
    except AnubisError as e:
        return f"Error: {e}"


@mcp.tool()
def anubis_checkpoint(message: str, reasoning: str | None = None) -> str:
    """Create a new checkpoint with optional reasoning.

    Captures the current state of changed files along with
    the reasoning behind the changes.

    Args:
        message: Short description of the checkpoint
        reasoning: Explanation of why these changes were made

    Returns:
        Confirmation with the new checkpoint ID
    """
    try:
        anubis = _get_anubis()
        checkpoint = anubis.checkpoint(message=message, reasoning=reasoning)
        result = f"Checkpoint created: {checkpoint.id}\n"
        result += f"  Message: {checkpoint.message}\n"
        if checkpoint.reasoning:
            result += f"  Reasoning: {checkpoint.reasoning}\n"
        if checkpoint.files_context:
            result += f"  Files: {', '.join(checkpoint.files_context[:5])}"
            if len(checkpoint.files_context) > 5:
                result += f" (+{len(checkpoint.files_context) - 5} more)"
        return result
    except NotInitializedError:
        return "Anubis not initialized. Run 'anubis init' first."
    except AnubisError as e:
        return f"Error: {e}"


@mcp.tool()
def anubis_status() -> str:
    """Get current Anubis status including repo state and recent checkpoints.

    Returns:
        Current branch, changed files, and recent checkpoint summaries
    """
    try:
        anubis = _get_anubis()
        status = anubis.status()

        lines = [
            f"**Repository:** {status['repo_root']}",
            f"**Branch:** {status['branch']}",
            f"**Has changes:** {'Yes' if status['has_changes'] else 'No'}",
        ]

        if status["changed_files"]:
            lines.append(f"\n**Changed files:** {', '.join(status['changed_files'][:10])}")
            if len(status["changed_files"]) > 10:
                lines.append(f"  (+{len(status['changed_files']) - 10} more)")

        if status["recent_checkpoints"]:
            lines.append("\n**Recent checkpoints:**")
            lines.append(_format_checkpoint_list(status["recent_checkpoints"]))

        return "\n".join(lines)
    except NotInitializedError:
        return "Anubis not initialized. Run 'anubis init' first."
    except AnubisError as e:
        return f"Error: {e}"


@mcp.tool()
def anubis_analyze() -> str:
    """Run semantic analysis on current changes.

    Detects added/removed/modified functions, classes, and other
    code symbols in changed files.

    Returns:
        List of semantic operations detected in current changes
    """
    try:
        anubis = _get_anubis()
        changed_files = anubis.git.get_changed_files()

        if not changed_files:
            return "No changes to analyze."

        # Collect file contents for analysis
        file_data = []
        for filepath in changed_files:
            status = anubis.git.get_file_status(filepath)
            if status == "added":
                old_content = None
                new_content = anubis.git.get_file_content(filepath)
            elif status == "deleted":
                old_content = anubis.git.get_staged_content(filepath)
                new_content = None
            else:
                old_content = anubis.git.get_staged_content(filepath)
                new_content = anubis.git.get_file_content(filepath)

            file_data.append((filepath, old_content, new_content))

        operations = analyze_diff_semantics(file_data)

        if not operations:
            return "No semantic changes detected (changes may be in non-code files)."

        lines = ["**Semantic changes detected:**\n"]
        for op in operations:
            lines.append(f"- {op.op_type}: `{op.target}`")
            if op.details:
                if "signature" in op.details:
                    lines.append(f"  Signature: `{op.details['signature']}`")
                if "old_name" in op.details and "new_name" in op.details:
                    lines.append(
                        f"  Renamed: `{op.details['old_name']}` -> `{op.details['new_name']}`"
                    )

        return "\n".join(lines)
    except NotInitializedError:
        return "Anubis not initialized. Run 'anubis init' first."
    except AnubisError as e:
        return f"Error: {e}"


@mcp.tool()
def anubis_setup() -> str:
    """Initialize Anubis in the current project.

    Sets up Anubis for the current git repository. Run this when
    starting work on a new project that doesn't have Anubis configured.

    Returns:
        Setup status and next steps
    """
    try:
        anubis = _get_anubis()

        if anubis.is_initialized():
            return "Anubis is already initialized in this repository."

        db_path = anubis.init()
        return f"""Anubis initialized successfully!

Database: {db_path}

You can now:
- Create checkpoints: anubis_checkpoint("message", "reasoning")
- List checkpoints: anubis_list_checkpoints()
- Resume from checkpoint: anubis_resume("checkpoint_id")

Auto-checkpointing is enabled - I'll capture reasoning on file changes."""

    except AnubisError as e:
        return f"Error: {e}"


# ============================================================================
# Resources
# ============================================================================


@mcp.resource("anubis://status")
def resource_status() -> str:
    """Current Anubis status."""
    return anubis_status()


@mcp.resource("anubis://checkpoints")
def resource_checkpoints() -> str:
    """List of all checkpoints."""
    return anubis_list_checkpoints(limit=50)


@mcp.resource("anubis://checkpoint/{checkpoint_id}")
def resource_checkpoint(checkpoint_id: str) -> str:
    """Individual checkpoint details."""
    return anubis_resume(checkpoint_id)


# ============================================================================
# Prompts
# ============================================================================


@mcp.prompt()
def resume_session(checkpoint_id: str) -> str:
    """Generate a prompt for resuming from a checkpoint.

    Args:
        checkpoint_id: The checkpoint ID to resume from
    """
    try:
        anubis = _get_anubis()
        checkpoint = anubis.resume(checkpoint_id)
        return f"""I'm resuming work from a previous session. Here's the context:

{checkpoint.to_prompt()}

Please review this context and help me continue where I left off."""
    except Exception as e:
        return f"Error loading checkpoint: {e}"


# ============================================================================
# Entry point
# ============================================================================


def main():
    """Run the Anubis MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
