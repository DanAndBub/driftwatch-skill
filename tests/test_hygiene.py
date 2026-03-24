"""Tests for the workspace hygiene checks module."""

from scripts.hygiene import analyze_hygiene


def test_duplicate_memory_detected(make_workspace):
    """Both MEMORY.md and memory.md present should produce critical finding."""
    ws = make_workspace({
        "MEMORY.md": "# Memory\nEntry 1.\n",
        "memory.md": "# memory\nEntry 2.\n",
    })
    result = analyze_hygiene(ws)

    dup_findings = [f for f in result["findings"] if f["check"] == "duplicate_memory"]
    assert len(dup_findings) == 1
    assert dup_findings[0]["severity"] == "critical"


def test_empty_bootstrap_flagged(make_workspace):
    """Empty bootstrap file should produce a warning."""
    ws = make_workspace({
        "IDENTITY.md": "",  # empty
        "AGENTS.md": "# Agents\nContent.\n",
    })
    result = analyze_hygiene(ws)

    empty_findings = [f for f in result["findings"] if f["check"] == "empty_bootstrap"]
    assert len(empty_findings) == 1
    assert empty_findings[0]["severity"] == "warning"
    assert "IDENTITY.md" in empty_findings[0]["message"]


def test_extra_markdown_detected(make_workspace):
    """Non-bootstrap .md file in workspace root should be flagged as info."""
    ws = make_workspace({
        "AGENTS.md": "# Agents\n",
        "NOTES.md": "# Notes\n",
        "TODO.md": "# TODO\n",
    })
    result = analyze_hygiene(ws)

    extra_findings = [f for f in result["findings"] if f["check"] == "extra_files"]
    assert len(extra_findings) == 1
    assert extra_findings[0]["severity"] == "info"
    assert "NOTES.md" in extra_findings[0]["message"]
    assert "TODO.md" in extra_findings[0]["message"]


def test_clean_workspace_no_warnings(minimal_workspace):
    """Full workspace with all bootstrap files — no critical or warning findings."""
    result = analyze_hygiene(minimal_workspace)

    for f in result["findings"]:
        assert f["severity"] not in ("critical", "warning"), (
            f"Unexpected finding: {f}"
        )
