# Driftwatch

You wrote 25,000 characters in AGENTS.md. Your agent can only see 14,000 of them.

The truncation is invisible. Your agent doesn't know it's working with an incomplete picture of your instructions — and it won't tell you. It just silently misses the rules at the bottom of your file.

Driftwatch is an OpenClaw skill that checks your workspace for these problems before they cost you bad output.

---

## What It Checks

**Truncation** — Per-file and aggregate character counts against OpenClaw's bootstrap limits. Flags files where content is being cut off.

**Compaction survival** — Checks which sections of AGENTS.md survive context compaction and which disappear. If your red lines aren't in the right section headings, they vanish silently.

**Hygiene** — Duplicate memory files, empty bootstrap slots, files you think are being loaded but aren't, and missing subagent files.

**Config** — Confirms openclaw.json exists, parses correctly, and has expected fields present.

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

Also works: "check my bootstrap files", "am I truncated", "workspace health check".

Your agent runs the scanner and summarizes the findings. Critical issues first, then warnings, then informational notes.

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
    "aggregate_status": "ok"
  },
  "compaction": {
    "surviving_sections": [
      { "heading": "Session Startup", "found": true, "status": "ok" },
      { "heading": "Red Lines", "found": false, "status": "critical" }
    ]
  }
}
```

Your agent translates this into plain language. You don't read JSON — you read: "Your AGENTS.md is at 92% of its limit, and your Red Lines section is missing entirely, which means none of those rules survive compaction."

---

## Security

**This skill makes zero network calls.**

The scanner uses only Python standard library: `os`, `json`, `argparse`, `re`, `datetime`. Nothing that touches a network socket.

Verify yourself:

```bash
grep -rn 'import requests\|import urllib\|import http\|import socket' scripts/
```

That command should return nothing. If it returns anything, don't install.

**What Driftwatch reads** (and nothing else):

| File | Why |
|------|-----|
| `AGENTS.md` | Checks truncation risk and compaction survival |
| `SOUL.md` | Checks truncation risk |
| `TOOLS.md` | Checks truncation risk |
| `IDENTITY.md` | Checks truncation risk |
| `USER.md` | Checks truncation risk |
| `HEARTBEAT.md` | Checks truncation risk |
| `BOOTSTRAP.md` | Checks truncation risk |
| `MEMORY.md` | Checks truncation risk and duplicate detection |
| `~/.openclaw/openclaw.json` | Confirms config exists and expected fields are present — **never reads or outputs API key values** |

That's it. File sizes and existence, heading structure in AGENTS.md, and config field presence. No content from your files ever leaves your machine.

---

## Web Dashboard

For visual truncation maps and drift tracking over time, visit [bubbuilds.com](https://bubbuilds.com).

The skill gives you the raw findings. The dashboard shows you how they change across sessions.

---

## Built By

Dan and Bub (and a small AI team). Two people solving the same problem we kept running into ourselves.

Source: [github.com/DanAndBub/driftwatch-skill](https://github.com/DanAndBub/driftwatch-skill)

---

## License

MIT-0 — do whatever you want with it.
