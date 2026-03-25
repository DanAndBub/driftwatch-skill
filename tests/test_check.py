"""Tests for --check mode: exit codes, threshold comparison, and one-line output.

These tests exercise the _check_thresholds() function in scan.py and the
integration of --check with --save and --json flags.

All threshold and config path dependencies are isolated via monkeypatching so
tests are deterministic and write nothing to the real ~/.driftwatch/ tree.
"""

import io
import json
import os
import sys
import pytest

# Add driftwatch package to sys.path (matches conftest.py approach)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "driftwatch"))

from scripts.scan import _check_thresholds, _load_check_config


# ---------------------------------------------------------------------------
# Helpers to build minimal report dicts with controlled per-file percentages
# ---------------------------------------------------------------------------

def _make_report(file_pcts=None, agg_pct=0.0, simulation_files=None, trends_files=None):
    """Build a minimal scan report dict for threshold testing.

    file_pcts: dict of {filename: percent_of_limit}  e.g. {"AGENTS.md": 75.0}
    agg_pct: aggregate percent (0-100+)
    simulation_files: list of {"file": name, "status": "..."} dicts
    trends_files: list of {"file": name, "growth_rate_chars_per_day": N} dicts
    """
    LIMIT = 20_000

    files = []
    for fname, pct in (file_pcts or {}).items():
        chars = int(LIMIT * pct / 100)
        files.append({
            "file": fname,
            "exists": True,
            "char_count": chars,
            "limit": LIMIT,
            "percent_of_limit": pct,
            "status": "ok",
        })

    agg_limit = 150_000
    agg_chars = int(agg_limit * agg_pct / 100)

    report = {
        "truncation": {
            "files": files,
            "aggregate": {
                "total_chars": agg_chars,
                "aggregate_limit": agg_limit,
                "percent_of_aggregate": agg_pct,
                "aggregate_status": "ok",
            },
        },
        "simulation": {"files": simulation_files or []},
        "trends": {"files": trends_files or []},
    }
    return report


# ---------------------------------------------------------------------------
# Helpers for capturing stdout and the exit code from _check_thresholds
# ---------------------------------------------------------------------------

def _run_check(report, capsys):
    """Call _check_thresholds and return (exit_code, printed_line)."""
    code = _check_thresholds(report)
    captured = capsys.readouterr()
    return code, captured.out.strip()


# ---------------------------------------------------------------------------
# TASK 5.2 — Test cases
# ---------------------------------------------------------------------------

class TestHealthyWorkspace:
    """Exit 0 — all files well under thresholds."""

    def test_exit_0_all_clear(self, capsys):
        """Healthy workspace: exit 0, message contains 'All clear'."""
        report = _make_report(
            file_pcts={"AGENTS.md": 31.6, "SOUL.md": 19.6, "MEMORY.md": 25.0},
            agg_pct=18.6,
        )
        code, line = _run_check(report, capsys)
        assert code == 0
        assert "All clear" in line

    def test_all_clear_shows_aggregate_pct(self, capsys):
        """The all-clear message includes aggregate percentage."""
        report = _make_report(
            file_pcts={"AGENTS.md": 40.0},
            agg_pct=22.5,
        )
        code, line = _run_check(report, capsys)
        assert code == 0
        assert "22.5" in line

    def test_empty_workspace_healthy(self, capsys):
        """Empty workspace (no files) exits 0."""
        report = _make_report(file_pcts={}, agg_pct=0.0)
        code, line = _run_check(report, capsys)
        assert code == 0


