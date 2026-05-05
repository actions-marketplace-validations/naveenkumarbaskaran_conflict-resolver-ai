"""Conflict Resolver AI — LLM-powered merge conflict resolution.

Parses conflict markers, understands both sides with context,
and proposes intelligent resolutions with confidence scores.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
API_KEY = os.environ.get("LLM_API_KEY", "")
MODE = os.environ.get("MODE", "suggest")
MAX_CONFLICTS = int(os.environ.get("MAX_CONFLICTS", "20"))
CONFIDENCE_THRESHOLD = int(os.environ.get("CONFIDENCE_THRESHOLD", "85"))
EXTRA_CONTEXT = os.environ.get("EXTRA_CONTEXT", "")

# ── Conflict Parsing ─────────────────────────────────────────────

CONFLICT_PATTERN = re.compile(
    r'<<<<<<<\s*(.*?)\n(.*?)=======\n(.*?)>>>>>>>\s*(.*?)\n',
    re.DOTALL
)


def parse_conflicts(content: str, filename: str) -> list[dict]:
    """Extract conflict blocks from a file with conflict markers."""
    conflicts = []
    lines = content.split("\n")

    i = 0
    conflict_idx = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            ours_label = line[7:].strip()
            ours_lines = []
            theirs_lines = []
            in_ours = True
            base_lines = []
            has_base = False
            i += 1

            while i < len(lines):
                if lines[i].startswith("|||||||"):
                    has_base = True
                    base_lines = ours_lines.copy()
                    ours_lines = []
                    i += 1
                    continue
                if lines[i].startswith("======="):
                    in_ours = False
                    i += 1
                    continue
                if lines[i].startswith(">>>>>>>"):
                    theirs_label = lines[i][7:].strip()

                    # Get surrounding context (5 lines before/after)
                    start = max(0, i - len(ours_lines) - len(theirs_lines) - 10)
                    end = min(len(lines), i + 6)

                    conflicts.append({
                        "file": filename,
                        "conflict_index": conflict_idx,
                        "ours_label": ours_label,
                        "theirs_label": theirs_label,
                        "ours": "\n".join(ours_lines),
                        "theirs": "\n".join(theirs_lines),
                        "base": "\n".join(base_lines) if has_base else None,
                        "context_before": "\n".join(lines[start:max(0, start + 5)]),
                        "context_after": "\n".join(lines[min(len(lines), i+1):end]),
                        "line_number": i - len(ours_lines) - len(theirs_lines) - 2,
                    })
                    conflict_idx += 1
                    break

                if in_ours:
                    ours_lines.append(lines[i])
                else:
                    theirs_lines.append(lines[i])
                i += 1
        i += 1

    return conflicts


# ── LLM Resolution ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert merge conflict resolver. You understand code semantics deeply and can intelligently combine changes from both branches.

For each conflict, analyze:
1. **Intent of each side** — what was each branch trying to accomplish?
2. **Compatibility** — can both changes coexist? Or are they mutually exclusive?
3. **Correctness** — which version is more correct? Or do they need to be combined?
4. **Dependencies** — does the resolution affect other parts of the file?

Resolution strategies:
- **TAKE_OURS**: Keep our branch's version (the current/head branch)
- **TAKE_THEIRS**: Keep their branch's version (the incoming/base branch)
- **COMBINE**: Intelligently merge both changes together
- **REWRITE**: Neither version is ideal; write a new solution

{extra_context}

Return JSON with this structure:
{
  "resolutions": [
    {
      "conflict_index": 0,
      "strategy": "COMBINE|TAKE_OURS|TAKE_THEIRS|REWRITE",
      "resolved_code": "the resolved code (exact text to replace the conflict block)",
      "confidence": 0-100,
      "reasoning": "why this resolution is correct",
      "risk_notes": "any risks or things to verify manually",
      "needs_human_review": false
    }
  ],
  "overall_assessment": "summary of all conflicts and how they relate"
}

CRITICAL RULES:
- resolved_code must be EXACT code — no conflict markers, no placeholders
- confidence < 50 means you're guessing — mark needs_human_review=true
- If changes are unrelated (different functions/blocks), COMBINE them
- If changes conflict on the same line, prefer the more complete version
- Preserve code formatting and indentation of the surrounding code
- If imports conflict, include ALL unique imports from both sides"""


