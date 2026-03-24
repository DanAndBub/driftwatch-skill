"""
Driftwatch — Main Entry Point
Runs all 3 analysis modules and aggregates into a single JSON report.

Usage:
    python3 scripts/scan.py [--workspace /path/to/workspace]
    python3 scripts/scan.py [--workspace /path/to/workspace] --save
    python3 scripts/scan.py [--workspace /path/to/workspace] --save --history

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


def _build_summary(truncation, compaction, hygiene):
    tc = _count_severities_truncation(truncation)
    cc = _count_severities_findings(compaction)
    hc = _count_severities_findings(hygiene)

    critical = tc["critical"] + cc["critical"] + hc["critical"]
    warning  = tc["warning"]  + cc["warning"]  + hc["warning"]
    info     = tc["info"]     + cc["info"]      + hc["info"]

    return {
        "critical": critical,
        "warning": warning,
        "info": info,
        "total_findings": critical + warning + info,
    }


def _resolve_workspace(args_workspace):
    """Return workspace path from arg → env var → default."""
    if args_workspace:
        return os.path.expanduser(args_workspace)
    env = os.environ.get("OPENCLAW_WORKSPACE")
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser("~/.openclaw/workspace/")


def main():
    parser = argparse.ArgumentParser(
        prog="scan.py",
        description=(
            "Driftwatch — OpenClaw workspace health scanner.\n"
            "Checks bootstrap truncation, compaction anchor health, and workspace hygiene.\n"
            "Outputs a JSON report to stdout.\n\n"
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
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persist scan results to ~/.driftwatch/history/ for trend tracking",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Include trend analysis from stored scan history",
    )
    args = parser.parse_args()

    workspace_path = _resolve_workspace(args.workspace)
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

    def load_simulation(wp):
        from scripts.simulation import analyze_simulation
        return analyze_simulation(wp)

    truncation = _run_module(load_truncation, workspace_path)
    compaction = _run_module(load_compaction, workspace_path)
    hygiene    = _run_module(load_hygiene,    workspace_path)
    simulation = _run_module(load_simulation, workspace_path)

    summary = _build_summary(truncation, compaction, hygiene)

    scan_timestamp = datetime.now(timezone.utc)

    report = {
        "driftwatch_version": DRIFTWATCH_VERSION,
        "openclaw_version_tag": OPENCLAW_VERSION_TAG,
        "workspace": workspace_path,
        "scan_timestamp": scan_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "truncation": truncation,
        "compaction": compaction,
        "hygiene": hygiene,
        "simulation": simulation,
        "web_dashboard_note": (
            "For visual truncation maps and drift tracking over time, visit bubbuilds.com"
        ),
    }

    # --history: load trends from stored scan history + current live scan
    if args.history:
        history_dir = os.path.expanduser("~/.driftwatch/history")
        try:
            from scripts.trends import analyze_trends
            report["trends"] = analyze_trends(history_dir, workspace_path, report)
        except Exception as e:
            report["trends"] = {"error": f"{type(e).__name__}: {e}"}

    # --save: persist scan to history
    if args.save:
        history_dir = os.path.expanduser("~/.driftwatch/history")
        try:
            os.makedirs(history_dir, exist_ok=True)
            filename = scan_timestamp.strftime("%Y-%m-%dT%H%M%SZ.json")
            save_path = os.path.join(history_dir, filename)
            save_data = dict(report)
            save_data["saved_to"] = save_path
            with open(save_path, "w") as f:
                json.dump(save_data, f, indent=2)
            report["saved_to"] = save_path
        except OSError as e:
            # Save failed — add warning but don't crash
            if "findings" not in report.get("hygiene", {}):
                report.setdefault("save_warning", str(e))
            else:
                report["hygiene"]["findings"].append({
                    "severity": "warning",
                    "check": "save_failed",
                    "message": f"Could not save scan history: {e}",
                })

        # Run retention pruning after save
        try:
            from scripts.trends import prune_history
            prune_history(history_dir)
        except Exception:
            pass  # Retention failure is non-critical

    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
