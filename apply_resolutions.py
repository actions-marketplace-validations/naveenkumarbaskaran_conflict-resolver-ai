"""Apply auto-resolutions to conflicted files and commit."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

CONFLICT_BLOCK = re.compile(
    r'<<<<<<<[^\n]*\n.*?=======\n.*?>>>>>>>[^\n]*\n',
    re.DOTALL
)


def apply_resolutions(result_path: str, commit_message: str):
    """Apply resolved conflicts to files and commit."""
    data = json.load(open(result_path))
    conflicts = data.get("conflicts", [])
    threshold = data.get("confidence_threshold", 85)

    # Group by file
    by_file: dict[str, list] = {}
    for c in conflicts:
        filepath = c.get("file", "")
        resolution = c.get("resolution", {})
        confidence = resolution.get("confidence", 0)

        if confidence < threshold or resolution.get("needs_human_review"):
            continue

        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].append(c)

    if not by_file:
        print("No conflicts meet confidence threshold for auto-resolution")
        return

    resolved_count = 0

    for filepath, file_conflicts in by_file.items():
        if not Path(filepath).exists():
            print(f"  Skip {filepath} — file not found")
            continue

        content = Path(filepath).read_text(errors="replace")

        # Replace each conflict block with its resolution
        # Process in reverse order to maintain line positions
        file_conflicts.sort(key=lambda c: c.get("line_number", 0), reverse=True)

        for c in file_conflicts:
            resolved_code = c["resolution"].get("resolved_code", "")
            if not resolved_code:
                continue

            # Find and replace the conflict block
            # Match the specific conflict markers in the file
            ours = re.escape(c.get("ours", ""))
            theirs = re.escape(c.get("theirs", ""))

            # Build pattern for this specific conflict
            pattern = (
                r'<<<<<<<[^\n]*\n'
                + ours + r'\n'
                + r'(?:\|\|\|\|\|\|\|[^\n]*\n.*?\n)?'  # optional base
                + r'=======\n'
                + theirs + r'\n'
                + r'>>>>>>>[^\n]*\n'
            )

            new_content = re.sub(pattern, resolved_code + "\n", content, count=1, flags=re.DOTALL)

            if new_content != content:
                content = new_content
                resolved_count += 1

        # If simple pattern didn't work, try sequential replacement
        if "<<<<<<" in content:
            # Fallback: replace conflict blocks in order
            blocks = list(CONFLICT_BLOCK.finditer(content))
            resolutions_for_file = [
                c["resolution"]["resolved_code"]
                for c in sorted(file_conflicts, key=lambda x: x.get("line_number", 0))
                if c["resolution"].get("resolved_code")
            ]

            for block, resolution in zip(blocks, resolutions_for_file):
                content = content[:block.start()] + resolution + "\n" + content[block.end():]
                resolved_count += 1

        Path(filepath).write_text(content)
        subprocess.run(["git", "add", filepath], check=True)
        print(f"  ✓ Resolved {filepath}")

    if resolved_count > 0:
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True
        )
        print(f"\nCommitted {resolved_count} resolution(s)")

        # Push
        result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("Pushed to remote")
        else:
            print(f"Push failed (may need permissions): {result.stderr}")
    else:
        print("No resolutions were applied")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--commit-message", default="fix: auto-resolve merge conflicts")
    args = parser.parse_args()
    apply_resolutions(args.result, args.commit_message)
