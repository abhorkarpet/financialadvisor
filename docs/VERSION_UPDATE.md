# Version Update Script

## Quick Start

Update the version across all files with a single command:

```bash
./update_version.sh 8.1.0
# or with 'v' prefix
./update_version.sh v8.1.0
```

The script will guide you through the entire release workflow interactively!

## What It Does

The script updates the version number in all of these files:

1. **fin_advisor.py**
   - Docstring: `Version: X.Y.Z`
   - Python constant: `VERSION = "X.Y.Z"`

2. **financialadvisor/__init__.py**
   - Package version: `__version__ = "X.Y.Z"`

3. **setup.py**
   - Setup version: `version="X.Y.Z"`

## Usage

```bash
./update_version.sh <version>
```

### Examples

```bash
# Major release
./update_version.sh 9.0.0
./update_version.sh v9.0.0  # 'v' prefix supported

# Minor release
./update_version.sh 8.1.0
./update_version.sh v8.1.0  # 'v' prefix supported

# Patch release
./update_version.sh 8.0.1
./update_version.sh v8.0.1  # 'v' prefix supported
```

## Features

- ✅ **Supports 'v' prefix**: Works with both `8.1.0` and `v8.1.0` formats
- ✅ **Interactive workflow**: Step-by-step confirmations for git operations
- ✅ **Validates format**: Checks for standard X.Y.Z versioning
- ✅ **Creates backups**: Saves `.bak` files before making changes
- ✅ **Shows results**: Color-coded output for each file updated
- ✅ **Safe**: Exits on error, confirms non-standard versions
- ✅ **Git automation**: Optionally handles commit, tag, and push

## Output Example

```
═══════════════════════════════════════════════════════
  Updating Smart Retire AI to version 8.1.0
═══════════════════════════════════════════════════════

✓ Updated: fin_advisor.py (docstring)
✓ Updated: fin_advisor.py (VERSION constant)
✓ Updated: financialadvisor/__init__.py (__version__)
✓ Updated: setup.py (setup version)

═══════════════════════════════════════════════════════
  Version update complete!
═══════════════════════════════════════════════════════

Files updated:
  • fin_advisor.py (docstring and VERSION)
  • financialadvisor/__init__.py (__version__)
  • setup.py (version)

═══════════════════════════════════════════════════════
  Git Workflow
═══════════════════════════════════════════════════════

Step 1/4: Review changes
Run 'git diff' to review changes? (Y/n) Y
[shows diff output]

Step 2/4: Stage and commit changes
Stage and commit changes? (Y/n) Y
Staging changes...
Committing...
✓ Committed

Step 3/4: Create git tag
Create git tag 'v8.1.0'? (Y/n) Y
✓ Tag created: v8.1.0

Step 4/4: Push to remote
Push commits and tags to remote? (Y/n) Y
Pushing commits...
Pushing tags...
✓ Pushed to remote

═══════════════════════════════════════════════════════
  Release v8.1.0 complete! 🚀
═══════════════════════════════════════════════════════
```

## Validation

The script checks for standard semantic versioning (X.Y.Z) format:
- ✅ Valid: `8.1.0`, `v8.1.0`, `10.0.0`, `v10.0.0`, `1.2.3`
- ⚠️  Warning: `8.1`, `8.1.0-beta`, `8.1.0-rc1`

**Note:** The `v` prefix is automatically stripped and handled correctly. Both `8.1.0` and `v8.1.0` will update files to `8.1.0` and create git tag `v8.1.0`.

If you use a non-standard format, the script will warn you and ask for confirmation.

## Interactive Workflow

The script now guides you through each step interactively:

```bash
./update_version.sh v8.1.0
```

You'll be prompted for each step:
1. **Review changes** - View git diff (Y/n)
2. **Commit** - Stage and commit with automatic message (Y/n)
3. **Tag** - Create git tag `v8.1.0` (Y/n)
4. **Push** - Push commits and tags to remote (Y/n)

You can skip any step by pressing `n` - perfect for:
- Testing version updates without committing
- Reviewing changes before committing
- Creating custom commit messages manually
- Pushing to different remotes

## Manual Workflow (if you skip steps)

If you skip the interactive steps, you can run commands manually:

```bash
# 1. Update version (files only, skip git steps)
./update_version.sh 8.1.0
# Press 'n' for all git prompts

# 2. Review and commit manually
git diff
git add -u
git commit -m "Bump version to 8.1.0"

# 3. Create tag manually
git tag -a v8.1.0 -m "Release v8.1.0"

# 4. Push manually
git push
git push --tags
```

## Interactive Features

### Step-by-Step Confirmations

Each git operation requires confirmation:
- **Default is Yes (Y)** - Just press Enter to proceed
- **Skip with No (n)** - Press 'n' to skip the step
- **Exit early** - If you skip commit, the script exits gracefully

### Tag Handling

If a tag already exists, the script will:
1. Detect the existing tag
2. Ask if you want to recreate it
3. Delete and recreate if you confirm
4. Keep the existing tag if you decline

### Safe Defaults

- All file changes create `.bak` backups
- Git operations only run after explicit confirmation
- Skipped steps show manual commands for later execution
- Non-standard versions require explicit confirmation

## Troubleshooting

### "File not found" error
Make sure you run the script from the repository root:
```bash
cd /path/to/financialadvisor
./update_version.sh 8.1.0
```

### Script not executable
Make it executable:
```bash
chmod +x update_version.sh
```

### No changes detected
The version might already be set to that value. Check current version:
```bash
grep "VERSION = " fin_advisor.py
```

## Current Version

To check the current version:

```bash
# Check all version locations
grep "^Version:" fin_advisor.py
grep "^VERSION = " fin_advisor.py
grep "__version__" financialadvisor/__init__.py
grep "version=" setup.py | head -1
```

## Script Location

`/home/user/financialadvisor/update_version.sh`
