"""Post conflict resolution suggestions as a PR comment."""

from __future__ import annotations

import argparse
import json
import subprocess


def post_comment(result_path: str, repo: str, pr: str, mode: str):
    data = json.load(open(result_path))
    conflicts = data.get("conflicts", [])
    auto_resolvable = data.get("auto_resolvable", 0)
    needs_human = data.get("needs_human_review", 0)
    avg_confidence = data.get("avg_confidence", 0)
    assessment = data.get("assessment", "")
    threshold = data.get("confidence_threshold", 85)

    strategy_emoji = {
        "TAKE_OURS": "⬅️", "TAKE_THEIRS": "➡️",
        "COMBINE": "🔀", "REWRITE": "✏️", "MANUAL": "🖐️"
    }

    lines = []
    lines.append("## 🔀 Conflict Resolver AI\n")

    # Status banner
    if mode == "auto-resolve" and auto_resolvable > 0:
        lines.append(f"✅ **Auto-resolved {auto_resolvable}/{len(conflicts)} conflict(s)**")
        if needs_human > 0:
            lines.append(f" | ⚠️ {needs_human} need manual review")
        lines.append("\n")
    else:
        lines.append(f"Found **{len(conflicts)} conflict(s)** across {len(set(c['file'] for c in conflicts))} file(s)\n")

    # Summary table
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Conflicts | {len(conflicts)} |")
    lines.append(f"| Auto-resolvable (≥{threshold}% confidence) | {auto_resolvable} |")
    lines.append(f"| Needs Human Review | {needs_human} |")
    lines.append(f"| Avg Confidence | {avg_confidence}% |")
    lines.append("")

    # Overall assessment
    if assessment:
        lines.append(f"### Assessment\n{assessment}\n")

    # Per-conflict resolutions
    lines.append("### Resolution Details\n")

    for c in conflicts:
        res = c.get("resolution", {})
        strategy = res.get("strategy", "MANUAL")
        confidence = res.get("confidence", 0)
        reasoning = res.get("reasoning", "")
        risk = res.get("risk_notes", "")
        resolved_code = res.get("resolved_code", "")
        needs_review = res.get("needs_human_review", True)
        emoji = strategy_emoji.get(strategy, "❓")

        conf_bar = "🟢" if confidence >= 85 else "🟡" if confidence >= 60 else "🔴"
        review_badge = " ⚠️" if needs_review else " ✅"

        lines.append(f"<details><summary>{emoji} <code>{c['file']}</code> (line ~{c.get('line_number', '?')}) — {strategy} {conf_bar} {confidence}%{review_badge}</summary>\n")

        lines.append(f"**Strategy:** {strategy} | **Confidence:** {confidence}%")
        lines.append(f"\n**Reasoning:** {reasoning}\n")

        if risk:
            lines.append(f"⚠️ **Risk:** {risk}\n")

        # Show the resolution
        if resolved_code:
            # Detect language from file extension
            ext = c["file"].rsplit(".", 1)[-1] if "." in c["file"] else ""
            lang = {"py": "python", "js": "javascript", "ts": "typescript",
                    "java": "java", "go": "go", "rs": "rust"}.get(ext, "")
            lines.append(f"**Resolved code:**\n```{lang}\n{resolved_code}\n```\n")

        # Show both sides for reference
        lines.append("<details><summary>Original conflict</summary>\n")
        lines.append(f"**Ours ({c.get('ours_label', 'HEAD')}):**\n```\n{c.get('ours', '')}\n```\n")
        lines.append(f"**Theirs ({c.get('theirs_label', 'incoming')}):**\n```\n{c.get('theirs', '')}\n```\n")
        lines.append("</details>\n")
        lines.append("</details>\n")

    # Instructions
    if mode == "suggest":
        lines.append("---")
        lines.append("💡 **To auto-resolve:** Set `mode: auto-resolve` in your workflow.")
        lines.append(f"Conflicts with ≥{threshold}% confidence will be committed automatically.\n")

    lines.append("---")
    lines.append("<sub>🤖 <a href='https://github.com/naveenkumarbaskaran/conflict-resolver-ai'>Conflict Resolver AI</a></sub>")

    body = "\n".join(lines)

    with open("/tmp/conflict_comment.md", "w") as f:
        f.write(body)

    result = subprocess.run(
        ["gh", "pr", "comment", pr, "--repo", repo, "--body-file", "/tmp/conflict_comment.md"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("Posted conflict resolution comment")
    else:
        print(f"Failed: {result.stderr}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--mode", default="suggest")
    args = parser.parse_args()
    post_comment(args.result, args.repo, args.pr, args.mode)
