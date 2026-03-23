"""
Driftwatch — Config Existence Checks (Simplified)
Task 6: Check openclaw.json existence and field presence.

Reports field presence/absence WITHOUT exposing values.
NEVER includes API key values in output.
Python stdlib only.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from references.constants import DRIFTWATCH_VERSION, OPENCLAW_VERSION_TAG

# Fields to check for existence (not value validation)
FIELDS_TO_CHECK = [
    "anthropicApiKey",
    "model",
    "agentProvider",
    "heartbeat",
    "skills",
    "sandbox",
]

# Nested path alternatives: field_name -> list of paths to check
# Each path is a list of keys to traverse
FIELD_ALTERNATIVES = {
    "anthropicApiKey": [
        ["anthropicApiKey"],
        ["apiKeys", "anthropicApiKey"],
        ["apiKeys", "anthropic"],
    ],
}


def _get_config_paths(workspace_path: str) -> list:
    """Return candidate config file paths in priority order."""
    standard = os.path.expanduser("~/.openclaw/openclaw.json")
    workspace_parent = os.path.join(os.path.dirname(os.path.abspath(workspace_path)), "openclaw.json")

    paths = [standard]
    # Add workspace fallback only if it's different from standard
    if os.path.abspath(workspace_parent) != os.path.abspath(standard):
        paths.append(workspace_parent)

    return paths


def _field_present_in_config(config: dict, field: str) -> bool:
    """
    Check if a field is present in the config dict.
    For fields with known nested alternatives, check all paths.
    Returns True if found at any path.
    """
    if field in FIELD_ALTERNATIVES:
        for path in FIELD_ALTERNATIVES[field]:
            node = config
            found = True
            for key in path:
                if isinstance(node, dict) and key in node:
                    node = node[key]
                else:
                    found = False
                    break
            if found:
                return True
        return False
    else:
        return field in config


def analyze_config(workspace_path: str) -> dict:
    """
    Check openclaw.json existence and required field presence.

    Args:
        workspace_path: Path to the OpenClaw workspace directory.

    Returns:
        dict with config health findings. Never exposes API key values.
    """
    candidate_paths = _get_config_paths(workspace_path)

    config_found = False
    config_path = None
    parseable = False
    parse_error = None
    config_data = None

    # Try candidates in priority order
    for candidate in candidate_paths:
        if os.path.isfile(candidate):
            config_found = True
            config_path = candidate
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                parseable = True
            except json.JSONDecodeError as e:
                parseable = False
                parse_error = f"JSON parse error: {str(e)}"
            except OSError as e:
                parseable = False
                parse_error = f"File read error: {str(e)}"
            break  # Stop at first found config

    findings = []
    fields_present = {}
    fields_missing = []

    if not config_found:
        # Config not found at any candidate path
        findings.append({
            "severity": "warning",
            "message": (
                f"openclaw.json not found. Checked: {', '.join(candidate_paths)}. "
                "Cannot verify config fields."
            ),
        })
        # All fields unknown
        for field in FIELDS_TO_CHECK:
            fields_present[field] = False
            fields_missing.append(field)
    elif not parseable:
        findings.append({
            "severity": "warning",
            "message": f"openclaw.json found at {config_path} but could not be parsed. {parse_error}",
        })
        for field in FIELDS_TO_CHECK:
            fields_present[field] = False
            fields_missing.append(field)
    else:
        # Config found and parseable — check fields
        present_count = 0
        for field in FIELDS_TO_CHECK:
            present = _field_present_in_config(config_data, field)
            fields_present[field] = present
            if present:
                present_count += 1
            else:
                fields_missing.append(field)

        total = len(FIELDS_TO_CHECK)
        summary_msg = f"openclaw.json found and parseable. {present_count} of {total} checked fields present."

        if fields_missing:
            missing_str = ", ".join(fields_missing)
            summary_msg += f" Missing fields: {missing_str}."

        findings.append({
            "severity": "info",
            "message": summary_msg,
        })

    result = {
        "driftwatch_version": DRIFTWATCH_VERSION,
        "openclaw_version_tag": OPENCLAW_VERSION_TAG,
        "config_found": config_found,
        "config_path": config_path,
        "parseable": parseable,
        "fields_present": fields_present,
        "fields_missing": fields_missing,
        "findings": findings,
    }

    # Safety assertion: never include actual values
    # (fields_present only contains booleans — verified by construction above)
    return result
