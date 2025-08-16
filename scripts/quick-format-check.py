#!/usr/bin/env python3
"""
Simple, Windows-compatible formatting checker.
Provides a quick summary without complex parsing.
"""

import os
import subprocess
import sys


def main():
    """Main function for quick formatting check."""
    print("🎨 Quick Formatting Check")
    print("=" * 40)

    # Change to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)

    try:
        # Check Black formatting
        print("🔍 Checking Black formatting...")
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", "."],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode == 0:
            print("✅ All files are properly formatted with Black!")
        else:
            # Count files that need formatting
            stderr_lines = result.stderr.split("\n")
            format_lines = [line for line in stderr_lines if "would reformat" in line]

            print(f"❌ Found {len(format_lines)} files that need formatting")

            # Show first few files
            for i, line in enumerate(format_lines[:5]):
                if "would reformat" in line:
                    filename = line.split("would reformat")[1].strip()
                    print(f"   {i+1}. {filename}")

            if len(format_lines) > 5:
                print(f"   ... and {len(format_lines) - 5} more files")

        print()

        # Check isort
        print("🔍 Checking import sorting...")
        result = subprocess.run(
            [sys.executable, "-m", "isort", "--check-only", "."],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode == 0:
            print("✅ All imports are properly sorted!")
        else:
            print("❌ Some imports need sorting")

        print()
        print("🔧 To fix all formatting issues:")
        print("   python -m black .")
        print("   python -m isort .")
        print()
        print("💡 Or install pre-commit hooks:")
        print("   pip install pre-commit")
        print("   pre-commit install")

    except FileNotFoundError as e:
        print(f"❌ Tool not found: {e}")
        print("💡 Install development dependencies:")
        print("   pip install -r requirements-dev.txt")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
