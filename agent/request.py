"""
Smart BethG - Agent Request Model (T0401)

Formalizes what used to be just a raw string passed to
Controller.handle_request(). Nothing exotic yet - no attachments, no
tool-permission overrides - because nothing downstream uses those
yet either; adding fields nothing reads would be exactly the kind of
premature complexity this project's build rules warn against.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentRequest:
    text: str
    user: dict
    workspace: str = "default"
    conversation_id: Optional[int] = None
    selection: Optional[str] = None  # AI provider/model choice, passed through to chat when intent is "chat"

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("AgentRequest.text must be a non-empty string.")
        if not isinstance(self.workspace, str) or not self.workspace.strip():
            raise ValueError("AgentRequest.workspace must be a non-empty string.")
        if "id" not in self.user:
            raise ValueError("AgentRequest.user must include an 'id'.")
