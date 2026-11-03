"""Validated, privacy-conscious contracts for Asset Provenance and Attribution."""
import hashlib
import json
import re

EVENT_TYPES = frozenset({
    "asset_created", "asset_uploaded", "source_attached",
    "ai_contribution", "agent_contribution", "human_edit",
    "transformation", "review", "approval", "rejection",
    "manifest_generated", "manifest_signed", "verification",
    "export", "deletion_requested",
})
ACTOR_TYPES = frozenset({
    "human", "smart_bethg", "provider", "external_tool", "system", "unknown",
})
MAX_EVENT_PAYLOAD_BYTES = 32 * 1024
MAX_EVENT_DEPTH = 6
MAX_EVENT_NODES = 512
MAX_EVENT_STRING_CHARS = 4000
_SENSITIVE_KEY = re.compile(
    r"(?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"authorization|cookie|private[_-]?key|credential)",
    re.IGNORECASE,
)


def canonical_json(value):
    """Serialize JSON deterministically for stable hashes and signatures."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(value):
    """Return SHA-256 for bytes or UTF-8 encoded text."""
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes):
        raise TypeError("SHA-256 input must be bytes or text.")
    return hashlib.sha256(value).hexdigest()


def _validate_tree(value, depth, counter):
    counter[0] += 1
    if counter[0] > MAX_EVENT_NODES:
        raise ValueError("Provenance event contains too many values.")
    if depth > MAX_EVENT_DEPTH:
        raise ValueError("Provenance event is nested too deeply.")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError("Provenance event keys must be short strings.")
            if _SENSITIVE_KEY.search(key):
                raise ValueError("Sensitive credentials or secrets cannot be recorded in provenance.")
            _validate_tree(child, depth + 1, counter)
    elif isinstance(value, list):
        for child in value:
            _validate_tree(child, depth + 1, counter)
    elif isinstance(value, str):
        if len(value) > MAX_EVENT_STRING_CHARS:
            raise ValueError("Provenance event text field is too long.")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError("Provenance event payload must contain JSON-compatible values.")


def validate_event(event_type, actor_type, payload=None, actor_id=None, actor_label=None):
    if event_type not in EVENT_TYPES:
        raise ValueError("Unsupported provenance event type.")
    if actor_type not in ACTOR_TYPES:
        raise ValueError("Unsupported provenance actor type.")
    if actor_id is not None and (not isinstance(actor_id, str) or len(actor_id) > 128):
        raise ValueError("Provenance actor ID must be at most 128 characters.")
    if actor_label is not None and (not isinstance(actor_label, str) or len(actor_label) > 160):
        raise ValueError("Provenance actor label must be at most 160 characters.")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Provenance event payload must be an object.")
    _validate_tree(payload, 0, [0])
    encoded = canonical_json(payload).encode("utf-8")
    if len(encoded) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError("Provenance event payload exceeds the 32 KiB limit.")
    return payload
