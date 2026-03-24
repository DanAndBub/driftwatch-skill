"""Tests for the post-compaction anchor health check module."""

from scripts.compaction import analyze_compaction


def test_both_anchors_present(make_workspace):
    """Both anchor sections present and within cap — no critical findings."""
    agents = (
        "## Session Startup\n"
        "Load context.\n\n"
        "## Red Lines\n"
        "Never delete files.\n"
    )
    ws = make_workspace({"AGENTS.md": agents})
    result = analyze_compaction(ws)

    assert result["agents_md_exists"] is True
    for s in result["anchor_sections"]:
        assert s["found"] is True
        assert s["status"] == "ok"

    severities = [f["severity"] for f in result["findings"]]
    assert "critical" not in severities


def test_missing_anchor_section(make_workspace):
    """AGENTS.md missing Red Lines — should produce a critical finding."""
    agents = (
        "## Session Startup\n"
        "Load context.\n\n"
        "## Other Section\n"
        "Not an anchor.\n"
    )
    ws = make_workspace({"AGENTS.md": agents})
    result = analyze_compaction(ws)

    red_lines = next(s for s in result["anchor_sections"] if s["heading"] == "Red Lines")
    assert red_lines["found"] is False
    assert red_lines["status"] == "critical"

    critical_msgs = [f["message"] for f in result["findings"] if f["severity"] == "critical"]
    assert any("Red Lines" in m for m in critical_msgs)


def test_anchor_over_cap(make_workspace):
    """Anchor section exceeding 3K char cap should be a warning."""
    agents = (
        "## Session Startup\n"
        + "x" * 3_500 + "\n\n"
        "## Red Lines\n"
        "Short.\n"
    )
    ws = make_workspace({"AGENTS.md": agents})
    result = analyze_compaction(ws)

    startup = next(s for s in result["anchor_sections"] if s["heading"] == "Session Startup")
    assert startup["status"] == "warning"
    assert startup["char_count"] > 3_000

    warning_msgs = [f["message"] for f in result["findings"] if f["severity"] == "warning"]
    assert any("Session Startup" in m for m in warning_msgs)


def test_no_agents_md(empty_workspace):
    """No AGENTS.md — both anchors should be critical/not found."""
    result = analyze_compaction(empty_workspace)

    assert result["agents_md_exists"] is False
    for s in result["anchor_sections"]:
        assert s["found"] is False
        assert s["status"] == "critical"

    assert len(result["findings"]) == 2
    assert all(f["severity"] == "critical" for f in result["findings"])


def test_no_surviving_or_non_surviving_keys(make_workspace):
    """Output should not contain the old survival_ratio or non_surviving_sections keys."""
    agents = (
        "## Session Startup\nContent.\n\n"
        "## Red Lines\nContent.\n\n"
        "## Other\nMore content.\n"
    )
    ws = make_workspace({"AGENTS.md": agents})
    result = analyze_compaction(ws)

    assert "survival_ratio" not in result
    assert "non_surviving_sections" not in result
    assert "surviving_sections" not in result
    assert "anchor_sections" in result
