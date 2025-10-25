#!/bin/bash
set -e  # Exit on error

# AURA Unified Installer
# Usage:
#   ./install.sh              # Install AURA microservices + setup current project
#   ./install.sh --aura-only  # Just install microservices, skip project setup

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 AURA Unified Installer${NC}\n"

# Detect where this script is (AURA installation location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AURA_HOME="$SCRIPT_DIR"

echo -e "${GREEN}📍 AURA Location:${NC} $AURA_HOME"

# Detect project root (where we'll install .context/ structure)
detect_project_root() {
    local current="$PWD"

    # Walk up to find .git directory
    while [[ "$current" != "/" ]]; do
        if [[ -d "$current/.git" ]]; then
            echo "$current"
            return 0
        fi
        current=$(dirname "$current")
    done

    # No git repo found, use current directory
    echo "$PWD"
    return 1
}

PROJECT_ROOT=$(detect_project_root) || true
if [[ -d "$PROJECT_ROOT/.git" ]]; then
    echo -e "${GREEN}📍 Project Root:${NC} $PROJECT_ROOT (git detected)"
else
    echo -e "${YELLOW}⚠️  Not a git repository${NC}"
    echo -e "${GREEN}📍 Project Root:${NC} $PROJECT_ROOT (using current dir)"
fi

# Parse arguments
AURA_ONLY=false
if [[ "$1" == "--aura-only" ]]; then
    AURA_ONLY=true
fi

echo ""

