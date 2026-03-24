"""Tests for visual budget map (terminal and HTML)."""

import os
import re

from scripts.visual import render_terminal, render_html


def _make_scan_result(file_percents=None):
    """Build a minimal scan result for visual rendering."""
    if file_percents is None:
        file_percents = {"AGENTS.md": 31.6, "SOUL.md": 19.6, "TOOLS.md": 10.6}

    files = []
    total = 0
    for fname, pct in file_percents.items():
        chars = int(20000 * pct / 100)
        files.append({
            "file": fname, "exists": True, "char_count": chars,
            "limit": 20000, "percent_of_limit": pct, "status": "ok",
        })
        total += chars

    return {
        "driftwatch_version": "1.1.0",
        "scan_timestamp": "2026-03-24T00:00:00Z",
        "workspace": "/test/workspace",
        "summary": {"critical": 0, "warning": 0, "info": 1, "total_findings": 1},
        "truncation": {
            "files": files,
            "aggregate": {
                "total_chars": total,
                "aggregate_limit": 150000,
                "percent_of_aggregate": round(total / 150000 * 100, 1),
                "aggregate_status": "ok",
            },
        },
        "compaction": {"anchor_sections": []},
        "hygiene": {"findings": []},
        "simulation": {"files": []},
    }


def test_terminal_correct_bar_proportions():
    """Bar proportions should match percentages."""
    result = _make_scan_result({"AGENTS.md": 50.0})
    output = render_terminal(result, use_color=False)
    # 50% of 20 chars = 10 filled blocks
    assert "██████████░░░░░░░░░░" in output


def test_terminal_color_bands():
    """Correct ANSI colors for each severity band."""
    result = _make_scan_result({
        "AGENTS.md": 30.0,    # green
        "SOUL.md": 70.0,      # yellow
        "TOOLS.md": 90.0,     # red
    })
    output = render_terminal(result, use_color=True)
    # Green for <60%
    assert "\033[32m" in output
    # Yellow for 60-80%
    assert "\033[33m" in output
    # Red for 80-100%
    assert "\033[31m" in output


def test_terminal_ansi_stripping():
    """ANSI codes should be stripped when not TTY."""
    result = _make_scan_result()
    output = render_terminal(result, use_color=False)
    assert "\033[" not in output


def test_html_file_created(tmp_path):
    """HTML output should create a file at specified path."""
    result = _make_scan_result()
    html_path = str(tmp_path / "report.html")
    render_html(result, html_path)
    assert os.path.isfile(html_path)


def test_html_valid_structure(tmp_path):
    """HTML should have valid structure (no broken tags)."""
    result = _make_scan_result()
    html_path = str(tmp_path / "report.html")
    render_html(result, html_path)
    with open(html_path) as f:
        content = f.read()
    assert content.startswith("<!DOCTYPE html>")
    assert "</html>" in content
    assert "<body>" in content
    assert "</body>" in content
    # No obvious broken tags
    open_tags = len(re.findall(r"<div", content))
    close_tags = len(re.findall(r"</div>", content))
    assert open_tags == close_tags


def test_html_contains_file_data(tmp_path):
    """HTML should contain expected file names and char counts."""
    result = _make_scan_result({"AGENTS.md": 31.6, "SOUL.md": 19.6})
    html_path = str(tmp_path / "report.html")
    render_html(result, html_path)
    with open(html_path) as f:
        content = f.read()
    assert "AGENTS.md" in content
    assert "SOUL.md" in content


def test_html_with_trends(tmp_path):
    """HTML should include trend data when present."""
    result = _make_scan_result()
    result["trends"] = {
        "scans_analyzed": 5,
        "time_span_days": 10,
        "files": [
            {"file": "AGENTS.md", "growth_rate_chars_per_day": 50,
             "days_to_limit": 200, "trend": "growing"}
        ],
    }
    html_path = str(tmp_path / "report.html")
    render_html(result, html_path)
    with open(html_path) as f:
        content = f.read()
    assert "growing" in content
    assert "scans_analyzed" in content


def test_html_without_trends(tmp_path):
    """HTML should work gracefully without trends data."""
    result = _make_scan_result()
    # No trends key at all
    html_path = str(tmp_path / "report.html")
    render_html(result, html_path)
    with open(html_path) as f:
        content = f.read()
    assert "<!DOCTYPE html>" in content
    # Should not crash
