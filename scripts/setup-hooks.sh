#!/bin/bash
# Setup Script for Git Hooks and Security Features
#
# This script installs pre-commit and pre-push git hooks that prevent:
# - Committing with debug flags set to True
# - Pushing to protected branches or release tags with debug flags
#
# Usage: ./setup-hooks.sh
# Or:    bash setup-hooks.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR="$SCRIPT_DIR/.git/hooks"
REPO_HOOKS_DIR="$SCRIPT_DIR/.githooks"

echo "======================================"
echo "Setting up Git Hooks for DICOMViewerV3"
echo "======================================"
echo ""

# Check if .git exists
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# Create hooks directories if they don't exist
mkdir -p "$GIT_HOOKS_DIR"
mkdir -p "$REPO_HOOKS_DIR"

# Copy pre-commit hook from .githooks if it exists there
if [ -f "$REPO_HOOKS_DIR/pre-commit" ]; then
    cp "$REPO_HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo -e "${GREEN}✓${NC} Installed pre-commit hook"
else
    echo -e "${YELLOW}!${NC} .githooks/pre-commit not found; creating default..."
    # Create a minimal hook if not present
    mkdir -p "$GIT_HOOKS_DIR"
    cat > "$GIT_HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Pre-commit hook: Check debug flags
DEBUG_FLAGS_FILE="src/utils/debug_flags.py"
if grep -E "^\s*DEBUG_.*\s*:\s*bool\s*=\s*True" "$DEBUG_FLAGS_FILE" > /dev/null 2>&1; then
    echo "[ERROR] Debug flags are set to True. Please fix before committing."
    exit 1
fi
exit 0
EOF
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo -e "${GREEN}✓${NC} Created minimal pre-commit hook"
fi

# Copy pre-push hook
if [ -f "$REPO_HOOKS_DIR/pre-push" ]; then
    cp "$REPO_HOOKS_DIR/pre-push" "$GIT_HOOKS_DIR/pre-push"
    chmod +x "$GIT_HOOKS_DIR/pre-push"
    echo -e "${GREEN}✓${NC} Installed pre-push hook"
fi

# Check Python environment
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python 3 is available"
fi

if command -v pip &> /dev/null; then
    echo -e "${GREEN}✓${NC} pip is available"
    
    # Optional: Check if log_sanitizer is importable
    if python3 -c "from src.utils.log_sanitizer import sanitize_message" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} log_sanitizer module is ready"
    else
        echo -e "${YELLOW}!${NC} log_sanitizer is not yet integrated (you can import it manually)"
    fi
fi

echo ""
echo "======================================"
echo "Git Hooks Configuration"
echo "======================================"
echo ""
echo "The following hooks are now active:"
echo ""
echo "  📋 pre-commit:  Prevents commits with DEBUG_* = True"
echo "  📤 pre-push:    Prevents pushes to protected branches/tags with debug flags"
echo ""
echo "Configuration:"
echo "  • Git hooks location: $GIT_HOOKS_DIR"
echo "  • Debug flags file:   src/utils/debug_flags.py"
echo "  • Log sanitizer:      src/utils/log_sanitizer.py"
echo ""
echo "Next Steps:"
echo "  1. Review src/utils/debug_flags.py - ensure all DEBUG_* = False"
echo "  2. Import log_sanitizer in your exception handlers (see docs)"
echo "  3. Run 'git commit' to test the pre-commit hook"
echo ""
echo -e "${GREEN}Setup complete!${NC}"
