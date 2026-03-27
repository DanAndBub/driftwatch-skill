# Driftwatch

You wrote 25,000 characters in AGENTS.md. Your agent can only see 14,000 of them.

The truncation is invisible. Your agent doesn't know it's working with an incomplete picture of your instructions — and it won't tell you. It just silently misses the rules at the bottom of your file.

Driftwatch is an OpenClaw skill that checks your workspace for these problems before they cost you bad output.

---

## What It Checks

**Truncation** — Per-file and aggregate character counts against OpenClaw's bootstrap limits. Flags files where content is being cut off.

**Truncation simulation** — Maps exactly which lines fall inside the truncation danger zone. For files approaching the limit, shows what sections get cut first. For files already over the limit, shows what content your agent *cannot see right now*.

**Compaction anchor health** — Checks whether AGENTS.md contains two recommended anchor sections (`## Session Startup` and `## Red Lines`). These are workspace conventions (not source-enforced) that ensure critical instructions are always present. Verifies each is present and within a 3,000-char budget.

**Hygiene** — Duplicate memory files, empty bootstrap slots, files you think are being loaded but aren't, and missing subagent files.

**Drift tracking** — Records scan results over time so you can see how fast your files are growing and how many days until you hit the limit.

**Cron alert mode** — Exit codes and one-line summaries designed for automated monitoring. Drop into crontab or CI pipelines.

---

## Install

```bash
openclaw skills install driftwatch
```

Or via ClawHub:

```bash
clawhub install driftwatch
```

Requires Python 3.9+. No other dependencies.

---

## Usage

Once installed, just say to your agent:

> "scan my config"

Also works: "check my bootstrap files", "analyze my workspace", "am I truncated", "workspace health check", "check for truncation".

Your agent runs the scanner and summarizes findings. Critical issues first, then warnings, then informational notes.

---

## Visual Budget Map

The `--visual` flag outputs a color-coded terminal bar chart of every bootstrap file's character budget:

```
Bootstrap File Budget (27,795 / 150,000 chars = 18.5%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENTS.md     ██████░░░░░░░░░░░░░░   6,325 / 20,000 ( 31.6%)
SOUL.md       ████░░░░░░░░░░░░░░░░   3,912 / 20,000 ( 19.6%)
TOOLS.md      ███░░░░░░░░░░░░░░░░░   2,686 / 20,000 ( 13.4%)
IDENTITY.md   ░░░░░░░░░░░░░░░░░░░░      14 / 20,000 (  0.1%)
USER.md       ██░░░░░░░░░░░░░░░░░░   2,188 / 20,000 ( 10.9%)
HEARTBEAT.md  ████░░░░░░░░░░░░░░░░   4,192 / 20,000 ( 21.0%)
BOOTSTRAP.md  ███░░░░░░░░░░░░░░░░░   3,053 / 20,000 ( 15.3%)
MEMORY.md     █████░░░░░░░░░░░░░░░   5,425 / 20,000 ( 27.1%)

Aggregate     ████░░░░░░░░░░░░░░░░  27,795 / 150,000 ( 18.5%)
```

Green = healthy. Yellow = approaching limit. Red = at risk or actively truncated.

Run with `--visual` for terminal output. Use `--html /path/report.html` for a shareable HTML report with budget bars, simulation details, and trend data when history is available. The HTML report works everywhere — including in-app viewers that don't run JavaScript.

---

## Truncation Simulation

OpenClaw truncates large bootstrap files by keeping the first 14,000 characters (head) and last 4,000 characters (tail). Everything in between is silently cut.

The simulation module maps this cut zone for every file:

- **Under 18,000 chars:** No danger zone — the file fits entirely within head + tail boundaries.
- **18,001–20,000 chars:** Danger zone identified. Shows which sections would be cut first if the file grows any more.
- **Over 20,000 chars:** Actively truncated. Shows exactly which lines and sections your agent cannot see *right now*.

Example finding: "AGENTS.md has 1,200 characters in the danger zone between lines 350–380. The `## Delegation Templates` section falls inside this zone — it would be the first content your agent loses if this file grows past 20,000 chars."

