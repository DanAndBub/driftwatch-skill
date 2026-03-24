"""Driftwatch — Compaction Survival Analysis"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from references.constants import (
    COMPACTION_SURVIVING_HEADINGS,
    COMPACTION_HEADING_CAP_CHARS,
)


def _parse_heading(line: str):
    """Return (level, text) for ## or ### headings only, else None."""
    m = re.match(r'^(#{2,3})\s+(.*)', line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None


def _parse_sections(lines):
    """
    Parse lines into (level, heading_text, content, start_line, end_line) tuples.
    content includes the heading line itself through (not including) the
    next heading of equal or higher level (lower level number).
    start_line and end_line are line indices into the original lines list.
    """
    headings = []
    for i, line in enumerate(lines):
        h = _parse_heading(line)
        if h:
            headings.append((i, h[0], h[1]))

    sections = []
    for idx, (line_i, level, text) in enumerate(headings):
        end_i = len(lines)
        for next_line_i, next_level, _ in headings[idx + 1:]:
            if next_level <= level:
                end_i = next_line_i
                break
        content = "".join(lines[line_i:end_i])
        sections.append((level, text, content, line_i, end_i))

    return sections


def analyze_compaction(workspace_path: str) -> dict:
    agents_path = os.path.join(workspace_path, "AGENTS.md")

    if not os.path.exists(agents_path):
        return {
            "agents_md_exists": False,
            "agents_md_chars": 0,
            "surviving_sections": [
                {
                    "heading": h,
                    "found": False,
                    "heading_level": None,
                    "char_count": 0,
                    "cap": COMPACTION_HEADING_CAP_CHARS,
                    "percent_of_cap": 0,
                    "status": "critical",
                }
                for h in COMPACTION_SURVIVING_HEADINGS
            ],
            "non_surviving_sections": [],
            "total_surviving_chars": 0,
            "total_non_surviving_chars": 0,
            "survival_ratio": 0.0,
            "findings": [
                {
                    "severity": "critical",
                    "message": f"AGENTS.md not found — cannot determine if '{h}' section exists",
                }
                for h in COMPACTION_SURVIVING_HEADINGS
            ],
        }

    with open(agents_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    agents_md_chars = len(raw)
    lines = raw.splitlines(keepends=True)
    sections = _parse_sections(lines)

    # Build lookup: surviving heading name -> (level, content, start, end), case-insensitive
    surviving_lookup = {}
    for level, text, content, start, end in sections:
        for target in COMPACTION_SURVIVING_HEADINGS:
            if text.lower() == target.lower() and target not in surviving_lookup:
                surviving_lookup[target] = (level, content, start, end)

    surviving_sections = []
    surviving_keys = set()

    for target in COMPACTION_SURVIVING_HEADINGS:
        if target in surviving_lookup:
            level, content, _, _ = surviving_lookup[target]
            char_count = len(content)
            cap = COMPACTION_HEADING_CAP_CHARS
            percent_of_cap = round(char_count / cap * 100, 1) if cap > 0 else 0.0
            status = "warning" if char_count > cap else "ok"
            surviving_sections.append({
                "heading": target,
                "found": True,
                "heading_level": level,
                "char_count": char_count,
                "cap": cap,
                "percent_of_cap": percent_of_cap,
                "status": status,
            })
            surviving_keys.add(target.lower())
        else:
            surviving_sections.append({
                "heading": target,
                "found": False,
                "heading_level": None,
                "char_count": 0,
                "cap": COMPACTION_HEADING_CAP_CHARS,
                "percent_of_cap": 0,
                "status": "critical",
            })

    # Build line ranges for surviving sections to detect nested subsections
    surviving_ranges = [
        (surviving_lookup[t][2], surviving_lookup[t][3])
        for t in COMPACTION_SURVIVING_HEADINGS
        if t in surviving_lookup
    ]

    def _is_nested_under_surviving(start):
        """Check if a section's start line falls within a surviving parent's range."""
        for range_start, range_end in surviving_ranges:
            if range_start < start < range_end:
                return True
        return False

    non_surviving_sections = [
        {
            "heading": text,
            "heading_level": level,
            "char_count": len(content),
            "note": "This section will be lost after compaction",
        }
        for level, text, content, start, end in sections
        if text.lower() not in surviving_keys and not _is_nested_under_surviving(start)
    ]

    total_surviving_chars = sum(s["char_count"] for s in surviving_sections if s["found"])
    # Avoid double-counting nested sections: derive non-surviving from the total
    total_non_surviving_chars = max(0, agents_md_chars - total_surviving_chars)
    survival_ratio = round(total_surviving_chars / agents_md_chars, 2) if agents_md_chars > 0 else 0.0

    findings = []

    for s in surviving_sections:
        if not s["found"]:
            findings.append({
                "severity": "critical",
                "message": f"Missing '## {s['heading']}' section — no {s['heading'].lower()} will survive compaction",
            })
        elif s["status"] == "warning":
            findings.append({
                "severity": "warning",
                "message": (
                    f"'{s['heading']}' section is {s['char_count']} chars, exceeding the "
                    f"{COMPACTION_HEADING_CAP_CHARS}-char cap — content will be truncated "
                    f"during compaction re-injection"
                ),
            })
        else:
            findings.append({
                "severity": "info",
                "message": (
                    f"'{s['heading']}' section found and within budget "
                    f"({s['char_count']} of {COMPACTION_HEADING_CAP_CHARS} chars)"
                ),
            })

    if agents_md_chars > 0:
        non_survival_ratio = total_non_surviving_chars / agents_md_chars
        if non_survival_ratio > 0.70:
            pct = round(non_survival_ratio * 100)
            findings.append({
                "severity": "warning",
                "message": (
                    f"{pct}% of AGENTS.md content ({total_non_surviving_chars} chars) will be "
                    f"lost after compaction. Consider moving critical rules into Session Startup "
                    f"or Red Lines sections."
                ),
            })

    return {
        "agents_md_exists": True,
        "agents_md_chars": agents_md_chars,
        "surviving_sections": surviving_sections,
        "non_surviving_sections": non_surviving_sections,
        "total_surviving_chars": total_surviving_chars,
        "total_non_surviving_chars": total_non_surviving_chars,
        "survival_ratio": survival_ratio,
        "findings": findings,
    }
