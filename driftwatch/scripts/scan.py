"""
Driftwatch — Main Entry Point
Runs all 4 analysis modules and aggregates into a single JSON report.

Usage:
    python3 scripts/scan.py [--workspace /path/to/workspace]

Output: JSON to stdout. Exit code always 0 — the agent interprets the JSON.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from references.constants import DRIFTWATCH_VERSION, OPENCLAW_VERSION_TAG


def _run_module(func, workspace_path):
    """Run a single analysis module, returning {"error": "..."} on failure."""
    try:
        return func(workspace_path)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _count_severities_truncation(result):
    """Extract critical/warning/info counts from truncation module output."""
    counts = {"critical": 0, "warning": 0, "info": 0}
    if "error" in result:
        counts["warning"] += 1
        return counts
    for f in result.get("files", []):
        s = f.get("status")
        if s in counts:
            counts[s] += 1
    agg_status = result.get("aggregate", {}).get("aggregate_status")
    if agg_status in counts:
        counts[agg_status] += 1
    return counts


def _count_severities_findings(result):
    """Extract critical/warning/info counts from a module with a 'findings' list."""
    counts = {"critical": 0, "warning": 0, "info": 0}
    if "error" in result:
        counts["warning"] += 1
        return counts
    for f in result.get("findings", []):
        s = f.get("severity")
        if s in counts:
            counts[s] += 1
    return counts


def _build_summary(truncation, compaction, hygiene, config):
    tc = _count_severities_truncation(truncation)
    cc = _count_severities_findings(compaction)
    hc = _count_severities_findings(hygiene)
    fc = _count_severities_findings(config)

    critical = tc["critical"] + cc["critical"] + hc["critical"] + fc["critical"]
    warning  = tc["warning"]  + cc["warning"]  + hc["warning"]  + fc["warning"]
    info     = tc["info"]     + cc["info"]      + hc["info"]     + fc["info"]

    return {
        "critical": critical,
        "warning": warning,
        "info": info,
        "total_findings": critical + warning + info,
    }


def _resolve_workspace(args_workspace):
    """Return workspace path from arg → env var → default, plus a warning if needed."""
    if args_workspace:
        return os.path.expanduser(args_workspace), None
    env = os.environ.get("OPENCLAW_WORKSPACE")
    if env:
        return os.path.expanduser(env), None
    default = os.path.expanduser("~/.openclaw/workspace/")
    return default, None


def main():
    parser = argparse.ArgumentParser(
        prog="scan.py",
        description=(
            "Driftwatch — OpenClaw config health scanner.\n"
            "Checks bootstrap truncation, compaction survival, workspace hygiene,\n"
            "and config completeness. Outputs a JSON report to stdout.\n\n"
            "Workspace resolution order:\n"
            "  1. --workspace flag\n"
            "  2. OPENCLAW_WORKSPACE environment variable\n"
            "  3. ~/.openclaw/workspace/ (default)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workspace",
        metavar="PATH",
        help="Path to your OpenClaw workspace directory (default: ~/.openclaw/workspace/)",
        default=None,
    )
    args = parser.parse_args()

    workspace_path, _warn = _resolve_workspace(args.workspace)
    workspace_path = os.path.abspath(workspace_path)

    # Import modules here so import failures are caught per-module
    def load_truncation(wp):
        from scripts.truncation import analyze_truncation
        return analyze_truncation(wp)

    def load_compaction(wp):
        from scripts.compaction import analyze_compaction
        return analyze_compaction(wp)

    def load_hygiene(wp):
        from scripts.hygiene import analyze_hygiene
        return analyze_hygiene(wp)

    def load_config(wp):
        from scripts.config_check import analyze_config
        return analyze_config(wp)

    truncation = _run_module(load_truncation, workspace_path)
    compaction = _run_module(load_compaction, workspace_path)
    hygiene    = _run_module(load_hygiene,    workspace_path)
    config     = _run_module(load_config,     workspace_path)

    summary = _build_summary(truncation, compaction, hygiene, config)

    report = {
        "driftwatch_version": DRIFTWATCH_VERSION,
        "openclaw_version_tag": OPENCLAW_VERSION_TAG,
        "workspace": workspace_path,
        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "truncation": truncation,
        "compaction": compaction,
        "hygiene": hygiene,
        "config": config,
        "web_dashboard_note": (
            "For visual truncation maps and drift tracking over time, visit bubbuilds.com"
        ),
    }

    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
