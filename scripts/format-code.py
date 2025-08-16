#!/usr/bin/env python3
"""
Code formatting script for MentorAI project.
Provides summary of formatting changes and runs Black + isort.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=False
        )
        return result
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return None


def format_with_black():
    """Run Black formatter and show summary."""
    print("=" * 60)
    print("🎨 FORMATTING CODE WITH BLACK")
    print("=" * 60)

    # First check what would be changed
    check_result = run_command("black --check --diff .", "Checking formatting")

    if check_result and check_result.returncode == 0:
        print("✅ All files are already properly formatted!")
        return True

    # Count files that need formatting
    count_result = run_command(
        "black --check . 2>&1 | grep -c 'would reformat'", "Counting files")

    if count_result and count_result.stdout.strip():
        file_count = count_result.stdout.strip()
        print(f"📊 Files needing formatting: {file_count}")

    # Show preview of changes (first 20 lines)
    if check_result and check_result.stdout:
        lines = check_result.stdout.split('\n')
        preview_lines = lines[:20]
        print("\n📋 Preview of changes:")
        print("-" * 40)
        for line in preview_lines:
            if line.strip():
                print(line)

        if len(lines) > 20:
            print(f"... and {len(lines) - 20} more lines")
        print("-" * 40)

    # Ask for confirmation
    response = input("\n🤔 Apply these formatting changes? (y/N): ").lower()

    if response in ['y', 'yes']:
        format_result = run_command("black .", "Applying Black formatting")
        if format_result and format_result.returncode == 0:
            print("✅ Black formatting applied successfully!")
            return True
        else:
            print("❌ Black formatting failed!")
            return False
    else:
        print("⏭️  Skipping Black formatting")
        return False


def format_with_isort():
    """Run isort and show summary."""
    print("\n" + "=" * 60)
    print("📚 SORTING IMPORTS WITH ISORT")
    print("=" * 60)

    # Check what would be changed
    check_result = run_command(
        "isort --check-only --diff .", "Checking imports")

    if check_result and check_result.returncode == 0:
        print("✅ All imports are already properly sorted!")
        return True

    if check_result and check_result.stdout:
        print("\n📋 Import changes needed:")
        print("-" * 40)
        lines = check_result.stdout.split('\n')[:15]  # Show first 15 lines
        for line in lines:
            if line.strip():
                print(line)
        print("-" * 40)

    # Ask for confirmation
    response = input("\n🤔 Apply import sorting? (y/N): ").lower()

    if response in ['y', 'yes']:
        sort_result = run_command("isort .", "Applying import sorting")
        if sort_result and sort_result.returncode == 0:
            print("✅ Import sorting applied successfully!")
            return True
        else:
            print("❌ Import sorting failed!")
            return False
    else:
        print("⏭️  Skipping import sorting")
        return False


def main():
    """Main function."""
    print("🚀 MentorAI Code Formatter")
    print("This script will help you format your code with Black and isort.")
    print()

    # Change to project root
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)

    success = True

    # Format with Black
    if not format_with_black():
        success = False

    # Sort imports with isort
    if not format_with_isort():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("🎉 CODE FORMATTING COMPLETED SUCCESSFULLY!")
        print("Your code is now properly formatted and ready for commit.")
    else:
        print("⚠️  CODE FORMATTING PARTIALLY COMPLETED")
        print("Some formatting steps were skipped or failed.")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
