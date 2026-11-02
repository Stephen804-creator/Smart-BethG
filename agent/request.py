"""
Smart BethG - Agent Request Model (T0401)

Formalizes what used to be just a raw string passed to
Controller.handle_request(). Nothing exotic yet - no attachments, no
tool-permission overrides - because nothing downstream uses those
yet either; adding fields nothing reads would be exactly the kind of
premature complexity this project's build rules warn against.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentRequest:
    text: str
    user: dict
    workspace: str = "default"
    conversation_id: Optional[int] = None
    selection: Optional[str] = None  # AI provider/model choice, passed through to chat when intent is "chat"
    user_instructions: Optional[str] = None  # User-authored context for AI chat responses
    mode: str = "Balanced"  # User-selected interaction mode
    mentor: bool = True  # Include learning-oriented explanations when useful
    file_ids: list[int] = field(default_factory=list)  # Owner-scoped uploaded source files

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("AgentRequest.text must be a non-empty string.")
        if not isinstance(self.workspace, str) or not self.workspace.strip():
            raise ValueError("AgentRequest.workspace must be a non-empty string.")
        if "id" not in self.user:
            raise ValueError("AgentRequest.user must include an 'id'.")
        if self.mode not in {"Plan", "Balanced", "Build"}:
            raise ValueError("AgentRequest.mode must be Plan, Balanced, or Build.")
        if len(self.file_ids) > 10 or any(not isinstance(file_id, int) or file_id < 1 for file_id in self.file_ids):
            raise ValueError("AgentRequest.file_ids must contain at most 10 positive integer IDs.")
