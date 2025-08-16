#!/usr/bin/env python3
"""
Quick formatting checker that summarizes Black's findings.
"""

import re
import subprocess
import sys
from collections import defaultdict


def analyze_black_output():
    """Analyze Black's output and provide a summary."""
    try:
        # Run black --check --diff to see what would change
        result = subprocess.run(
            ["black", "--check", "--diff", "."],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode == 0:
            print("✅ All files are properly formatted!")
            return True

        output = result.stdout

        # Parse the output to understand what needs to be changed
        files_to_format = []
        change_types = defaultdict(int)

        current_file = None
        for line in output.split("\n"):
            if line.startswith("---") and ".py" in line:
                # Extract filename
                match = re.search(r"--- (.+\.py)", line)
                if match:
                    current_file = match.group(1)
                    files_to_format.append(current_file)
            elif line.startswith("+") or line.startswith("-"):
                # Analyze the type of change
                if "import" in line.lower():
                    change_types["Import formatting"] += 1
                elif line.strip() in ["", "+", "-"]:
                    change_types["Whitespace/blank lines"] += 1
                elif '"' in line or "'" in line:
                    change_types["String formatting"] += 1
                elif "(" in line or ")" in line or "[" in line or "]" in line:
                    change_types["Bracket/parentheses formatting"] += 1
                else:
                    change_types["Other formatting"] += 1

        # Print summary
        print("📊 BLACK FORMATTING SUMMARY")
        print("=" * 50)
        print(f"Files needing formatting: {len(files_to_format)}")
        print(f"Total changes needed: {sum(change_types.values())}")
        print()

        print("📋 Types of changes needed:")
        for change_type, count in sorted(
            change_types.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  • {change_type}: {count} changes")
        print()

        print("📁 Files that need formatting:")
        for i, file_path in enumerate(files_to_format[:10], 1):
            print(f"  {i}. {file_path}")

        if len(files_to_format) > 10:
            print(f"  ... and {len(files_to_format) - 10} more files")

        print()
        print("🔧 To fix all formatting issues, run:")
        print("   black .")
        print("   python scripts/format-code.py  # Interactive mode")

        return False

    except FileNotFoundError:
        print("❌ Black is not installed. Install with: pip install black")
        return False
    except Exception as e:
        print(f"❌ Error running Black: {e}")
        return False


def main():
    print("🎨 MentorAI Formatting Checker")
    print("Analyzing your code formatting...\n")

    success = analyze_black_output()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