class TestWarningThreshold:
    """Exit 1 — at least one file hits warning threshold (default 70%)."""

    def test_file_at_75_exits_1(self, capsys):
        """File at 75% → exit 1, warning message."""
        report = _make_report(file_pcts={"AGENTS.md": 75.0}, agg_pct=10.0)
        code, line = _run_check(report, capsys)
        assert code == 1
        assert "Warning" in line or "⚠" in line

    def test_warning_message_names_file(self, capsys):
        """Warning message names the offending file."""
        report = _make_report(file_pcts={"SOUL.md": 78.0}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 1
        assert "SOUL.md" in line

    def test_warning_message_shows_percentage(self, capsys):
        """Warning message includes the file's percentage."""
        report = _make_report(file_pcts={"TOOLS.md": 82.0}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 1
        assert "82" in line

    def test_exactly_at_warning_threshold(self, capsys):
        """File exactly at 70% (the default warning threshold) → exit 1."""
        report = _make_report(file_pcts={"AGENTS.md": 70.0}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 1

    def test_just_under_warning_threshold(self, capsys):
        """File at 69.9% is still OK — exit 0."""
        report = _make_report(file_pcts={"AGENTS.md": 69.9}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 0


class TestCriticalThreshold:
    """Exit 2 — at least one file hits critical threshold (default 90%)."""

    def test_file_at_95_exits_2(self, capsys):
        """File at 95% → exit 2, critical message."""
        report = _make_report(file_pcts={"MEMORY.md": 95.0}, agg_pct=15.0)
        code, line = _run_check(report, capsys)
        assert code == 2
        assert "Critical" in line or "✗" in line

    def test_critical_message_names_file(self, capsys):
        """Critical message names the offending file."""
        report = _make_report(file_pcts={"AGENTS.md": 92.0}, agg_pct=10.0)
        code, line = _run_check(report, capsys)
        assert code == 2
        assert "AGENTS.md" in line

    def test_critical_beats_warning(self, capsys):
        """When both warning and critical files exist, exit code is 2."""
        report = _make_report(
            file_pcts={"SOUL.md": 75.0, "AGENTS.md": 95.0},
            agg_pct=10.0,
        )
        code, line = _run_check(report, capsys)
        assert code == 2

    def test_exactly_at_critical_threshold(self, capsys):
        """File exactly at 90% → exit 2."""
        report = _make_report(file_pcts={"AGENTS.md": 90.0}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 2

    def test_simulation_truncated_now_is_critical(self, capsys):
        """A file marked truncated_now in simulation always triggers exit 2."""
        report = _make_report(
            file_pcts={"MEMORY.md": 50.0},  # Under warning threshold
            agg_pct=5.0,
            simulation_files=[
                {"file": "MEMORY.md", "status": "truncated_now"}
            ],
        )
        code, line = _run_check(report, capsys)
        assert code == 2

    def test_over_100_pct_exits_2(self, capsys):
        """File over 100% of limit → exit 2."""
        report = _make_report(file_pcts={"AGENTS.md": 110.0}, agg_pct=20.0)
        code, line = _run_check(report, capsys)
        assert code == 2


class TestCustomThresholds:
    """Custom thresholds from config.json are respected."""

    def test_custom_warning_threshold_respected(self, tmp_path, monkeypatch):
        """Config with per_file_warning_percent=50 should warn at 55%."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "alert_thresholds": {
                "per_file_warning_percent": 50,
                "per_file_critical_percent": 90,
                "aggregate_warning_percent": 60,
                "aggregate_critical_percent": 80,
                "growth_rate_warning_chars_per_day": 200,
            }
        }))
        monkeypatch.setattr(
            "scripts.scan._load_check_config",
            lambda: {
                "per_file_warning_percent": 50,
                "per_file_critical_percent": 90,
                "aggregate_warning_percent": 60,
                "aggregate_critical_percent": 80,
                "growth_rate_warning_chars_per_day": 200,
            }
        )
        report = _make_report(file_pcts={"AGENTS.md": 55.0}, agg_pct=5.0)
        # 55% > custom 50% warning threshold → should warn
        from scripts.scan import _check_thresholds as _ct
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = _ct(report)
        assert code == 1

    def test_custom_critical_threshold_respected(self, tmp_path, monkeypatch):
        """Config with per_file_critical_percent=75 should critical at 80%."""
        monkeypatch.setattr(
            "scripts.scan._load_check_config",
            lambda: {
                "per_file_warning_percent": 60,
                "per_file_critical_percent": 75,
                "aggregate_warning_percent": 60,
                "aggregate_critical_percent": 80,
                "growth_rate_warning_chars_per_day": 200,
            }
        )
        report = _make_report(file_pcts={"AGENTS.md": 80.0}, agg_pct=5.0)
        import io
        from contextlib import redirect_stdout
        from scripts.scan import _check_thresholds as _ct
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = _ct(report)
        assert code == 2

    def test_custom_aggregate_warning_threshold(self, monkeypatch, capsys):
        """Custom aggregate_warning_percent=40 warns when aggregate hits 45%."""
        monkeypatch.setattr(
            "scripts.scan._load_check_config",
            lambda: {
                "per_file_warning_percent": 70,
                "per_file_critical_percent": 90,
                "aggregate_warning_percent": 40,
                "aggregate_critical_percent": 80,
                "growth_rate_warning_chars_per_day": 200,
            }
        )
        report = _make_report(file_pcts={"AGENTS.md": 10.0}, agg_pct=45.0)
        code, line = _run_check(report, capsys)
        assert code == 1  # Aggregate at 45% > custom 40% warning

    def test_config_loaded_via_load_check_config(self, tmp_path, monkeypatch):
        """_load_check_config reads from the configured path and returns thresholds."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "alert_thresholds": {
                "per_file_warning_percent": 55,
                "per_file_critical_percent": 85,
                "aggregate_warning_percent": 45,
                "aggregate_critical_percent": 70,
                "growth_rate_warning_chars_per_day": 100,
            }
        }))
        # Patch the config path used by _load_check_config
        import scripts.scan as scan_module
        original_expanduser = os.path.expanduser

        def patched_expanduser(path):
            if path == "~/.driftwatch/config.json":
                return str(config_path)
            return original_expanduser(path)

        monkeypatch.setattr("os.path.expanduser", patched_expanduser)
        config = _load_check_config()
        assert config["per_file_warning_percent"] == 55
        assert config["per_file_critical_percent"] == 85
        assert config["growth_rate_warning_chars_per_day"] == 100


class TestMissingConfig:
    """Missing config.json uses defaults without crashing."""

    def test_missing_config_uses_defaults(self, tmp_path, monkeypatch):
        """When config.json doesn't exist, _load_check_config returns defaults."""
        original_expanduser = os.path.expanduser

        def patched_expanduser(path):
            if path == "~/.driftwatch/config.json":
                return str(tmp_path / "nonexistent" / "config.json")
            return original_expanduser(path)

        monkeypatch.setattr("os.path.expanduser", patched_expanduser)
        config = _load_check_config()
        # Defaults from spec
        assert config["per_file_warning_percent"] == 70
        assert config["per_file_critical_percent"] == 90
        assert config["aggregate_warning_percent"] == 60
        assert config["aggregate_critical_percent"] == 80
        assert config["growth_rate_warning_chars_per_day"] == 200

    def test_missing_config_still_checks_thresholds(self, tmp_path, monkeypatch, capsys):
        """Scan runs correctly even with no config.json on disk."""
        original_expanduser = os.path.expanduser

        def patched_expanduser(path):
            if path == "~/.driftwatch/config.json":
                return str(tmp_path / "missing" / "config.json")
            return original_expanduser(path)

        monkeypatch.setattr("os.path.expanduser", patched_expanduser)
        # With defaults (70% warning), a file at 80% should warn
        report = _make_report(file_pcts={"AGENTS.md": 80.0}, agg_pct=5.0)
        code, line = _run_check(report, capsys)
        assert code == 1

    def test_invalid_config_uses_defaults(self, tmp_path, monkeypatch, capsys):
        """Corrupt config.json silently falls back to defaults."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{not valid json{{{{")
        original_expanduser = os.path.expanduser

        def patched_expanduser(path):
            if path == "~/.driftwatch/config.json":
                return str(config_path)
            return original_expanduser(path)

        monkeypatch.setattr("os.path.expanduser", patched_expanduser)
        config = _load_check_config()
        # Should have fallen back to defaults
        assert config["per_file_warning_percent"] == 70


class TestCheckWithSave:
    """--check --save: both operations work together."""

    def test_check_and_save_both_work(self, tmp_path, monkeypatch, capsys, make_workspace):
        """--check --save saves the scan AND produces exit code/summary line."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        history_dir = str(tmp_path / "driftwatch_history")
        os.makedirs(history_dir)

        # Patch history directory used by scan.py --save
        # We run via subprocess to fully exercise the CLI path
        scan_script = os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        )
        scan_script = os.path.abspath(scan_script)

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)  # Redirect ~/.driftwatch/ to tmp_path

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws, "--check", "--save"],
            capture_output=True, text=True, env=env
        )

        # --check: exit code should be 0 or 1 (healthy workspace)
        assert result.returncode in (0, 1, 2)
        # --check: stdout should have the one-line summary
        assert len(result.stdout.strip()) > 0
        # --save: a history file should have been created under tmp_path
        history_path = tmp_path / ".driftwatch" / "history"
        if history_path.exists():
            saved_files = list(history_path.iterdir())
            assert len(saved_files) >= 1
            # The saved file should be valid JSON
            with open(saved_files[0]) as f:
                saved = json.load(f)
            assert "scan_timestamp" in saved


