"""Tests for the main scan entry point."""

import json
import os
import re
from unittest.mock import patch

from scripts.truncation import analyze_truncation
from scripts.compaction import analyze_compaction
from scripts.hygiene import analyze_hygiene
from scripts.config_check import analyze_config


# Re-implement the core scan logic here to avoid argparse/sys.exit issues.
# This tests the aggregation and summary logic without subprocess overhead.
def _run_scan(workspace_path):
    """Run all 4 modules and aggregate, mirroring scan.py's main()."""
    from datetime import datetime, timezone
    from references.constants import DRIFTWATCH_VERSION, OPENCLAW_VERSION_TAG

    def _run_module(func, wp):
        try:
            return func(wp)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    truncation = _run_module(analyze_truncation, workspace_path)
    compaction = _run_module(analyze_compaction, workspace_path)
    hygiene = _run_module(analyze_hygiene, workspace_path)
    config = _run_module(analyze_config, workspace_path)

    # Import summary builder from scan module
    from scripts.scan import _build_summary
    summary = _build_summary(truncation, compaction, hygiene, config)

    return {
        "driftwatch_version": DRIFTWATCH_VERSION,
        "openclaw_version_tag": OPENCLAW_VERSION_TAG,
        "workspace": workspace_path,
        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "truncation": truncation,
        "compaction": compaction,
        "hygiene": hygiene,
        "config": config,
    }


def test_full_scan_valid_json(minimal_workspace):
    """Full scan against a minimal workspace should produce valid, complete output."""
    report = _run_scan(minimal_workspace)

    # Check all required top-level keys
    required_keys = [
        "driftwatch_version", "openclaw_version_tag", "workspace",
        "scan_timestamp", "summary", "truncation", "compaction",
        "hygiene", "config",
    ]
    for key in required_keys:
        assert key in report, f"Missing top-level key: {key}"

    # Verify timestamp format
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report["scan_timestamp"])

    # Verify summary counts are consistent with module findings
    summary = report["summary"]
    assert summary["total_findings"] == (
        summary["critical"] + summary["warning"] + summary["info"]
    )

    # Should serialize to valid JSON
    serialized = json.dumps(report)
    json.loads(serialized)  # round-trip validation


def test_module_error_isolation(minimal_workspace):
    """One module raising an exception shouldn't crash the scan."""
    def broken_compaction(wp):
        raise RuntimeError("Intentional test failure")

    report = _run_scan.__wrapped__(minimal_workspace) if hasattr(_run_scan, '__wrapped__') else None

    # Manually test isolation by running modules with one broken
    from scripts.scan import _run_module, _build_summary

    truncation = _run_module(analyze_truncation, minimal_workspace)
    compaction = _run_module(broken_compaction, minimal_workspace)
    hygiene = _run_module(analyze_hygiene, minimal_workspace)
    config = _run_module(analyze_config, minimal_workspace)

    assert "error" in compaction
    assert "RuntimeError" in compaction["error"]

    # Other modules should have normal results
    assert "error" not in truncation
    assert "error" not in hygiene
    assert "error" not in config

    # Summary should still compute (errored module counts as 1 warning)
    summary = _build_summary(truncation, compaction, hygiene, config)
    assert summary["warning"] >= 1


def test_empty_workspace_no_crash(empty_workspace):
    """Scan against empty workspace — valid output, no exceptions."""
    report = _run_scan(empty_workspace)

    assert report["summary"]["total_findings"] > 0  # should have info/warning findings
    assert "error" not in report["truncation"]
    assert "error" not in report["compaction"]
    assert "error" not in report["hygiene"]
    assert "error" not in report["config"]


def test_realistic_workspace(make_workspace, make_config):
    """Integration test with realistic content, populated config, and edge cases."""
    agents = (
        "# Agent Configuration\n\n"
        "## Session Startup\n"
        "When starting a new session:\n"
        "1. Load the last 3 memory entries for context\n"
        "2. Check for any pending tasks in the task list\n"
        "3. Greet the user and summarize what you remember\n\n"
        "## Delegation Templates\n"
        "### Code Tasks → Sonnet\n"
        "Use sonnet for routine code generation.\n\n"
        "### Research → Haiku\n"
        "Use haiku for quick lookups.\n\n"
        "## Red Lines\n"
        "- Never delete user files without explicit confirmation\n"
        "- Never push to main/master without approval\n"
        "- Never expose API keys in logs, output, or commits\n"
        "- Never skip pre-commit hooks\n\n"
        "## QA Protocol\n"
        "Run tests after every code change. Fix failures before moving on.\n"
    )
    soul = (
        "# Soul\n\n"
        "You are a senior software engineer who values correctness over speed.\n"
        "You write tests before implementing features. You explain your reasoning.\n"
    )
    ws = make_workspace({
        "AGENTS.md": agents,
        "SOUL.md": soul,
        "TOOLS.md": "# Tools\n- git\n- python3\n- node\n- docker\n",
        "IDENTITY.md": "# Identity\nSenior full-stack developer.\n",
        "USER.md": "# User Preferences\n- Concise answers\n- Dark mode\n- Vim keybindings\n",
        "HEARTBEAT.md": "# Heartbeat\nCheck every 5 minutes for idle timeout.\n",
        "BOOTSTRAP.md": "# Bootstrap\nStandard project setup with Python 3.12.\n",
        "MEMORY.md": "# Memory\n- User prefers pytest over unittest\n- Project uses FastAPI\n",
    })

    # Add a config file
    config_dir = os.path.dirname(ws)
    make_config(config_dir, {
        "anthropicApiKey": "sk-ant-real-key-here",
        "model": "claude-sonnet-4-6",
        "agentProvider": "anthropic",
        "heartbeat": True,
        "skills": ["driftwatch"],
        "sandbox": "docker",
    })

    report = _run_scan(ws)

    # No errors in any module
    for module in ["truncation", "compaction", "hygiene", "config"]:
        assert "error" not in report[module], f"{module} had error: {report[module].get('error')}"

    # Truncation: all files should be well under limits
    for f in report["truncation"]["files"]:
        assert f["exists"] is True
        assert f["status"] == "ok"
    assert report["truncation"]["aggregate"]["aggregate_status"] == "ok"

    # Compaction: both anchors found
    for s in report["compaction"]["anchor_sections"]:
        assert s["found"] is True
        assert s["status"] == "ok"

    # Config: all fields present
    assert report["config"]["config_found"] is True
    assert report["config"]["parseable"] is True
    assert report["config"]["fields_missing"] == []

    # Security: API key not in output
    serialized = json.dumps(report)
    assert "sk-ant-real-key-here" not in serialized

    # Hygiene: no critical or warning findings for a clean workspace
    for f in report["hygiene"]["findings"]:
        assert f["severity"] not in ("critical", "warning"), f"Unexpected: {f}"
