"""Typed, fail-closed registry for connector actions."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CapabilitySpec:
    connector_key: str
    action: str
    description: str
    input_fields: dict[str, type]
    required_fields: frozenset[str]
    risk: str = "read"
    side_effecting: bool = False
    @property
    def permission(self):
        return f"{self.connector_key}.{self.action}"

def default_capabilities():
    return [
        CapabilitySpec("github", "issues.list", "List repository issues.", {"repository": str, "state": str, "limit": int}, frozenset({"repository"})),
        CapabilitySpec("github", "issues.create", "Create a repository issue.", {"repository": str, "title": str, "body": str}, frozenset({"repository", "title"}), "write", True),
        CapabilitySpec("google_drive", "files.search", "Search accessible Drive files.", {"query": str, "limit": int}, frozenset({"query"})),
        CapabilitySpec("slack", "messages.send", "Send a message to an approved channel.", {"channel": str, "text": str}, frozenset({"channel", "text"}), "write", True),
        CapabilitySpec("smartbethg", "knowledge.search", "Search the owner's indexed knowledge.", {"query": str, "limit": int}, frozenset({"query"})),
    ]

class CapabilityRegistry:
    def __init__(self, capabilities=None):
        self._items = {}
        for capability in capabilities or default_capabilities():
            self.register(capability)
    def register(self, capability):
        key = (capability.connector_key, capability.action)
        if key in self._items:
            raise ValueError(f"Capability already registered: {key[0]}.{key[1]}")
        if capability.risk not in {"read", "write", "destructive", "financial"}:
            raise ValueError("Unsupported capability risk.")
        self._items[key] = capability
    def get(self, connector_key, action):
        return self._items.get((str(connector_key), str(action)))
    def list_for_connector(self, connector_key):
        return [self.describe(item) for item in self._items.values() if item.connector_key == connector_key]
    def list_all(self):
        return [self.describe(item) for item in self._items.values()]
    @staticmethod
    def describe(item):
        return {"connector_key": item.connector_key, "action": item.action, "description": item.description,
                "input_fields": {key: value.__name__ for key, value in item.input_fields.items()},
                "required_fields": sorted(item.required_fields), "risk": item.risk,
                "side_effecting": item.side_effecting, "permission": item.permission}
    def validate_arguments(self, connector_key, action, arguments):
        capability = self.get(connector_key, action)
        if capability is None:
            raise ValueError("Unknown connector action.")
        if not isinstance(arguments, dict) or len(arguments) > 40:
            raise ValueError("Action arguments must be an object with at most 40 fields.")
        unknown = set(arguments) - set(capability.input_fields)
        missing = capability.required_fields - set(arguments)
        if unknown:
            raise ValueError("Unsupported action argument(s): " + ", ".join(sorted(unknown)))
        if missing:
            raise ValueError("Missing required action argument(s): " + ", ".join(sorted(missing)))
        for key, value in arguments.items():
            expected = capability.input_fields[key]
            if expected is str:
                valid = isinstance(value, str) and len(value) <= 12000
            elif expected is int:
                valid = isinstance(value, int) and not isinstance(value, bool)
            elif expected is bool:
                valid = isinstance(value, bool)
            elif expected is dict:
                valid = isinstance(value, dict)
            elif expected is list:
                valid = isinstance(value, list)
            else:
                valid = isinstance(value, expected)
            if not valid:
                raise ValueError(f"Invalid value for action argument: {key}.")
        return capability
