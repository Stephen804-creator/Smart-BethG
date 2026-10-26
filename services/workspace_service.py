"""Organization and workspace membership with fail-closed role checks."""
import re
from database import get_connection

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")
_ORG_ROLES = {"owner", "admin", "member", "viewer"}
_WORKSPACE_ROLES = {"owner", "admin", "editor", "viewer"}
_PERMISSIONS = {
    "view": {"owner", "admin", "editor", "viewer"},
    "edit": {"owner", "admin", "editor"},
    "manage_members": {"owner", "admin"},
    "admin": {"owner", "admin"},
}


def _slug(value):
    value = (value or "").strip().lower()
    if not _SLUG.fullmatch(value):
        raise ValueError("Slug must be 3–60 lowercase letters, numbers, or hyphens and cannot start/end with a hyphen.")
    return value


class WorkspaceService:
    def create_organization(self, user_id, name, slug, workspace_name=None, workspace_slug=None):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Organization name must be 1–120 characters.")
        slug = _slug(slug)
        workspace_name = (workspace_name or "General").strip()
        workspace_slug = _slug(workspace_slug or "general")
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO organizations(name,slug,owner_user_id) VALUES (?,?,?) RETURNING id,name,slug,owner_user_id,created_at",
                (name, slug, user_id),
            ).fetchone()
            org_id = row["id"]
            conn.execute(
                "INSERT INTO organization_members(organization_id,user_id,role,invited_by) VALUES (?,?, 'owner',?)",
                (org_id, user_id, user_id),
            )
            ws = conn.execute(
                "INSERT INTO workspaces(organization_id,name,slug,created_by) VALUES (?,?,?,?) RETURNING id,name,slug,organization_id,status,created_at",
                (org_id, workspace_name, workspace_slug, user_id),
            ).fetchone()
            conn.execute(
                "INSERT INTO workspace_members(workspace_id,user_id,role,granted_by) VALUES (?,?, 'owner',?)",
                (ws["id"], user_id, user_id),
            )
            conn.commit()
            return {"organization": dict(row), "default_workspace": dict(ws), "role": "owner"}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_organizations(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT o.id,o.name,o.slug,o.owner_user_id,o.created_at,om.role "
                "FROM organizations o JOIN organization_members om ON om.organization_id=o.id "
                "WHERE om.user_id=? ORDER BY o.created_at DESC,o.id DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_organization_member(self, actor_id, organization_id, username, role):
        role = (role or "").strip().lower()
        if role not in {"admin", "member", "viewer"}:
            raise ValueError("New members may be assigned admin, member, or viewer; ownership cannot be transferred through this endpoint.")
        username = (username or "").strip()
        if not username or len(username) > 254:
            raise ValueError("A valid username is required.")
        conn = get_connection()
        try:
            actor = conn.execute(
                "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
                (organization_id, actor_id),
            ).fetchone()
            if not actor or actor["role"] not in {"owner", "admin"}:
                raise PermissionError("Only organization owners or admins can manage members.")
            target = conn.execute(
                "SELECT id FROM users WHERE username=? AND status='active'", (username,)
            ).fetchone()
            if not target:
                raise LookupError("Active user not found.")
            existing = conn.execute(
                "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
                (organization_id, target["id"]),
            ).fetchone()
            if existing and existing["role"] == "owner":
                raise PermissionError("The organization owner cannot be demoted through member management.")
            cursor = conn.execute(
                "INSERT INTO organization_members(organization_id,user_id,role,invited_by) VALUES (?,?,?,?) "
                "ON CONFLICT(organization_id,user_id) DO UPDATE SET role=EXCLUDED.role "
                "WHERE organization_members.role <> 'owner'",
                (organization_id, target["id"], role, actor_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Organization membership could not be changed.")
            conn.commit()
            return {"organization_id": organization_id, "user_id": target["id"], "role": role}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_organization_members(self, user_id, organization_id):
        conn = get_connection()
        try:
            self._require_org_member(conn, user_id, organization_id)
            rows = conn.execute(
                "SELECT om.user_id,u.username,om.role,om.created_at FROM organization_members om "
                "JOIN users u ON u.id=om.user_id WHERE om.organization_id=? ORDER BY om.created_at,om.user_id",
                (organization_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def create_workspace(self, user_id, organization_id, name, slug):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Workspace name must be 1–120 characters.")
        slug = _slug(slug)
        conn = get_connection()
        try:
            member = conn.execute(
                "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
                (organization_id, user_id),
            ).fetchone()
            if not member or member["role"] not in {"owner", "admin"}:
                raise PermissionError("Organization admin permission is required to create a workspace.")
            row = conn.execute(
                "INSERT INTO workspaces(organization_id,name,slug,created_by) VALUES (?,?,?,?) "
                "RETURNING id,organization_id,name,slug,status,created_at",
                (organization_id, name, slug, user_id),
            ).fetchone()
            conn.execute(
                "INSERT INTO workspace_members(workspace_id,user_id,role,granted_by) VALUES (?,?, 'owner',?)",
                (row["id"], user_id, user_id),
            )
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_workspaces(self, user_id, organization_id=None):
        conn = get_connection()
        try:
            if organization_id is None:
                rows = conn.execute(
                    "SELECT w.id,w.organization_id,w.name,w.slug,w.status,w.created_at,"
                    "CASE WHEN om.role IN ('owner','admin') THEN 'admin' ELSE wm.role END AS role "
                    "FROM workspaces w LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=? "
                    "LEFT JOIN organization_members om ON om.organization_id=w.organization_id AND om.user_id=? "
                    "WHERE (wm.user_id IS NOT NULL OR om.role IN ('owner','admin')) AND w.status='active' "
                    "ORDER BY w.created_at DESC,w.id DESC",
                    (user_id, user_id),
                ).fetchall()
            else:
                self._require_org_member(conn, user_id, organization_id)
                rows = conn.execute(
                    "SELECT w.id,w.organization_id,w.name,w.slug,w.status,w.created_at,"
                    "CASE WHEN om.role IN ('owner','admin') THEN 'admin' ELSE wm.role END AS role "
                    "FROM workspaces w LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=? "
                    "LEFT JOIN organization_members om ON om.organization_id=w.organization_id AND om.user_id=? "
                    "WHERE (wm.user_id IS NOT NULL OR om.role IN ('owner','admin')) "
                    "AND w.organization_id=? AND w.status='active' ORDER BY w.created_at DESC,w.id DESC",
                    (user_id, user_id, organization_id),
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_workspace_member(self, actor_id, workspace_id, username, role):
        role = (role or "").strip().lower()
        if role not in {"admin", "editor", "viewer"}:
            raise ValueError("New workspace members may be assigned admin, editor, or viewer.")
        conn = get_connection()
        try:
            workspace = conn.execute(
                "SELECT id,organization_id FROM workspaces WHERE id=? AND status='active'",
                (workspace_id,),
            ).fetchone()
            if not workspace:
                raise LookupError("Workspace not found.")
            actor = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, actor_id),
            ).fetchone()
            org_actor = conn.execute(
                "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
                (workspace["organization_id"], actor_id),
            ).fetchone()
            if not ((actor and actor["role"] in {"owner", "admin"}) or
                    (org_actor and org_actor["role"] in {"owner", "admin"})):
                raise PermissionError("Workspace or organization admin permission is required.")
            target = conn.execute(
                "SELECT id FROM users WHERE username=? AND status='active'", (username.strip(),)
            ).fetchone()
            if not target:
                raise LookupError("Active user not found.")
            org_target = conn.execute(
                "SELECT 1 FROM organization_members WHERE organization_id=? AND user_id=?",
                (workspace["organization_id"], target["id"]),
            ).fetchone()
            if not org_target:
                raise ValueError("Add the user to the organization before granting workspace access.")
            existing = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, target["id"]),
            ).fetchone()
            if existing and existing["role"] == "owner":
                raise PermissionError("The workspace owner cannot be demoted through member management.")
            cursor = conn.execute(
                "INSERT INTO workspace_members(workspace_id,user_id,role,granted_by) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role "
                "WHERE workspace_members.role <> 'owner'",
                (workspace_id, target["id"], role, actor_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Workspace membership could not be changed.")
            conn.commit()
            return {"workspace_id": workspace_id, "user_id": target["id"], "role": role}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def require_workspace_access(self, user_id, workspace_id, permission="view"):
        if permission not in _PERMISSIONS:
            raise ValueError("Unknown workspace permission.")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT w.status,wm.role AS workspace_role,om.role AS organization_role "
                "FROM workspaces w LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=? "
                "LEFT JOIN organization_members om ON om.organization_id=w.organization_id AND om.user_id=? "
                "WHERE w.id=?",
                (user_id, user_id, workspace_id),
            ).fetchone()
            if not row or row["status"] != "active":
                raise PermissionError("Workspace permission denied.")
            role = "admin" if row["organization_role"] in {"owner", "admin"} else row["workspace_role"]
            if role not in _PERMISSIONS[permission]:
                raise PermissionError("Workspace permission denied.")
            return {"workspace_id": workspace_id, "role": role, "permission": permission}
        finally:
            conn.close()

    @staticmethod
    def _require_org_member(conn, user_id, organization_id):
        row = conn.execute(
            "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
            (organization_id, user_id),
        ).fetchone()
        if not row:
            raise PermissionError("Organization access denied.")
        return row["role"]
