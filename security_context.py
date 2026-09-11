"""Smart BethG security context.

LV: Trusted application state creates this context. Model output cannot grant
itself permissions by changing prompts, tool output, or generated text.
"""
from dataclasses import dataclass, field
from typing import FrozenSet, Mapping

@dataclass(frozen=True)
class SecurityContext:
    user_id: str
    session_id: str
    agent_id: str
    workspace: str
    permissions: FrozenSet[str] = field(default_factory=frozenset)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