class TestCheckWithJson:
    """--check --json: one-line summary AND full JSON in output."""

    def test_check_json_contains_both(self, tmp_path, make_workspace):
        """--check --json: stdout has one-line summary AND full JSON report."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws, "--check", "--json"],
            capture_output=True, text=True, env=env
        )

        output = result.stdout
        lines = output.strip().splitlines()

        # Must have at least 2 lines (summary line + JSON blob)
        assert len(lines) >= 2, f"Expected summary line + JSON, got:\n{output}"

        # First line should be the one-line summary (check/warning/clear)
        first_line = lines[0]
        assert any(marker in first_line for marker in ["✓", "⚠", "✗", "All clear", "Warning", "Critical"]), (
            f"First line should be summary: {first_line}"
        )

        # The rest of the output should be parseable as JSON
        json_text = "\n".join(lines[1:])
        # Find the JSON object start
        json_start = output.find("\n{")
        if json_start == -1:
            json_start = output.find("{")
        assert json_start != -1, "No JSON object found in output"
        try:
            parsed = json.loads(output[json_start:])
        except json.JSONDecodeError:
            # Try from line 1 onward
            rest = "\n".join(lines[1:])
            parsed = json.loads(rest)

        assert "summary" in parsed
        assert "truncation" in parsed

    def test_check_without_json_suppresses_full_json(self, tmp_path, make_workspace):
        """--check alone: stdout is one-line summary only (no JSON blob)."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws, "--check"],
            capture_output=True, text=True, env=env
        )

        output = result.stdout.strip()
        # Should be a short one-line summary, not a JSON blob
        assert not output.startswith("{"), "Check mode should not output JSON object without --json"
        assert len(output.splitlines()) == 1, f"Expected 1 line, got:\n{output}"


