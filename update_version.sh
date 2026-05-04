#!/bin/bash
# Update version across all Smart Retire AI files

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if version argument provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Version number required${NC}"
    echo ""
    echo "Usage: $0 <version>"
    echo "Examples: "
    echo "  $0 8.1.0"
    echo "  $0 v8.1.0"
    echo ""
    exit 1
fi

INPUT_VERSION="$1"

# Strip 'v' prefix if present (support both 8.1.0 and v8.1.0)
if [[ "$INPUT_VERSION" =~ ^v ]]; then
    NEW_VERSION="${INPUT_VERSION#v}"
    echo -e "${CYAN}ℹ Detected 'v' prefix, using version: ${NEW_VERSION}${NC}"
else
    NEW_VERSION="$INPUT_VERSION"
fi

# Validate version format (basic check for X.Y.Z pattern)
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${YELLOW}Warning: Version '$NEW_VERSION' doesn't match standard X.Y.Z format${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Updating Smart Retire AI to version ${NEW_VERSION}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Function to update file and show result
update_file() {
    local file=$1
    local pattern=$2
    local replacement=$3
    local description=$4

    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ File not found: $file${NC}"
        return 1
    fi

    # Create backup
    cp "$file" "$file.bak"

    # Perform replacement - handle macOS vs Linux sed
    # Use -E for extended regex (works on both macOS and Linux)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS requires empty string after -i
        sed -i '' -E "s/$pattern/$replacement/g" "$file"
    else
        # Linux sed with extended regex
        sed -i -E "s/$pattern/$replacement/g" "$file"
    fi

    # Check if change was made
    if diff -q "$file" "$file.bak" > /dev/null; then
        echo -e "${YELLOW}⚠ No changes in: $file ($description)${NC}"
        rm "$file.bak"
        return 1
    else
        echo -e "${GREEN}✓ Updated: $file ($description)${NC}"
        rm "$file.bak"
        return 0
    fi
}

# Update fin_advisor.py docstring (using extended regex syntax)
update_file \
    "fin_advisor.py" \
    "^Version: [0-9]+\.[0-9]+\.[0-9]+$" \
    "Version: $NEW_VERSION" \
    "docstring"

# Update fin_advisor.py VERSION variable
update_file \
    "fin_advisor.py" \
    '^VERSION = "[0-9]+\.[0-9]+\.[0-9]+"$' \
    "VERSION = \"$NEW_VERSION\"" \
    "VERSION constant"

# Update financialadvisor/__init__.py
update_file \
    "financialadvisor/__init__.py" \
    '^__version__ = "[0-9]+\.[0-9]+\.[0-9]+"$' \
    "__version__ = \"$NEW_VERSION\"" \
    "__version__"

# Update setup.py
update_file \
    "setup.py" \
    '^    version="[0-9]+\.[0-9]+\.[0-9]+",$' \
    "    version=\"$NEW_VERSION\"," \
    "setup version"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Version update complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "Files updated:"
echo "  • fin_advisor.py (docstring and VERSION)"
echo "  • financialadvisor/__init__.py (__version__)"
echo "  • setup.py (version)"
echo ""

# ── AI steps via Claude CLI ──────────────────────────────────────────
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AI Steps (Claude CLI)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

if ! command -v claude &> /dev/null; then
    echo -e "${YELLOW}⚠ 'claude' CLI not found — skipping AI steps.${NC}"
    echo "  Update README.md, CLAUDE.md, and release notes manually."
    echo ""
else
    # Update README.md and CLAUDE.md
    echo -e "${CYAN}Updating README.md and CLAUDE.md...${NC}"
    claude --allowedTools "Edit,Read" --output-format text -p \
"Update the version number to ${NEW_VERSION} in two files:
1. README.md — the line that reads '**Current version: X.Y.Z**' should become '**Current version: ${NEW_VERSION}**'
2. CLAUDE.md — the line that reads 'Current version: **X.Y.Z**' should become 'Current version: **${NEW_VERSION}**'
Make only those two targeted edits, nothing else."
    echo -e "${GREEN}✓ README.md and CLAUDE.md updated${NC}"
    echo ""

    # Generate release notes
    echo -e "${CYAN}Generating release notes for v${NEW_VERSION}...${NC}"
    claude --allowedTools "Read,Write,Bash" --output-format text -p \
"Create release notes for Smart Retire AI v${NEW_VERSION}:
1. Run 'git log --oneline -30' to see recent commits
2. Read one existing file from release-notes/ to match the format and style
3. Write RELEASE_NOTES_v${NEW_VERSION}.md at the project root with sections: Release Overview, Features/Changes, Bug Fixes, UI Changes, Files Changed
4. Find any RELEASE_NOTES_v*.md file at the project root that is NOT the newly created v${NEW_VERSION} file — for each one, copy it into the release-notes/ folder and delete the root copy"
    echo -e "${GREEN}✓ Release notes created: RELEASE_NOTES_v${NEW_VERSION}.md${NC}"
    echo ""
fi

# Interactive git workflow
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Git Workflow${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Review changes
echo -e "${CYAN}Step 1/3: Review changes${NC}"
read -p "Run 'git diff' to review changes? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Skipped git diff${NC}"
else
    echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
    git diff
    echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
fi
echo ""

# Step 2: Stage and commit
echo -e "${CYAN}Step 2/3: Stage and commit changes${NC}"
read -p "Stage and commit changes? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Skipped commit. You can commit manually later:${NC}"
    echo "  git add -u"
    echo "  git commit -m 'Bump version to $NEW_VERSION'"
    exit 0
else
    echo -e "${GREEN}Staging changes...${NC}"
    git add -u
    # Also stage new files created by the Claude CLI steps (git add -u skips untracked files)
    git add "RELEASE_NOTES_v${NEW_VERSION}.md" release-notes/ 2>/dev/null || true

    echo -e "${GREEN}Committing...${NC}"
    git commit -m "Bump version to $NEW_VERSION"
    echo -e "${GREEN}✓ Committed${NC}"
fi

echo ""

# Step 3: Push to remote
echo -e "${CYAN}Step 3/3: Push to remote${NC}"
read -p "Push commits? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Skipped push. You can push manually later:${NC}"
    echo "  git push"
else
    echo -e "${GREEN}Pushing commits...${NC}"
    git push
    echo -e "${GREEN}✓ Pushed to remote${NC}"
fi
echo ""

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Release v${NEW_VERSION} complete! 🚀${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
