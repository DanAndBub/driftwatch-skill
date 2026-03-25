# Driftwatch Skill v1.1 — Code Review Handoff

## What This Is
A ClawHub skill (Python CLI) that scans an OpenClaw operator's workspace for truncation risks, compaction survival issues, and workspace hygiene problems. v1.1 adds drift tracking, truncation simulation, visual budget maps, and cron-friendly alert mode.

## Repo
`/home/bumby/.openclaw/workspace/driftwatch-skill/`
Branch: `v1.1` (6 sprint commits, not yet merged to master)

## Known Bug (Reason for Review)
**IDENTITY.md trend shows -202,143.4 chars/day "shrinking"** in the HTML report.

Root cause: `trends.py` calculates growth rate as `(current - oldest) / time_span_days`. When the time span between scans is very short (hours, not days), the per-day extrapolation produces absurd numbers. IDENTITY.md went from 634 → 14 chars over ~17 hours, and the math extrapolated that to a daily rate.

**Fix needed:** Minimum time span guard in `trends.py` — don't extrapolate daily rates from sub-day scan intervals. Or cap the rate, or show "insufficient data" when span < 1 day.

The bug is in `driftwatch/scripts/trends.py` in the `analyze_trends()` function.

## Spec
Full v1.1 spec with all task breakdowns: `/home/bumby/.openclaw/workspace/specs/driftwatch-skill-v1.1-spec.md`

## Directory Structure
```
driftwatch-skill/
├── driftwatch/                    # The skill package
│   ├── SKILL.md                   # Agent instructions (266 lines)
│   ├── README.md                  # ClawHub listing / GitHub README (250 lines)
│   ├── scripts/
│   │   ├── scan.py                # Entry point — runs all modules, outputs JSON
│   │   ├── truncation.py          # Bootstrap file size + truncation zone analysis
│   │   ├── compaction.py          # Compaction anchor health check
│   │   ├── hygiene.py             # Workspace file health checks
│   │   ├── simulation.py          # Truncation danger zone mapping (v1.1)
│   │   ├── trends.py              # Drift tracking + trend calculation (v1.1) ← BUG HERE
│   │   ├── visual.py              # Terminal + HTML budget visualization (v1.1)
│   │   └── __init__.py
│   └── references/
│       ├── constants.py           # OpenClaw constants (limits, file order, version)
│       └── __init__.py
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── test_check.py              # --check mode tests (30 tests, v1.1)
│   ├── test_compaction.py         # Compaction tests (5 tests)
│   ├── test_hygiene.py            # Hygiene tests (4 tests)
│   ├── test_scan.py               # Integration tests (4 tests)
│   ├── test_simulation.py         # Simulation tests (8 tests)
│   ├── test_trends.py             # Trend tracking tests (11 tests)
│   ├── test_truncation.py         # Truncation tests (4 tests)
│   ├── test_visual.py             # Visual output tests (8 tests)
│   └── __init__.py
└── HANDOFF.md                     # This file
```

## Key Constraints
- Python stdlib only — zero pip dependencies
- Zero network calls (ClawHub security requirement)
- `{baseDir}` in SKILL.md for runtime path resolution
- Non-zero exit codes ONLY in `--check` mode
- History data stored in `~/.driftwatch/history/`

## Test Suite
```bash
cd /home/bumby/.openclaw/workspace/driftwatch-skill
python3 -m pytest tests/ -v          # 74/74 passing
```

## Key Files to Review
1. **`driftwatch/scripts/trends.py`** — the bug is here, growth rate calculation
2. **`driftwatch/scripts/visual.py`** — generates the HTML report that surfaces the bad data
3. **`driftwatch/scripts/scan.py`** — entry point, wires everything together
4. **`driftwatch/references/constants.py`** — source-verified OpenClaw limits

## Git History (v1.1 branch)
```
cce6cfe docs: update SKILL.md, README.md for v1.1, bump version to 1.1.0 (Sprint 6)
52100f3 feat: add --check mode with exit codes and threshold alerts (Sprint 5)
60739a8 feat: add visual budget map with --visual and --html flags (Sprint 4)
50dbf1e feat: add truncation danger zone simulation (Sprint 3)
c522276 feat: add drift tracking with --save and --history flags (Sprint 2)
bc8e92f feat: remove config_check module (Sprint 1)
```

## Security Audit (Clean)
```bash
grep -rn "import requests\|import urllib\|import http\|import socket" driftwatch/scripts/  # zero hits
grep -rn "os.system\|subprocess\|eval(\|exec(" driftwatch/scripts/                         # zero hits
```