---

## Drift Tracking

Save scan results over time to track how fast your files are growing:

```bash
# Save a baseline
python3 scripts/scan.py --save

# One week later — see how things changed
python3 scripts/scan.py --save --history
```

The `--history` flag adds a `trends` section to the output:

```json
{
  "trends": {
    "scans_analyzed": 7,
    "files": [
      {
        "file": "AGENTS.md",
        "current_chars": 9200,
        "oldest_chars": 6800,
        "delta": 2400,
        "growth_rate_chars_per_day": 48,
        "days_to_limit": 224,
        "trend": "stable"
      }
    ]
  }
}
```

Your agent translates this into: "AGENTS.md has grown by 2,400 characters over the past week — about 48 chars per day. At that rate you have roughly 224 days before it hits the limit."

---

## Cron Integration

Drop Driftwatch into your daily cron for automated monitoring:

```bash
# In crontab (runs every morning at 8am)
0 8 * * * python3 ~/.openclaw/skills/driftwatch/scripts/scan.py --check --save
```

Exit codes:
- `0` — all healthy
- `1` — warnings present
- `2` — criticals present

One-line stdout output:
```
✓ All clear — 8 files healthy, 18.6% aggregate budget used
⚠ Warning — AGENTS.md at 82% of limit
✗ Critical — MEMORY.md TRUNCATED
```

**Note:** Non-zero exit codes are only produced in `--check` mode. Normal scans always exit 0 so agent-facing calls are never misread as script failures.

---

## Example Output

The scanner returns structured JSON. Here's the shape (abbreviated):

```json
{
  "summary": {
    "critical": 1,
    "warning": 3,
    "info": 2
  },
  "truncation": {
    "files": [
      {
        "file": "AGENTS.md",
        "char_count": 18500,
        "limit": 20000,
        "percent_of_limit": 92.5,
        "status": "warning"
      }
    ],
    "aggregate": { "percent_of_aggregate": 36.0, "aggregate_status": "ok" }
  },
  "compaction": {
    "anchor_sections": [
      { "heading": "Session Startup", "found": true, "status": "ok" },
      { "heading": "Red Lines", "found": false, "status": "critical" }
    ]
  },
  "simulation": {
    "files": [
      {
        "file": "AGENTS.md",
        "status": "at_risk",
        "danger_zone": {
          "start_char": 14000,
          "end_char": 14500,
          "chars_at_risk": 500,
          "sections_at_risk": [
            { "heading": "## QA Protocol", "line": 352, "chars_in_zone": 400 }
          ]
        }
      }
    ]
  }
}
```

Your agent translates this into plain language. You don't read JSON — you read: "AGENTS.md is at 92% of its limit and has content in the danger zone. Your Red Lines anchor section is missing entirely, which means post-compaction recovery protocols can't reference it."

---

## Security

**This skill makes zero network calls.**

The scanner uses only Python standard library: `os`, `json`, `argparse`, `re`, `datetime`. Nothing touches a network socket.

Verify yourself:

```bash
grep -rn 'import requests\|import urllib\|import http\|import socket' scripts/
```

That command should return nothing.

**What Driftwatch reads:**

| File | Why |
|------|-----|
| `AGENTS.md` | Truncation risk, anchor section health, danger zone simulation |
| `SOUL.md` | Truncation risk, danger zone simulation |
| `TOOLS.md` | Truncation risk |
| `IDENTITY.md` | Truncation risk |
| `USER.md` | Truncation risk |
| `HEARTBEAT.md` | Truncation risk |
| `BOOTSTRAP.md` | Truncation risk |
| `MEMORY.md` | Truncation risk, duplicate detection |

History data (`~/.driftwatch/`) is stored locally and never transmitted.

---

## Built By

Dan and Bub (and a small AI team). Two people solving the same problem we kept running into ourselves.

Source: [github.com/DanAndBub/driftwatch-skill](https://github.com/DanAndBub/driftwatch-skill)

---

## License

MIT-0 — do whatever you want with it.
