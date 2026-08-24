#!/bin/bash
# Demo script for Anubis MCP integration

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m' # No Color

sleep 0.5

echo -e "${DIM}$ ${NC}anubis init"
sleep 0.3
echo "Initialized Anubis in /home/user/myproject"
echo "Database: /home/user/myproject/.anubis/anubis.db"
sleep 1.2

echo ""
echo -e "${DIM}$ ${NC}claude mcp add anubis -- anubis-mcp"
sleep 0.3
echo -e "${GREEN}Added MCP server: anubis${NC}"
sleep 1.2

echo ""
echo -e "${DIM}$ ${NC}anubis checkpoint \"Added JWT auth\" -r \"Switching from sessions for better scaling\""
sleep 0.3
echo "Checkpoint created: 3f8a2b1c"
echo "  Message: Added JWT auth"
echo "  Reasoning: Switching from sessions for better scaling"
echo "  Files: src/auth.py, src/middleware.py"
sleep 1.5

echo ""
echo -e "${DIM}$ ${NC}anubis log"
sleep 0.3
echo ""
echo -e "${YELLOW}3f8a2b1c${NC} - 2 minutes ago"
echo "  Added JWT auth"
echo -e "  Reasoning: ${DIM}Switching from sessions for better scaling${NC}"
echo "  Files: src/auth.py, src/middleware.py"
echo ""
echo -e "${YELLOW}a91c4e2d${NC} - 15 minutes ago"
echo "  Refactoring user model"
echo -e "  Reasoning: ${DIM}Normalizing fields for API consistency${NC}"
sleep 2

echo ""
echo -e "${DIM}# Now in Claude Code...${NC}"
sleep 1
echo ""
echo -e "${CYAN}Claude:${NC} I can see your checkpoint 3f8a2b1c."
echo "        You were adding JWT auth because sessions"
echo "        don't scale. Let me continue from there..."
sleep 2.5
