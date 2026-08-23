# VHS demo script for Anubis
# Install: brew install vhs (or go install github.com/charmbracelet/vhs@latest)
# Run: vhs demo.tape

Output demo.gif

Set FontSize 14
Set Width 800
Set Height 500
Set Theme "Dracula"

Type "# Working on a feature with Claude Code..."
Enter
Sleep 500ms

Type "anubis init"
Enter
Sleep 1s

Type@50ms "# Claude makes some changes..."
Enter
Sleep 500ms

Type "echo 'def authenticate(user):' >> auth.py"
Enter
Sleep 300ms

Type "echo '    return jwt.encode(user.id)' >> auth.py"
Enter
Sleep 500ms

Type@50ms "# Anubis auto-checkpoints with reasoning"
Enter
Sleep 500ms

Type "anubis checkpoint 'Added JWT auth' -r 'Switching from sessions - better for scaling'"
Enter
Sleep 1.5s

Type "anubis log"
Enter
Sleep 2s

Type@50ms "# Later, resume with full context..."
Enter
Sleep 500ms

Type "anubis resume --format=prompt | head -20"
Enter
Sleep 3s

Type@50ms "# Copy this into Claude to continue exactly where you left off"
Enter
Sleep 2s
