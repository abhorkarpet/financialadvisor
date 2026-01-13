#!/bin/bash
# Update version across all Smart Retire AI files

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if version argument provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Version number required${NC}"
    echo ""
    echo "Usage: $0 <version>"
    echo "Example: $0 8.1.0"
    echo ""
    exit 1
fi

NEW_VERSION="$1"

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

echo -e "${BLUE}Updating Smart Retire AI to version ${NEW_VERSION}...${NC}"
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

    # Perform replacement
    sed -i "s/$pattern/$replacement/g" "$file"

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

# Update fin_advisor.py docstring
update_file \
    "fin_advisor.py" \
    "^Version: [0-9]\+\.[0-9]\+\.[0-9]\+$" \
    "Version: $NEW_VERSION" \
    "docstring"

# Update fin_advisor.py VERSION variable
update_file \
    "fin_advisor.py" \
    '^VERSION = "[0-9]\+\.[0-9]\+\.[0-9]\+"$' \
    "VERSION = \"$NEW_VERSION\"" \
    "VERSION constant"

# Update financialadvisor/__init__.py
update_file \
    "financialadvisor/__init__.py" \
    '^__version__ = "[0-9]\+\.[0-9]\+\.[0-9]\+"$' \
    "__version__ = \"$NEW_VERSION\"" \
    "__version__"

# Update setup.py
update_file \
    "setup.py" \
    '^    version="[0-9]\+\.[0-9]\+\.[0-9]\+",$' \
    "    version=\"$NEW_VERSION\"," \
    "setup version"

echo ""
echo -e "${GREEN}Version update complete!${NC}"
echo ""
echo "Files updated:"
echo "  • fin_advisor.py (docstring and VERSION)"
echo "  • financialadvisor/__init__.py (__version__)"
echo "  • setup.py (version)"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Commit: git add -u && git commit -m 'Bump version to $NEW_VERSION'"
echo "  3. Tag: git tag -a v$NEW_VERSION -m 'Release v$NEW_VERSION'"
echo "  4. Push: git push && git push --tags"
echo ""
