---
name: driftwatch
description: >
  Scan your OpenClaw workspace for config health issues — truncation risks,
  compaction survival problems, workspace hygiene, and missing config fields.
  Use when the operator asks to "scan my config", "check my bootstrap files",
  "analyze my workspace", "check for truncation", "is my config healthy",
  or any question about OpenClaw configuration health and bootstrap file status.
metadata:
  openclaw:
    requires:
      bins:
        - python3
    emoji: "🔍"
    homepage: https://bubbuilds.com
---

# Driftwatch — Config Health Scanner

## Running a Scan

```bash
python3 {baseDir}/scripts/scan.py --workspace <workspace_path>
```

The `--workspace` argument defaults to the agent's own workspace (checks `OPENCLAW_WORKSPACE` env var, then falls back to `~/.openclaw/workspace/`). Most of the time you can omit it:

```bash
python3 {baseDir}/scripts/scan.py
```

The scanner outputs JSON to stdout. Parse it, then present findings conversationally — never dump raw JSON at the operator.

## What the Scanner Checks

Four modules run in sequence. Each contributes its own section to the output JSON:

**truncation** — Measures every bootstrap file's character count against the 20,000-char per-file limit and the 150,000-char aggregate budget. Tracks sequential budget consumption so you can see when MEMORY.md (last in the injection order) is getting starved.

**compaction** — Parses AGENTS.md for the two sections that survive context compaction: `## Session Startup` and `## Red Lines`. Reports what percentage of the file lives outside those sections and will vanish after compaction.

**hygiene** — Checks for duplicate memory files (MEMORY.md and memory.md coexisting), empty bootstrap files, missing subagent-required files, and stray markdown files that the operator may think are being loaded but aren't.

**config** — Confirms openclaw.json exists, is parseable, and has expected top-level fields present. Shallow check only — never reads or reports field values.

## Severity Levels

- **critical** — address immediately. Something is broken or will break. Examples: a compaction-surviving section is missing, aggregate char budget exceeded.
- **warning** — review soon. Not broken yet, but trending bad. Examples: AGENTS.md is 87% of its limit, a surviving section is near its 3,000-char cap.
- **info** — awareness only. Nothing's wrong, just worth knowing. Examples: IDENTITY.md is empty, a non-bootstrap markdown file exists in the workspace root.

## Presenting Findings

Lead with critical findings. If there are none, say so up front — that's the good news. Then work through warnings and info grouped by module.

Translate the numbers into what they mean. Don't say "char_count: 18500, limit: 20000, percent_of_limit: 92.5". Say: "AGENTS.md is at 18,500 characters — 92% of its 20,000-char limit. If you add much more, the tail of the file will start getting cut off."

Keep it brief. One or two sentences per finding. Operators don't need a lecture, they need to know what to do.

**What not to do:** Don't modify any files. Don't attempt to auto-fix anything. Present findings and let the operator decide what to change.

---

## Sample Output Interpretation

Here's what a healthy workspace looks like in the JSON, and how to present it:

```json
{
  "summary": { "critical": 0, "warning": 1, "info": 2 },
  "truncation": {
    "files": [
      {
        "file": "AGENTS.md",
        "char_count": 9200,
        "limit": 20000,
        "percent_of_limit": 46.0,
        "status": "ok"
      }
    ],
    "aggregate": {
      "total_chars": 54000,
      "aggregate_limit": 150000,
      "percent_of_aggregate": 36.0,
      "aggregate_status": "ok"
    }
  },
  "compaction": {
    "surviving_sections": [
      { "heading": "Session Startup", "found": true, "char_count": 1200, "status": "ok" },
      { "heading": "Red Lines", "found": true, "char_count": 800, "status": "ok" }
    ],
    "survival_ratio": 0.22
  },
  "hygiene": {
    "findings": [
      { "severity": "warning", "check": "empty_bootstrap", "message": "IDENTITY.md exists but is empty" }
    ]
  },
  "config": {
    "config_found": true,
    "parseable": true,
    "findings": [{ "severity": "info", "message": "openclaw.json found and parseable. 5 of 6 checked fields present." }]
  }
}
```

**How to present this to the operator:**

> Config looks healthy overall — no critical issues.
>
> One thing to note: IDENTITY.md exists but is empty. It's taking up a bootstrap slot without contributing any instructions. Worth either filling it in or removing it.
>
> Your bootstrap files are using about 54,000 of your 150,000-character aggregate budget (36%) — plenty of room. AGENTS.md is at 46% of its individual limit, well clear of truncation territory.
>
> Both compaction-critical sections are present in AGENTS.md (Session Startup and Red Lines). About 22% of the file's content will survive a compaction event — that's normal.

That's the tone. Factual, brief, actionable.

---

## Notes

- Character counts, not token counts. OpenClaw enforces char-based limits. The scanner reflects that exactly.
- Findings are stamped with the OpenClaw version tag they were calibrated against (currently `2026.03`). If you're on a different version, limits may differ.
- The scanner makes zero network calls. Everything runs locally against your workspace files.
