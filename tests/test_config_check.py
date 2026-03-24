"""Tests for the config existence checks module."""

import json
import os

from scripts.config_check import analyze_config


def _patch_config_paths(monkeypatch, config_path):
    """Monkeypatch _get_config_paths to only return the fixture config location."""
    monkeypatch.setattr(
        "scripts.config_check._get_config_paths",
        lambda workspace_path: [config_path],
    )


def test_valid_config_all_fields(make_workspace, make_config, monkeypatch):
    """Config with all expected fields — all present, none missing."""
    ws = make_workspace()
    config_dir = os.path.dirname(ws)
    config_path = make_config(config_dir, {
        "anthropicApiKey": "sk-ant-test-key",
        "model": "claude-sonnet-4-6",
        "agentProvider": "anthropic",
        "heartbeat": True,
        "skills": ["driftwatch"],
        "sandbox": "docker",
    })
    _patch_config_paths(monkeypatch, config_path)

    result = analyze_config(ws)

    assert result["config_found"] is True
    assert result["parseable"] is True
    assert all(result["fields_present"].values()), (
        f"Expected all fields present, got: {result['fields_present']}"
    )
    assert result["fields_missing"] == []


def test_missing_config_file(make_workspace, monkeypatch):
    """No config file anywhere — should warn, all fields missing."""
    ws = make_workspace()
    # Point at a path that doesn't exist
    _patch_config_paths(monkeypatch, os.path.join(ws, "nonexistent", "openclaw.json"))

    result = analyze_config(ws)

    assert result["config_found"] is False
    assert len(result["fields_missing"]) == 6
    assert any(f["severity"] == "warning" for f in result["findings"])


def test_malformed_json(make_workspace, make_config, monkeypatch):
    """Invalid JSON in config — parseable should be False."""
    ws = make_workspace()
    config_dir = os.path.dirname(ws)
    config_path = make_config(config_dir, raw_text='{"broken": true,}')  # trailing comma
    _patch_config_paths(monkeypatch, config_path)

    result = analyze_config(ws)

    assert result["config_found"] is True
    assert result["parseable"] is False
    assert any("parse error" in f["message"].lower() for f in result["findings"])


def test_api_key_never_in_output(make_workspace, make_config, monkeypatch):
    """API key values must never appear in the output — security regression test."""
    ws = make_workspace()
    config_dir = os.path.dirname(ws)
    secret = "sk-ant-super-secret-key-12345"
    config_path = make_config(config_dir, {
        "anthropicApiKey": secret,
        "model": "claude-sonnet-4-6",
    })
    _patch_config_paths(monkeypatch, config_path)

    result = analyze_config(ws)

    # Serialize the entire output and check the secret doesn't appear
    serialized = json.dumps(result)
    assert secret not in serialized, (
        f"API key value leaked into output: {serialized}"
    )
    # Also verify the field is detected as present
    assert result["fields_present"]["anthropicApiKey"] is True
