"""Small developer SDK for describing extensions without executing plugin code.

Manifests are metadata contracts. Runtime execution still requires an approved,
trusted adapter; arbitrary Python, shell commands, URLs, and import paths are rejected.
"""
import re

FIELD_TYPES = {"string", "integer", "number", "boolean", "object", "array"}
RISKS = {"read", "write", "destructive", "financial"}


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) - {"key", "name", "version", "description", "actions"}:
        raise ValueError("Unsupported manifest shape.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,62}", str(manifest.get("key", ""))):
        raise ValueError("key must be a lowercase identifier of 2-63 characters.")
    if not str(manifest.get("name", "")).strip() or len(str(manifest["name"])) > 120:
        raise ValueError("name must be between 1 and 120 characters.")
    if not str(manifest.get("version", "")).strip() or len(str(manifest["version"])) > 40:
        raise ValueError("version must be between 1 and 40 characters.")
    actions = manifest.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
        raise ValueError("actions must contain 1-30 declarative actions.")
    seen = set()
    for action in actions:
        if not isinstance(action, dict) or set(action) - {"key", "description", "fields", "required", "risk", "side_effecting"}:
            raise ValueError("Unsupported action shape.")
        key = str(action.get("key", ""))
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,79}", key) or key in seen:
            raise ValueError("Action keys must be unique lowercase identifiers.")
        seen.add(key)
        fields = action.get("fields", {})
        required = action.get("required", [])
        if not isinstance(fields, dict) or len(fields) > 40 or not isinstance(required, list):
            raise ValueError("Invalid action fields.")
        if any(not isinstance(item, str) for item in required):
            raise ValueError("Required field names must be strings.")
        if set(required) - set(fields):
            raise ValueError("Required fields must exist in fields.")
        for field, kind in fields.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", str(field)) or not isinstance(kind, str) or kind not in FIELD_TYPES:
                raise ValueError("Unsupported field name/type.")
        risk = action.get("risk", "read")
        side_effecting = action.get("side_effecting", False)
        if not isinstance(risk, str) or risk not in RISKS or not isinstance(side_effecting, bool):
            raise ValueError("Invalid risk/side_effecting value.")
        if risk != "read" and not side_effecting:
            raise ValueError("Non-read actions must be marked side_effecting.")
    return manifest


class ExtensionBuilder:
    """Fluent builder for a versioned, declarative extension manifest."""
    def __init__(self, key, name, version, description=""):
        self._manifest = {"key": key, "name": name, "version": version,
                          "description": description, "actions": []}

    def action(self, key, description, fields=None, required=None, risk="read", side_effecting=False):
        self._manifest["actions"].append({
            "key": key, "description": description, "fields": fields or {},
            "required": required or [], "risk": risk, "side_effecting": side_effecting,
        })
        return self

    def build(self):
        # Return a defensive copy so caller mutation cannot alter builder state.
        import copy
        return copy.deepcopy(validate_manifest(self._manifest))
