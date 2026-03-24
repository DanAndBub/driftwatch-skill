"""Tests for the truncation analysis module."""

from scripts.truncation import analyze_truncation


def test_all_files_under_limit(minimal_workspace):
    """Small workspace — all files ok, aggregate ok, no starvation risk."""
    result = analyze_truncation(minimal_workspace)

    for f in result["files"]:
        if f["exists"]:
            assert f["status"] == "ok" or f["status"] == "info", (
                f"{f['file']} unexpected status: {f['status']}"
            )

    assert result["aggregate"]["aggregate_status"] == "ok"
    assert "budget_starvation_risk" not in result["aggregate"]


def test_file_exceeds_per_file_limit(make_workspace):
    """One file over 20K chars should be critical with truncated middle."""
    ws = make_workspace({"AGENTS.md": "x" * 21_000})
    result = analyze_truncation(ws)

    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["status"] == "critical"
    assert agents["char_count"] == 21_000
    assert agents["truncated_middle_chars"] > 0


def test_aggregate_over_budget(make_workspace):
    """8 files each near per-file limit should blow the aggregate budget."""
    files = {}
    bootstrap_order = [
        "AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md",
        "USER.md", "HEARTBEAT.md", "BOOTSTRAP.md", "MEMORY.md",
    ]
    for name in bootstrap_order:
        files[name] = "x" * 19_500  # 8 * 19500 = 156000 > 150000

    ws = make_workspace(files)
    result = analyze_truncation(ws)

    assert result["aggregate"]["aggregate_status"] == "critical"
    assert result["aggregate"]["total_chars"] == 8 * 19_500


def test_starvation_fires_when_tight(make_workspace):
    """Starvation risk should appear only when remaining budget is < 20K."""
    bootstrap_order = [
        "AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md",
        "USER.md", "HEARTBEAT.md", "BOOTSTRAP.md", "MEMORY.md",
    ]
    # First 7 files consume 133K, leaving 17K (< 20K per-file limit)
    files = {name: "x" * 19_000 for name in bootstrap_order[:7]}
    files["MEMORY.md"] = "small"
    ws = make_workspace(files)
    result = analyze_truncation(ws)

    assert "budget_starvation_risk" in result["aggregate"]

    # Now with small files — no starvation
    files_small = {name: "small content" for name in bootstrap_order}
    ws2 = make_workspace(files_small)
    result2 = analyze_truncation(ws2)

    assert "budget_starvation_risk" not in result2["aggregate"]
