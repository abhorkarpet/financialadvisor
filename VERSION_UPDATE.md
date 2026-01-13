# Version Update Script

## Quick Start

Update the version across all files with a single command:

```bash
./update_version.sh 8.1.0
```

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

# Minor release
./update_version.sh 8.1.0

# Patch release
./update_version.sh 8.0.1
```

## Features

- ✅ **Validates format**: Checks for standard X.Y.Z versioning
- ✅ **Creates backups**: Saves `.bak` files before making changes
- ✅ **Shows results**: Color-coded output for each file updated
- ✅ **Safe**: Exits on error, confirms non-standard versions
- ✅ **Helpful**: Shows next steps after updating

## Output Example

```
Updating Smart Retire AI to version 8.1.0...

✓ Updated: fin_advisor.py (docstring)
✓ Updated: fin_advisor.py (VERSION constant)
✓ Updated: financialadvisor/__init__.py (__version__)
✓ Updated: setup.py (setup version)

Version update complete!

Files updated:
  • fin_advisor.py (docstring and VERSION)
  • financialadvisor/__init__.py (__version__)
  • setup.py (version)

Next steps:
  1. Review changes: git diff
  2. Commit: git add -u && git commit -m 'Bump version to 8.1.0'
  3. Tag: git tag -a v8.1.0 -m 'Release v8.1.0'
  4. Push: git push && git push --tags
```

## Validation

The script checks for standard semantic versioning (X.Y.Z) format:
- ✅ Valid: `8.1.0`, `10.0.0`, `1.2.3`
- ⚠️  Warning: `8.1`, `v8.1.0`, `8.1.0-beta`

If you use a non-standard format, the script will warn you and ask for confirmation.

## Complete Release Workflow

```bash
# 1. Update version
./update_version.sh 8.1.0

# 2. Review changes
git diff

# 3. Commit version bump
git add -u
git commit -m "Bump version to 8.1.0"

# 4. Create git tag
git tag -a v8.1.0 -m "Release v8.1.0"

# 5. Push to remote
git push
git push --tags
```

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
