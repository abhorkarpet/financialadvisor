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

# Interactive git workflow
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Git Workflow${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Review changes
echo -e "${CYAN}Step 1/4: Review changes${NC}"
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
echo -e "${CYAN}Step 2/4: Stage and commit changes${NC}"
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

    echo -e "${GREEN}Committing...${NC}"
    git commit -m "Bump version to $NEW_VERSION"
    echo -e "${GREEN}✓ Committed${NC}"
fi
echo ""

# Step 3: Create git tag
echo -e "${CYAN}Step 3/4: Create git tag${NC}"
read -p "Create git tag 'v$NEW_VERSION'? (Y/n) " -n 1 -r
tag = 1
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Skipped tag creation. You can tag manually later:${NC}"
    echo "  git tag -a v$NEW_VERSION -m 'Release v$NEW_VERSION'"
    tag = 0
else
    # Check if tag already exists
    if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
        echo -e "${RED}✗ Tag v$NEW_VERSION already exists${NC}"
        read -p "Delete and recreate tag? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git tag -d "v$NEW_VERSION"
            git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
            echo -e "${GREEN}✓ Tag recreated: v$NEW_VERSION${NC}"
        else
            echo -e "${YELLOW}Keeping existing tag${NC}"
        fi
    else
        git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
        echo -e "${GREEN}✓ Tag created: v$NEW_VERSION${NC}"
    fi
fi
echo ""

# Step 4: Push to remote
echo -e "${CYAN}Step 4/4: Push to remote${NC}"
read -p "Push commits and tags to remote? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Skipped push. You can push manually later:${NC}"
    echo "  git push"
    echo "  git push --tags"
else
    echo -e "${GREEN}Pushing commits...${NC}"
    git push
    if $tag = 1; then
	echo -e "${GREEN}Pushing tags...${NC}"
	git push --tags
    fi
    echo -e "${GREEN}✓ Pushed to remote${NC}"
fi
echo ""

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Release v${NEW_VERSION} complete! 🚀${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