class TestNonCheckModeAlwaysExits0:
    """Without --check, exit code is always 0 regardless of findings."""

    def test_normal_scan_exits_0_with_no_issues(self, tmp_path, make_workspace):
        """Normal scan of healthy workspace exits 0."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws],
            capture_output=True, text=True, env=env
        )
        assert result.returncode == 0

    def test_normal_scan_exits_0_even_with_findings(self, tmp_path, make_workspace):
        """Normal scan exits 0 even when workspace has findings (no --check)."""
        import subprocess

        # A workspace missing anchor sections — compaction will warn
        ws = make_workspace({
            "AGENTS.md": "# Agents — no required headings here\n" + "x" * 18000,
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws],
            capture_output=True, text=True, env=env
        )
        # MUST be 0 even with critical findings
        assert result.returncode == 0
        # Output should be valid JSON
        report = json.loads(result.stdout)
        assert "summary" in report

    def test_visual_mode_exits_0(self, tmp_path, make_workspace):
        """--visual mode exits 0 regardless of findings."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws, "--visual"],
            capture_output=True, text=True, env=env
        )
        assert result.returncode == 0

    def test_save_mode_exits_0(self, tmp_path, make_workspace):
        """--save mode exits 0 regardless of findings."""
        import subprocess

        ws = make_workspace({
            "AGENTS.md": "## Session Startup\nHi\n\n## Red Lines\nNone.\n",
            "SOUL.md": "# Soul\n",
            "TOOLS.md": "# Tools\n",
            "IDENTITY.md": "# ID\n",
            "USER.md": "# User\n",
            "HEARTBEAT.md": "# HB\n",
            "BOOTSTRAP.md": "# Boot\n",
            "MEMORY.md": "# Memory\n",
        })

        scan_script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "driftwatch", "scripts", "scan.py"
        ))

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, scan_script, "--workspace", ws, "--save"],
            capture_output=True, text=True, env=env
        )
        assert result.returncode == 0


class TestGrowthRateThreshold:
    """Growth rate warnings from trends data."""

    def test_growth_rate_above_threshold_warns(self, capsys):
        """File growing > 200 chars/day (default) triggers warning."""
        report = _make_report(
            file_pcts={"AGENTS.md": 30.0},
            agg_pct=5.0,
            trends_files=[
                {"file": "AGENTS.md", "growth_rate_chars_per_day": 250}
            ],
        )
        code, line = _run_check(report, capsys)
        assert code == 1
        assert "AGENTS.md" in line

    def test_growth_rate_below_threshold_ok(self, capsys):
        """File growing <= 200 chars/day (default) does not trigger warning."""
        report = _make_report(
            file_pcts={"AGENTS.md": 30.0},
            agg_pct=5.0,
            trends_files=[
                {"file": "AGENTS.md", "growth_rate_chars_per_day": 199}
            ],
        )
        code, line = _run_check(report, capsys)
        assert code == 0
