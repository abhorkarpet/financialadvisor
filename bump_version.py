#!/usr/bin/env python3
"""
Version Bump Script for Financial Advisor

This script automatically bumps the minor version number in fin_advisor.py
and updates both the docstring and footer display.

Usage:
    python bump_version.py
"""

import re
import sys

def bump_version_in_file(file_path: str) -> str:
    """Bump the minor version in the specified file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find current version in VERSION constant
        version_match = re.search(r'VERSION = "(\d+\.\d+\.\d+)"', content)
        if not version_match:
            print(f"❌ Could not find VERSION constant in {file_path}")
            return None
        
        current_version = version_match.group(1)
        print(f"📋 Current version: {current_version}")
        
        # Bump minor version
        parts = current_version.split('.')
        major, minor, patch = parts[0], parts[1], parts[2]
        new_minor = str(int(minor) + 1)
        new_version = f"{major}.{new_minor}.{patch}"
        
        print(f"🚀 Bumping to version: {new_version}")
        
        # Replace VERSION constant
        content = re.sub(
            r'VERSION = "\d+\.\d+\.\d+"',
            f'VERSION = "{new_version}"',
            content
        )
        
        # Replace version in docstring
        content = re.sub(
            r'Version: \d+\.\d+\.\d+',
            f'Version: {new_version}',
            content
        )
        
        # Write back to file
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Successfully bumped version to {new_version}")
        return new_version
        
    except Exception as e:
        print(f"❌ Error bumping version: {e}")
        return None

if __name__ == "__main__":
    new_version = bump_version_in_file("fin_advisor.py")
    if new_version:
        print(f"\n🎉 Version {new_version} is ready for commit!")
        sys.exit(0)
    else:
        sys.exit(1)
