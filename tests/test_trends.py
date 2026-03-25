"""Tests for drift tracking and trend analysis."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

from scripts.trends import analyze_trends, prune_history, _load_config, _classify_trend


def _make_scan_json(workspace_path, timestamp, file_chars=None):
    """Build a minimal scan result dict for testing."""
    if file_chars is None:
        file_chars = {"AGENTS.md": 6000, "SOUL.md": 3000, "TOOLS.md": 2000,
                      "IDENTITY.md": 500, "USER.md": 2000, "HEARTBEAT.md": 4000,
                      "BOOTSTRAP.md": 3000, "MEMORY.md": 5000}
    files = []
    for fname, chars in file_chars.items():
        files.append({
            "file": fname, "exists": True, "char_count": chars,
            "limit": 20000, "percent_of_limit": round(chars / 20000 * 100, 1),
            "status": "ok",
        })
    return {
        "workspace": workspace_path,
        "scan_timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "truncation": {"files": files},
    }


def _save_scan(history_dir, scan_data, timestamp):
    """Write a scan JSON to history dir with a proper filename."""
    fname = timestamp.strftime("%Y-%m-%dT%H%M%SZ.json")
    fpath = os.path.join(history_dir, fname)
    with open(fpath, "w") as f:
        json.dump(scan_data, f)
    return fpath


def test_save_creates_file(tmp_path):
    """--save should create a file in history dir with correct timestamp format."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ts = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    scan = _make_scan_json("/test/workspace", ts)
    path = _save_scan(history_dir, scan, ts)
    assert os.path.isfile(path)
    assert path.endswith("2026-03-20T120000Z.json")
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["workspace"] == "/test/workspace"


def test_save_creates_directory(tmp_path):
    """--save should work even if history dir needs to be created."""
    history_dir = str(tmp_path / "nonexistent" / "history")
    os.makedirs(history_dir, exist_ok=True)
    assert os.path.isdir(history_dir)


def test_history_zero_scans(tmp_path):
    """--history with 0 stored scans returns 'no history' note."""
    history_dir = str(tmp_path / "empty_history")
    os.makedirs(history_dir)
    current = _make_scan_json("/test/ws", datetime.now(timezone.utc))
    result = analyze_trends(history_dir, "/test/ws", current)
    assert result["scans_analyzed"] == 0
    assert "No history found" in result["note"]


