"""Shared fixtures for Driftwatch tests."""

import json
import os
import sys
import pytest

# Add the driftwatch package to sys.path so modules can import references.constants
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "driftwatch"))


@pytest.fixture
def make_workspace(tmp_path):
    """Return a helper that creates bootstrap files in a temp workspace.

    Usage:
        ws = make_workspace({"AGENTS.md": "content", "SOUL.md": "content"})
    """
    def _make(files: dict | None = None):
        ws = tmp_path / "workspace"
        ws.mkdir(exist_ok=True)
        if files:
            for name, content in files.items():
                filepath = ws / name
                filepath.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    filepath.write_bytes(content)
                else:
                    filepath.write_text(content, encoding="utf-8")
        return str(ws)
    return _make


@pytest.fixture
def minimal_workspace(make_workspace):
    """Workspace with all 8 bootstrap files and valid anchor sections."""
    agents = (
        "## Session Startup\n"
        "Load context and greet user.\n\n"
        "## Red Lines\n"
        "Never delete files without confirmation.\n\n"
        "## Other Rules\n"
        "Follow PEP 8.\n"
    )
    return make_workspace({
        "AGENTS.md": agents,
        "SOUL.md": "# Soul\nBe helpful.\n",
        "TOOLS.md": "# Tools\n- git\n- python3\n",
        "IDENTITY.md": "# Identity\nCoding assistant.\n",
        "USER.md": "# User\nPrefers concise answers.\n",
        "HEARTBEAT.md": "# Heartbeat\nCheck every 5 min.\n",
        "BOOTSTRAP.md": "# Bootstrap\nStandard setup.\n",
        "MEMORY.md": "# Memory\n- User likes dark mode.\n",
    })


@pytest.fixture
def empty_workspace(make_workspace):
    """Workspace directory exists but contains no files."""
    return make_workspace()


@pytest.fixture
def make_config(tmp_path):
    """Return a helper that writes an openclaw.json to a given directory."""
    def _make(config_dir: str, data=None, raw_text: str | None = None):
        path = os.path.join(config_dir, "openclaw.json")
        if raw_text is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(raw_text)
        elif data is not None:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        return path
    return _make
