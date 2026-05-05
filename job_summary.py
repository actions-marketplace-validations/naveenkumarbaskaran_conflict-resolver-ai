"""Write conflict resolution summary to GitHub Actions job summary."""

from __future__ import annotations

import json
import os
import sys


def write_summary(result_path: str):
    data = json.load(open(result_path))
    conflicts = data.get("conflicts", [])
    auto_resolvable = data.get("auto_resolvable", 0)
    needs_human = data.get("needs_human_review", 0)
    avg_confidence = data.get("avg_confidence", 0)
    mode = data.get("mode", "suggest")
    threshold = data.get("confidence_threshold", 85)

    total = len(conflicts)
    files_affected = len(set(c["file"] for c in conflicts))

    # Strategies breakdown
    strategies = {}
    for c in conflicts:
        strat = c.get("resolution", {}).get("strategy", "MANUAL")
        strategies[strat] = strategies.get(strat, 0) + 1

    lines = []
    lines.append("# 🔀 Conflict Resolution Report\n")

    # Status
    if mode == "auto-resolve" and auto_resolvable > 0:
        lines.append(f"✅ Auto-resolved **{auto_resolvable}** of {total} conflicts\n")
    elif total == 0:
        lines.append("✅ No merge conflicts detected\n")
    else:
        lines.append(f"Found **{total}** conflict(s) in **{files_affected}** file(s)\n")

    # Overview table
    lines.append("## Overview\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Conflicts | {total} |")
    lines.append(f"| Files Affected | {files_affected} |")
    lines.append(f"| Auto-resolvable (≥{threshold}%) | {auto_resolvable} |")
    lines.append(f"| Needs Human Review | {needs_human} |")
    lines.append(f"| Average Confidence | {avg_confidence}% |")
    lines.append(f"| Mode | `{mode}` |")
    lines.append("")

    # Strategy breakdown
    if strategies:
        lines.append("## Resolution Strategies\n")
        lines.append("| Strategy | Count | Description |")
        lines.append("|----------|-------|-------------|")
        desc = {
            "TAKE_OURS": "Keep current branch version",
            "TAKE_THEIRS": "Accept incoming changes",
            "COMBINE": "Merge both sides intelligently",
            "REWRITE": "Rewrite for correctness",
            "MANUAL": "Requires human decision"
        }
        for strat, count in sorted(strategies.items(), key=lambda x: -x[1]):
            lines.append(f"| {strat} | {count} | {desc.get(strat, '')} |")
        lines.append("")

    # Per-file table
    if conflicts:
        lines.append("## Per-Conflict Details\n")
        lines.append("| File | Line | Strategy | Confidence | Status |")
        lines.append("|------|------|----------|------------|--------|")
        for c in conflicts:
            res = c.get("resolution", {})
            strat = res.get("strategy", "MANUAL")
            conf = res.get("confidence", 0)
            human = res.get("needs_human_review", True)
            status = "⚠️ Review" if human else "✅ Resolved"
            conf_emoji = "🟢" if conf >= 85 else "🟡" if conf >= 60 else "🔴"
            lines.append(f"| `{c['file']}` | {c.get('line_number', '?')} | {strat} | {conf_emoji} {conf}% | {status} |")
        lines.append("")

    # Assessment
    assessment = data.get("assessment", "")
    if assessment:
        lines.append(f"## Assessment\n\n{assessment}\n")

    summary = "\n".join(lines)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(summary)
        print("Wrote job summary")
    else:
        print(summary)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: job_summary.py <result.json>")
        sys.exit(1)
    write_summary(sys.argv[1])