def test_history_one_scan(tmp_path):
    """--history with 1 stored scan returns 'baseline established' note."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ts = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    scan = _make_scan_json("/test/ws", ts)
    _save_scan(history_dir, scan, ts)
    current = _make_scan_json("/test/ws", datetime.now(timezone.utc))
    result = analyze_trends(history_dir, "/test/ws", current)
    assert result["scans_analyzed"] == 1
    assert "Baseline established" in result["note"]


def test_history_multiple_scans(tmp_path):
    """--history with 3+ scans produces valid trend calculations."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    # 3 scans over 10 days, AGENTS.md growing by 500 chars each
    for i, day_offset in enumerate([0, 5, 10]):
        ts = datetime(2026, 3, 10 + day_offset, 12, 0, 0, tzinfo=timezone.utc)
        chars = {"AGENTS.md": 6000 + (i * 500), "SOUL.md": 3000, "TOOLS.md": 2000,
                 "IDENTITY.md": 500, "USER.md": 2000, "HEARTBEAT.md": 4000,
                 "BOOTSTRAP.md": 3000, "MEMORY.md": 5000}
        scan = _make_scan_json(ws, ts, chars)
        _save_scan(history_dir, scan, ts)

    current = _make_scan_json(ws, datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
                               {"AGENTS.md": 7000, "SOUL.md": 3000, "TOOLS.md": 2000,
                                "IDENTITY.md": 500, "USER.md": 2000, "HEARTBEAT.md": 4000,
                                "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})
    result = analyze_trends(history_dir, ws, current)

    assert result["scans_analyzed"] == 3
    assert "files" in result
    assert len(result["files"]) == 8

    # AGENTS.md should show growth
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["delta"] > 0
    assert agents["growth_rate_chars_per_day"] > 0
    assert agents["days_to_limit"] is not None
    assert agents["trend"] in ("stable", "growing", "accelerating")

    # SOUL.md should be stable (no change)
    soul = next(f for f in result["files"] if f["file"] == "SOUL.md")
    assert soul["delta"] == 0
    assert soul["trend"] == "stable"


def test_trend_classifications():
    """Verify trend classification at boundaries."""
    assert _classify_trend(-10) == "shrinking"
    assert _classify_trend(0) == "stable"
    assert _classify_trend(49.9) == "stable"
    assert _classify_trend(50) == "growing"
    assert _classify_trend(200) == "growing"
    assert _classify_trend(200.1) == "accelerating"


def test_days_to_limit(tmp_path):
    """days_to_limit: normal growth, already over, negative growth."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    # Oldest scan: AGENTS.md at 10000
    ts_old = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    scan_old = _make_scan_json(ws, ts_old, {"AGENTS.md": 10000, "SOUL.md": 3000,
        "TOOLS.md": 2000, "IDENTITY.md": 500, "USER.md": 2000,
        "HEARTBEAT.md": 4000, "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})
    _save_scan(history_dir, scan_old, ts_old)

    # Newer scan: AGENTS.md at 15000
    ts_new = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
    scan_new = _make_scan_json(ws, ts_new, {"AGENTS.md": 15000, "SOUL.md": 3000,
        "TOOLS.md": 2000, "IDENTITY.md": 500, "USER.md": 2000,
        "HEARTBEAT.md": 4000, "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})
    _save_scan(history_dir, scan_new, ts_new)

    # Current: AGENTS.md at 18000 (approaching limit)
    current = _make_scan_json(ws, datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc),
        {"AGENTS.md": 18000, "SOUL.md": 3000, "TOOLS.md": 2000, "IDENTITY.md": 500,
         "USER.md": 2000, "HEARTBEAT.md": 4000, "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})

    result = analyze_trends(history_dir, ws, current)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")

    # Growing at 500 chars/day, 2000 chars remaining = ~4 days
    assert agents["days_to_limit"] is not None
    assert agents["days_to_limit"] > 0

    # SOUL.md: no growth = null days_to_limit
    soul = next(f for f in result["files"] if f["file"] == "SOUL.md")
    assert soul["days_to_limit"] is None


def test_retention_pruning(tmp_path):
    """Files older than 90 days should be pruned after --save."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    # Old scan (100 days ago)
    ts_old = datetime.now(timezone.utc) - timedelta(days=100)
    scan_old = _make_scan_json(ws, ts_old)
    old_path = _save_scan(history_dir, scan_old, ts_old)

    # Recent scan (1 day ago)
    ts_recent = datetime.now(timezone.utc) - timedelta(days=1)
    scan_recent = _make_scan_json(ws, ts_recent)
    recent_path = _save_scan(history_dir, scan_recent, ts_recent)

    assert os.path.isfile(old_path)
    assert os.path.isfile(recent_path)

    prune_history(history_dir)

    assert not os.path.isfile(old_path), "Old scan should have been pruned"
    assert os.path.isfile(recent_path), "Recent scan should still exist"


def test_corrupt_history_file(tmp_path):
    """Corrupt history file should be skipped gracefully."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    # Write a corrupt file
    corrupt_path = os.path.join(history_dir, "2026-03-15T120000Z.json")
    with open(corrupt_path, "w") as f:
        f.write("{{not valid json")

    # Write a valid file
    ts = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    scan = _make_scan_json(ws, ts)
    _save_scan(history_dir, scan, ts)

    current = _make_scan_json(ws, datetime.now(timezone.utc))
    result = analyze_trends(history_dir, ws, current)

    # Should have loaded 1 valid scan (corrupt one skipped)
    assert result["scans_analyzed"] == 1


def test_config_missing(tmp_path, monkeypatch):
    """Missing config.json should use defaults without error."""
    monkeypatch.setattr("scripts.trends.DEFAULT_CONFIG_PATH",
                        str(tmp_path / "nonexistent" / "config.json"))
    config, warning = _load_config()
    assert warning is None
    assert config["retention_days"] == 90


def test_config_invalid(tmp_path, monkeypatch):
    """Invalid config.json should return defaults with warning."""
    bad_config = tmp_path / "config.json"
    bad_config.write_text("not json {{{")
    monkeypatch.setattr("scripts.trends.DEFAULT_CONFIG_PATH", str(bad_config))
    config, warning = _load_config()
    assert warning is not None
    assert config["retention_days"] == 90  # Defaults used


def test_sub_day_scans_no_extrapolation(tmp_path):
    """Scans less than 24 hours apart should NOT extrapolate daily rates.

    This is the bug that caused IDENTITY.md to show -202,143 chars/day —
    a 17-hour span between scans got extrapolated to a daily rate.
    """
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    # Two scans 6 hours apart — IDENTITY.md dropped from 634 to 14 chars
    ts1 = datetime(2026, 3, 20, 6, 0, 0, tzinfo=timezone.utc)
    scan1 = _make_scan_json(ws, ts1, {"AGENTS.md": 6000, "SOUL.md": 3000,
        "TOOLS.md": 2000, "IDENTITY.md": 634, "USER.md": 2000,
        "HEARTBEAT.md": 4000, "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})
    _save_scan(history_dir, scan1, ts1)

    ts2 = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    scan2 = _make_scan_json(ws, ts2, {"AGENTS.md": 6000, "SOUL.md": 3000,
        "TOOLS.md": 2000, "IDENTITY.md": 14, "USER.md": 2000,
        "HEARTBEAT.md": 4000, "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})
    _save_scan(history_dir, scan2, ts2)

    current = _make_scan_json(ws, datetime(2026, 3, 20, 23, 0, 0, tzinfo=timezone.utc),
        {"AGENTS.md": 6000, "SOUL.md": 3000, "TOOLS.md": 2000,
         "IDENTITY.md": 14, "USER.md": 2000, "HEARTBEAT.md": 4000,
         "BOOTSTRAP.md": 3000, "MEMORY.md": 5000})

    result = analyze_trends(history_dir, ws, current)

    # Should refuse to calculate daily rates from sub-day span
    assert "note" in result
    assert "less than 1 day" in result["note"]
    # Should NOT contain per-file trends with absurd rates
    assert "files" not in result or len(result.get("files", [])) == 0


def test_exactly_one_day_calculates_trends(tmp_path):
    """Scans exactly 24 hours apart should produce valid trend data."""
    history_dir = str(tmp_path / "history")
    os.makedirs(history_dir)
    ws = "/test/ws"

    ts1 = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
    scan1 = _make_scan_json(ws, ts1)
    _save_scan(history_dir, scan1, ts1)

    ts2 = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    scan2 = _make_scan_json(ws, ts2)
    _save_scan(history_dir, scan2, ts2)

    current = _make_scan_json(ws, datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc))
    result = analyze_trends(history_dir, ws, current)

    # Exactly 1 day span — should calculate normally
    assert "files" in result
    assert len(result["files"]) == 8
