"""
Smart BethG - Role Permissions

Bridges the application's user accounts (users.role: "user" or "admin")
to the tool-permission system already built in security/ (SecurityContext,
PolicyEngine, RiskEngine). This is the missing piece that let that
security stack sit fully built but never wired to anything.

Only two roles exist for V1: "user" and "admin". This is deliberately
coarse - a real per-permission grant system (letting one user opt into
git.write without terminal.execute, say) is future work, not something
to fake here.
"""
from security.security_context import SecurityContext

# Every tool name from controller.ToolOrchestrator, split by what each
# role may even attempt (the PolicyEngine still separately decides
# allow / deny / approval_required based on risk - holding the
# permission is necessary but not sufficient for high-risk actions).
ROLE_PERMISSIONS = {
    "user": frozenset({
        "filesystem.read",
        "git.read",
    }),
    "admin": frozenset({
        "filesystem.read",
        "filesystem.write",
        "git.read",
        "git.write",
        "terminal.execute",
        "network.request",
        "docker.run",
    }),
}

DEFAULT_ROLE = "user"


def permissions_for_role(role: str) -> frozenset:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[DEFAULT_ROLE])


def build_security_context(user: dict, workspace: str = "default", session_id: str = "") -> SecurityContext:
    """
    `user` is whatever get_current_user()/authenticate_user() returns -
    must at least have "id" and "role" keys.
    """
    role = user.get("role", DEFAULT_ROLE)
    return SecurityContext(
        user_id=str(user["id"]),
        session_id=session_id,
        agent_id="smart_bethg",
        workspace=workspace,
        permissions=permissions_for_role(role),
    )