def resolve_conflicts(conflicts: list[dict]) -> list[dict]:
    """Send conflicts to LLM for resolution."""
    import litellm
    litellm.drop_params = True

    user_prompt = "Resolve these merge conflicts:\n\n"

    for c in conflicts:
        user_prompt += f"### Conflict #{c['conflict_index']} in `{c['file']}` (line ~{c['line_number']})\n\n"

        if c.get("context_before"):
            user_prompt += f"**Context before:**\n```\n{c['context_before']}\n```\n\n"

        user_prompt += f"**OURS ({c['ours_label']}):**\n```\n{c['ours']}\n```\n\n"

        if c.get("base"):
            user_prompt += f"**BASE (common ancestor):**\n```\n{c['base']}\n```\n\n"

        user_prompt += f"**THEIRS ({c['theirs_label']}):**\n```\n{c['theirs']}\n```\n\n"

        if c.get("context_after"):
            user_prompt += f"**Context after:**\n```\n{c['context_after']}\n```\n\n"

        user_prompt += "---\n\n"

    system = SYSTEM_PROMPT.format(
        extra_context=f"Project context: {EXTRA_CONTEXT}" if EXTRA_CONTEXT else ""
    )

    response = litellm.completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        api_key=API_KEY,
        temperature=0.1,
        response_format={"type": "json_object"},
        timeout=90,
    )

    text = response.choices[0].message.content or "{}"
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        result = json.loads(text[start:end]) if start >= 0 else {}

    return result.get("resolutions", []), result.get("overall_assessment", "")


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conflict-files", required=True, help="File listing conflicted paths")
    parser.add_argument("--conflict-dir", required=True, help="Dir with conflict file copies")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    # Read conflict files
    conflict_file_list = Path(args.conflict_files).read_text().strip().split("\n")
    conflict_file_list = [f.strip() for f in conflict_file_list if f.strip()]

    if MAX_CONFLICTS > 0:
        conflict_file_list = conflict_file_list[:MAX_CONFLICTS]

    print(f"Processing {len(conflict_file_list)} conflicted files...")

    # Parse all conflicts
    all_conflicts = []
    for filepath in conflict_file_list:
        safe_name = filepath.replace("/", "_")
        conflict_path = Path(args.conflict_dir) / safe_name
        if not conflict_path.exists():
            print(f"  Warning: {conflict_path} not found, skipping")
            continue

        content = conflict_path.read_text(errors="replace")
        file_conflicts = parse_conflicts(content, filepath)
        all_conflicts.extend(file_conflicts)
        print(f"  {filepath}: {len(file_conflicts)} conflict(s)")

    if not all_conflicts:
        print("No conflict markers found in files")
        result = {"conflicts": [], "resolutions": [], "resolved": 0}
        with open(args.output, "w") as f:
            json.dump(result, f)
        return

    print(f"\nTotal conflicts: {len(all_conflicts)}")
    print("Sending to LLM for resolution...")

    # Resolve in batches if needed (max 10 per call)
    all_resolutions = []
    assessment = ""
    batch_size = 10

    for i in range(0, len(all_conflicts), batch_size):
        batch = all_conflicts[i:i + batch_size]
        try:
            resolutions, batch_assessment = resolve_conflicts(batch)
            all_resolutions.extend(resolutions)
            if batch_assessment:
                assessment += batch_assessment + "\n"
        except Exception as e:
            print(f"  Warning: LLM call failed for batch {i//batch_size}: {e}")
            for c in batch:
                all_resolutions.append({
                    "conflict_index": c["conflict_index"],
                    "strategy": "MANUAL",
                    "resolved_code": "",
                    "confidence": 0,
                    "reasoning": f"LLM resolution failed: {e}",
                    "risk_notes": "Requires manual resolution",
                    "needs_human_review": True,
                })

    # Match resolutions back to conflicts
    resolution_map = {r["conflict_index"]: r for r in all_resolutions}
    for c in all_conflicts:
        idx = c["conflict_index"]
        if idx in resolution_map:
            c["resolution"] = resolution_map[idx]
        else:
            c["resolution"] = {
                "strategy": "MANUAL",
                "resolved_code": "",
                "confidence": 0,
                "reasoning": "No resolution generated",
                "needs_human_review": True,
            }

    # Stats
    auto_resolvable = [
        c for c in all_conflicts
        if c["resolution"].get("confidence", 0) >= CONFIDENCE_THRESHOLD
        and not c["resolution"].get("needs_human_review", True)
    ]
    avg_confidence = (
        sum(c["resolution"].get("confidence", 0) for c in all_conflicts) // len(all_conflicts)
        if all_conflicts else 0
    )

    result = {
        "conflicts": all_conflicts,
        "resolutions_count": len(all_resolutions),
        "auto_resolvable": len(auto_resolvable),
        "needs_human_review": len(all_conflicts) - len(auto_resolvable),
        "avg_confidence": avg_confidence,
        "assessment": assessment.strip(),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "mode": MODE,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Set outputs
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as out:
            out.write(f"conflicts_found={len(all_conflicts)}\n")
            out.write(f"conflicts_resolved={len(auto_resolvable)}\n")
            out.write(f"confidence_avg={avg_confidence}\n")
            out.write(f"result_json={json.dumps(result, default=str)}\n")

    print(f"\nResults: {len(all_conflicts)} conflicts, {len(auto_resolvable)} auto-resolvable (>={CONFIDENCE_THRESHOLD}% confidence)")


if __name__ == "__main__":
    main()
