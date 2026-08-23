# VHS demo script for Anubis
# Simulates anubis commands with realistic output

Output demo.gif

Set FontSize 14
Set Width 850
Set Height 450
Set Theme "Dracula"
Set Padding 20

Sleep 500ms

Type "# Initialize Anubis in a git repo"
Enter
Sleep 800ms

Type "anubis init"
Enter
Sleep 300ms
Type "Initialized Anubis in /home/user/myproject"
Enter
Type "Database: /home/user/myproject/.anubis/anubis.db"
Enter
Sleep 1s

Type "# Create a checkpoint with reasoning"
Enter
Sleep 800ms

Type "anubis checkpoint 'Added JWT auth' -r 'Switching from sessions for better scaling'"
Enter
Sleep 300ms
Type "Checkpoint created: 3f8a2b1c"
Enter
Type "  Message: Added JWT auth"
Enter
Type "  Reasoning: Switching from sessions for better scaling"
Enter
Type "  Files: src/auth.py, src/middleware.py"
Enter
Sleep 1.5s

Type "# View checkpoint history"
Enter
Sleep 800ms

Type "anubis log"
Enter
Sleep 300ms
Enter
Type "3f8a2b1c - 2 minutes ago"
Enter
Type "  Added JWT auth"
Enter
Type "  Reasoning: Switching from sessions for better scaling"
Enter
Type "  Files: src/auth.py, src/middleware.py"
Enter
Enter
Type "a91c4e2d - 15 minutes ago"
Enter
Type "  Refactoring user model"
Enter
Type "  Reasoning: Normalizing fields for API consistency"
Enter
Type "  Files: src/models/user.py"
Enter
Sleep 2s

Type "# Resume with AI-friendly output"
Enter
Sleep 800ms

Type "anubis resume 3f8a --format=prompt"
Enter
Sleep 300ms
Enter
Type "# Checkpoint: 3f8a2b1c"
Enter
Type "**Message:** Added JWT auth"
Enter
Type "**Created:** 2024-01-15T10:30:00"
Enter
Enter
Type "## Reasoning"
Enter
Type "Switching from sessions for better scaling"
Enter
Enter
Type "## Changed Files"
Enter
Type "### src/auth.py (modified)"
Enter
Type "\`\`\`diff"
Enter
Type "- from flask import session"
Enter
Type "+ import jwt"
Enter
Type "+ def create_token(user_id):"
Enter
Type "+     return jwt.encode({'user_id': user_id}, SECRET)"
Enter
Type "\`\`\`"
Enter
Sleep 2s

Type "# Copy this into Claude to resume exactly where you left off"
Enter
Sleep 2s
