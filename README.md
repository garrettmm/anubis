# Anubis

**AI-native version control.** Semantic commits and reasoning traces on top of git.

Anubis helps AI coding assistants (Claude, Cursor, Copilot) preserve context across sessions. Create checkpoints that capture not just code state, but *why* changes were made.

## The Problem

When working with AI coding assistants:
- Sessions end and context is lost
- You can't resume exactly where you left off
- There's no record of the reasoning behind changes
- Code review lacks the "why"

## The Solution

Anubis wraps git and adds:
- **Checkpoints** with reasoning traces ("I'm trying approach A because...")
- **File snapshots** capturing content and diffs at each checkpoint
- **Semantic analysis** detecting what changed (added function, renamed class)
- **AI-friendly output** for injecting context into new sessions

## Installation

```bash
pip install anubis-vcs
```

Requires Python 3.11+ and git.

## Quick Start

```bash
# One-command setup (initializes + configures Claude Code)
cd your-project
anubis setup

# Or initialize manually
anubis init

# Create a checkpoint with reasoning
anubis checkpoint "Refactoring auth" -r "Trying JWT approach, moving from sessions"

# View checkpoint history
anubis log

# Resume with AI-optimized output (perfect for pasting into Claude/ChatGPT)
anubis resume abc123 --format=prompt

# See semantic analysis of changes
anubis analyze
```

## Commands

| Command | Description |
|---------|-------------|
| `anubis setup` | One-command setup (init + MCP + hooks) |
| `anubis init` | Initialize Anubis in a git repo |
| `anubis checkpoint "msg" -r "reasoning"` | Create checkpoint with reasoning |
| `anubis status` | Show current state and recent checkpoints |
| `anubis log` | View checkpoint history |
| `anubis resume <id>` | View checkpoint details |
| `anubis resume <id> --format=prompt` | AI-optimized output for context injection |
| `anubis resume <id> --format=json` | Machine-readable output |
| `anubis analyze` | Semantic analysis of current changes |
| `anubis commit "msg" -r "reasoning"` | Semantic commit (wraps git commit) |
| `anubis hooks setup` | Set up Claude Code integration |

## Example: AI-Friendly Resume

```bash
$ anubis resume abc123 --format=prompt
```

Output:
```markdown
# Checkpoint: abc123
**Message:** Refactoring auth system
**Created:** 2024-01-15T10:30:00

## Reasoning
Trying JWT approach. Sessions were causing issues with horizontal scaling.
Planning to add refresh token rotation next.

## Changed Files

### src/auth.py (modified)
diff
- from flask import session
+ import jwt
+
+ def create_token(user_id: str) -> str:
+     return jwt.encode({"user_id": user_id}, SECRET_KEY)
```

Copy this into your AI assistant to resume exactly where you left off.

## Claude Code Integration

### MCP Server (Recommended)

Connect Anubis directly to Claude Code via MCP for seamless checkpoint access:

```bash
# Add Anubis MCP server to Claude Code
claude mcp add anubis -- anubis-mcp

# Verify connection
claude mcp list
```

Once connected, Claude Code can:
- List and resume from checkpoints automatically
- Create checkpoints with reasoning during coding
- Access semantic analysis of changes

### Hooks (Auto-checkpoint)

Auto-checkpoint when Claude Code makes changes:

```bash
anubis hooks setup
```

Add the output to `~/.claude/settings.json` to enable automatic checkpoints on file edits.

## How It Works

- Metadata stored in `.anubis/` directory (gitignored)
- Wraps git for file versioning
- SQLite database for checkpoints and semantic data
- AST parsing for Python/JavaScript semantic analysis

## License

MIT
