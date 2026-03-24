"""Tests for the config existence checks module."""

import json
import os

from scripts.config_check import analyze_config


def test_valid_config_all_fields(make_workspace, make_config):
    """Config with all expected fields — all present, none missing."""
    ws = make_workspace()
    # Place config at the workspace parent dir (where config_check looks)
    config_dir = os.path.dirname(ws)
    make_config(config_dir, {
        "anthropicApiKey": "sk-ant-test-key",
        "model": "claude-sonnet-4-6",
        "agentProvider": "anthropic",
        "heartbeat": True,
        "skills": ["driftwatch"],
        "sandbox": "docker",
    })

    result = analyze_config(ws)

    assert result["config_found"] is True
    assert result["parseable"] is True
    assert all(result["fields_present"].values()), (
        f"Expected all fields present, got: {result['fields_present']}"
    )
    assert result["fields_missing"] == []


def test_missing_config_file(make_workspace):
    """No config file anywhere — should warn, all fields missing."""
    ws = make_workspace()
    result = analyze_config(ws)

    assert result["config_found"] is False
    assert len(result["fields_missing"]) == 6
    assert any(f["severity"] == "warning" for f in result["findings"])


def test_malformed_json(make_workspace, make_config):
    """Invalid JSON in config — parseable should be False."""
    ws = make_workspace()
    config_dir = os.path.dirname(ws)
    make_config(config_dir, raw_text='{"broken": true,}')  # trailing comma

    result = analyze_config(ws)

    assert result["config_found"] is True
    assert result["parseable"] is False
    assert any("parse error" in f["message"].lower() for f in result["findings"])


def test_api_key_never_in_output(make_workspace, make_config):
    """API key values must never appear in the output — security regression test."""
    ws = make_workspace()
    config_dir = os.path.dirname(ws)
    secret = "sk-ant-super-secret-key-12345"
    make_config(config_dir, {
        "anthropicApiKey": secret,
        "model": "claude-sonnet-4-6",
    })

    result = analyze_config(ws)

    # Serialize the entire output and check the secret doesn't appear
    serialized = json.dumps(result)
    assert secret not in serialized, (
        f"API key value leaked into output: {serialized}"
    )
    # Also verify the field is detected as present
    assert result["fields_present"]["anthropicApiKey"] is True
