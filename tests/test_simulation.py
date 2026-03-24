"""Tests for truncation danger zone simulation."""

import os

from scripts.simulation import analyze_simulation


def _write_file(workspace, filename, content):
    """Write a file to the test workspace."""
    path = os.path.join(workspace, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def _make_content(target_chars, headings=None):
    """Generate markdown content of exactly target_chars length.

    headings: list of (char_position, heading_text) tuples to insert headings
    at approximate positions.
    """
    if headings is None:
        # Fill with lines of text
        line = "x" * 79 + "\n"  # 80 chars per line
        num_lines = target_chars // 80
        remainder = target_chars - (num_lines * 80)
        content = line * num_lines + "x" * remainder
        assert len(content) == target_chars
        return content

    # Build content with headings at specified positions
    result = []
    current_pos = 0
    heading_list = sorted(headings, key=lambda h: h[0])

    for pos, heading_text in heading_list:
        # Fill up to heading position
        fill_needed = pos - current_pos
        if fill_needed > 0:
            line = "x" * 79 + "\n"
            full_lines = fill_needed // 80
            result.append(line * full_lines)
            current_pos += full_lines * 80
            if current_pos < pos:
                result.append("x" * (pos - current_pos))
                current_pos = pos

        # Insert heading
        heading_line = f"## {heading_text}\n"
        result.append(heading_line)
        current_pos += len(heading_line)

    # Fill remaining
    remaining = target_chars - current_pos
    if remaining > 0:
        line = "x" * 79 + "\n"
        full_lines = remaining // 80
        result.append(line * full_lines)
        current_pos += full_lines * 80
        if current_pos < target_chars:
            result.append("x" * (target_chars - current_pos))

    content = "".join(result)
    # Trim or pad to exact size
    if len(content) > target_chars:
        content = content[:target_chars]
    elif len(content) < target_chars:
        content += "x" * (target_chars - len(content))
    return content


def test_file_at_6k(tmp_path):
    """File at 6K chars — simulation_needed: false."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(6000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is False
    assert agents["status"] == "safe"


def test_file_at_15k(tmp_path):
    """File at 15K chars — under 18K, no danger zone."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(15000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is False
    assert agents["status"] == "approaching"


def test_file_at_19k(tmp_path):
    """File at 19K chars — danger zone exists, status: at_risk."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(19000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    assert agents["status"] == "at_risk"
    dz = agents["danger_zone"]
    assert dz["start_char"] == 14000
    assert dz["end_char"] == 15000  # 19000 - 4000
    assert dz["chars_at_risk"] == 1000


def test_file_at_25k(tmp_path):
    """File at 25K chars — actively truncated."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(25000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    assert agents["status"] == "truncated_now"
    dz = agents["danger_zone"]
    assert dz["start_char"] == 14000
    assert dz["end_char"] == 21000  # 25000 - 4000
    assert dz["chars_truncated"] == 7000


def test_headings_in_danger_zone(tmp_path):
    """Headings in danger zone should be reported in sections_at_risk."""
    ws = str(tmp_path)
    # 19K file with a heading at char ~14500 (in the danger zone)
    content = _make_content(14200)
    content += "\n## Delegation Templates\n"
    content += "x" * 79 + "\n"  # filler in danger zone
    remaining = 19000 - len(content)
    content += "x" * remaining
    _write_file(ws, "AGENTS.md", content)

    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    dz = agents["danger_zone"]
    sections = dz["sections_at_risk"]
    assert len(sections) > 0
    assert any("Delegation Templates" in s["heading"] for s in sections)


def test_no_headings_in_file(tmp_path):
    """File with no headings — empty sections list, line range still reported."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(19000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    dz = agents["danger_zone"]
    assert dz["sections_at_risk"] == []
    assert dz["start_line"] > 0
    assert dz["end_line"] > dz["start_line"]


def test_file_at_18001(tmp_path):
    """File at exactly 18,001 chars — minimal danger zone (1 char)."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(18001))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    assert agents["status"] == "at_risk"
    dz = agents["danger_zone"]
    assert dz["chars_at_risk"] == 1  # 18001 - 4000 = 14001, zone = 14000-14001


def test_file_at_exactly_20k(tmp_path):
    """File at exactly 20,000 chars — at_risk, danger zone = 14000-16000."""
    ws = str(tmp_path)
    _write_file(ws, "AGENTS.md", _make_content(20000))
    result = analyze_simulation(ws)
    agents = next(f for f in result["files"] if f["file"] == "AGENTS.md")
    assert agents["simulation_needed"] is True
    assert agents["status"] == "at_risk"  # At limit, not over
    dz = agents["danger_zone"]
    assert dz["start_char"] == 14000
    assert dz["end_char"] == 16000  # 20000 - 4000
    assert dz["chars_at_risk"] == 2000
