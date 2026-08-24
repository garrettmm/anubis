# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Anubis is an AI-native version control system that wraps git and adds semantic understanding and reasoning traces. It's designed to help AI coding assistants (like Claude) preserve context across sessions through checkpoints that capture not just code state, but the reasoning behind changes.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check src/

# CLI usage
anubis init                              # Initialize in a git repo
anubis checkpoint "message"              # Create checkpoint
anubis checkpoint "msg" -r "reasoning"   # With reasoning trace
anubis status                            # Show state + recent checkpoints
anubis log                               # Show checkpoint history
anubis resume <id>                       # View checkpoint details
anubis resume <id> --format=prompt       # AI-optimized output for context injection
anubis resume <id> --format=json         # Machine-readable output
anubis commit "message"                  # Semantic commit (wraps git)
anubis analyze                           # Semantic analysis of current changes
anubis analyze <checkpoint-id>           # Analyze specific checkpoint
anubis hooks setup                       # Generate Claude Code hook config
```

## Architecture

```
src/anubis/
├── cli.py          # Click CLI entry point
├── core.py         # Anubis class - main business logic
├── storage.py      # SQLite persistence for checkpoints/commits
├── git_wrapper.py  # GitPython wrapper for git operations
├── models.py       # Dataclasses: Checkpoint, FileSnapshot, SemanticCommit
├── semantic.py     # AST-based semantic diff detection (Python, JS/TS)
├── hooks.py        # Integration hooks for Claude Code auto-checkpointing
└── mcp_server.py   # MCP server for Claude Code native integration
```

**Data flow:** CLI (`cli.py`) → Core (`core.py`) → Storage (`storage.py`) + Git (`git_wrapper.py`)

**Storage:** Metadata stored in `.anubis/anubis.db` (SQLite), separate from git. The `.anubis` directory is gitignored.

## Key Concepts

- **Checkpoint**: Snapshot with message, reasoning, file snapshots (content + diffs), and context summary. Supports `to_prompt()` for AI-friendly formatting.
- **FileSnapshot**: Captures file content, diff, and status (added/modified/deleted/untracked) at checkpoint time.
- **SemanticCommit**: Git commit enriched with semantic operations and reasoning.
- **SemanticOperation**: Detected code changes like `add_function`, `delete_class`, `rename`, `modify_function`.

## When working on this codebase

- The `Anubis` class in `core.py` is the main entry point for all operations
- Checkpoints use prefix matching for IDs (e.g., `abc` matches `abc123def`)
- Git operations go through `GitWrapper` to keep git logic isolated
- All models have `to_dict()`/`from_dict()` for SQLite JSON serialization
- `Checkpoint.to_prompt()` formats checkpoint data for AI context injection
- Semantic analysis in `semantic.py` uses Python AST and regex for JS/TS
- Database migrations handled in `storage._migrate_db()` - bump `SCHEMA_VERSION` for schema changes

## MCP Server

The MCP server (`mcp_server.py`) enables Claude Code to access Anubis natively without copy/paste.

**Tools exposed:**
- `anubis_list_checkpoints` - List recent checkpoints
- `anubis_resume` - Get checkpoint context in prompt format
- `anubis_checkpoint` - Create a new checkpoint
- `anubis_status` - Get repo status and recent checkpoints
- `anubis_analyze` - Run semantic analysis on current changes

**Resources:**
- `anubis://status` - Current status
- `anubis://checkpoints` - All checkpoints
- `anubis://checkpoint/{id}` - Individual checkpoint details

**Setup:** `claude mcp add anubis -- anubis-mcp`