# ===== Check for old installation =====
if command -v pipx &> /dev/null; then
    if pipx list 2>/dev/null | grep -q "aura"; then
        echo -e "${YELLOW}⚠️  Old monolithic 'aura' installation detected${NC}"
        echo -e "${YELLOW}   This may conflict with the new microservices.${NC}"
        echo -e "${YELLOW}   Recommended: pipx uninstall aura${NC}"
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# ===== STEP 1: Install Microservices =====
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 Step 1: Installing Microservices${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Check if venv exists
if [[ ! -d "$AURA_HOME/venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$AURA_HOME/venv"
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
fi

# Activate venv
source "$AURA_HOME/venv/bin/activate"

# Install microservices
echo ""
echo "Installing IMEM (vector search)..."
pip install -e "$AURA_HOME/imem" -q
echo -e "${GREEN}✅ IMEM installed${NC}"

echo ""
echo "Installing TRACE (conversation archaeology)..."
pip install -e "$AURA_HOME/trace" -q
echo -e "${GREEN}✅ TRACE installed${NC}"

echo ""
echo "Installing Qdrant (database manager)..."
pip install -e "$AURA_HOME/qdrant" -q
echo -e "${GREEN}✅ Qdrant installed${NC}"

# Test CLIs
echo ""
echo "Verifying installations..."
if command -v imem &> /dev/null && command -v trace &> /dev/null; then
    echo -e "${GREEN}✅ All CLIs available${NC}"
else
    echo -e "${RED}❌ CLI installation failed${NC}"
    exit 1
fi

# Exit early if --aura-only
if [[ "$AURA_ONLY" == "true" ]]; then
    echo ""
    echo -e "${GREEN}✅ AURA microservices installed!${NC}"
    echo ""
    echo "To use in a project, run from the project directory:"
    echo "  cd /path/to/your/project"
    echo "  $AURA_HOME/install.sh"
    exit 0
fi

# ===== STEP 2: Create .context/ Structure =====
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📁 Step 2: Creating .context/ Structure${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

cd "$PROJECT_ROOT"

# Create directories
mkdir -p .context/design/.changes
mkdir -p .context/design/.modules
mkdir -p .context/designate
mkdir -p .context/develop/.changes
mkdir -p .context/document

echo -e "${GREEN}✅ Created:${NC}"
echo "   .context/design/.changes/      (design exploration)"
echo "   .context/design/.modules/      (R&D staging)"
echo "   .context/designate/            (ground truth plans)"
echo "   .context/develop/.changes/     (implementation logs)"
echo "   .context/document/             (maintained docs)"

# ===== STEP 3: Initialize Registry =====
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 Step 3: Initializing Registry${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Create registry.json in .claude/.trace/
mkdir -p "$PROJECT_ROOT/.claude/.trace"
REGISTRY_FILE="$PROJECT_ROOT/.claude/.trace/registry.json"

if [[ ! -f "$REGISTRY_FILE" ]]; then
    cat > "$REGISTRY_FILE" <<EOF
{
  "conversations": [],
  "metadata": {
    "created": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "project_root": "$PROJECT_ROOT"
  }
}
EOF
    echo -e "${GREEN}✅ Created registry:${NC} $REGISTRY_FILE"
else
    echo -e "${GREEN}✅ Registry exists:${NC} $REGISTRY_FILE"
fi

# ===== STEP 4: SessionStart Hook (Optional) =====
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🪝 Step 4: SessionStart Hook (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

HOOK_TEMPLATE="$AURA_HOME/templates/hooks/session-start.sh"
if [[ -f "$HOOK_TEMPLATE" ]]; then
    mkdir -p "$PROJECT_ROOT/.claude/hooks"

    if [[ ! -f "$PROJECT_ROOT/.claude/hooks/session-start.sh" ]]; then
        cp "$HOOK_TEMPLATE" "$PROJECT_ROOT/.claude/hooks/session-start.sh"
        chmod +x "$PROJECT_ROOT/.claude/hooks/session-start.sh"
        echo -e "${GREEN}✅ Installed SessionStart hook${NC}"
    else
        echo -e "${GREEN}✅ SessionStart hook exists${NC}"
    fi

    # Note about settings.json
    echo -e "${YELLOW}ℹ️  Don't forget to configure .claude/settings.json${NC}"
    echo "   See: https://docs.claude.com/claude-code/hooks"
else
    echo -e "${YELLOW}ℹ️  Hook template not found (skip)${NC}"
fi

# ===== STEP 5: Check Qdrant =====
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 Step 5: Checking Services${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Check if Qdrant is running
if imem service status 2>/dev/null | grep -q "running"; then
    echo -e "${GREEN}✅ Qdrant running on port 6334${NC}"
else
    echo -e "${YELLOW}ℹ️  Qdrant not running${NC}"
    echo "   Start with: imem service start"
fi

# Check conversation folder
CLAUDE_FOLDER="$HOME/.claude/projects"
if [[ -d "$CLAUDE_FOLDER" ]]; then
    CONV_COUNT=$(find "$CLAUDE_FOLDER" -name "*.jsonl" 2>/dev/null | wc -l)
    echo -e "${GREEN}✅ Claude conversations: $CONV_COUNT found${NC}"
else
    echo -e "${YELLOW}ℹ️  No Claude conversations yet${NC}"
fi

# ===== SUCCESS! =====
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ AURA Installed Successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 Installation Summary:${NC}"
echo "   • Microservices: $AURA_HOME"
echo "   • Project: $PROJECT_ROOT"
echo "   • Virtual env: $AURA_HOME/venv"
echo ""
echo -e "${BLUE}🎯 Next Steps:${NC}"
echo ""
echo "1. Activate virtual environment:"
echo -e "   ${YELLOW}source $AURA_HOME/venv/bin/activate${NC}"
echo ""
echo "2. Start Qdrant service:"
echo -e "   ${YELLOW}imem service start${NC}"
echo ""
echo "3. Index your project:"
echo -e "   ${YELLOW}cd $PROJECT_ROOT${NC}"
echo -e "   ${YELLOW}imem init${NC}"
echo ""
echo "4. Search documentation:"
echo -e "   ${YELLOW}imem search \"your query\"${NC}"
echo ""
echo "5. Browse conversations:"
echo -e "   ${YELLOW}trace --list${NC}"
echo ""
echo -e "${BLUE}📚 Documentation:${NC}"
echo "   • IMEM: $AURA_HOME/imem/README.md"
echo "   • TRACE: $AURA_HOME/trace/README.md"
echo "   • Main: $AURA_HOME/README.md"
echo ""
