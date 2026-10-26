"""Organization and workspace authorization with explicit role checks."""
import json
import re

from database import get_connection


ORG_ROLES = {"owner", "admin", "member"}
WORKSPACE_ROLES = {"admin", "editor", "viewer"}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value):
    result = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    if not result:
        raise ValueError("Name must contain at least one letter or number.")
    return result[:80]


class WorkspaceService:
    def create_organization(self, user_id, name):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Organization name must be between 1 and 120 characters.")
        slug = _slug(name)
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO organizations(name,slug,owner_user_id) VALUES (?,?,?) RETURNING id",
                (name, slug, user_id),
            ).fetchone()
            organization_id = row["id"]
            conn.execute(
                "INSERT INTO organization_members(organization_id,user_id,role,added_by) VALUES (?,?,'owner',?)",
                (organization_id, user_id, user_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_organization(user_id, organization_id)

    def list_organizations(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT o.id,o.name,o.slug,o.owner_user_id,o.status,o.created_at,o.updated_at,om.role AS member_role "
                "FROM organizations o JOIN organization_members om ON om.organization_id=o.id "
                "WHERE om.user_id=? AND o.status='active' ORDER BY o.name,o.id",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_organization(self, user_id, organization_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT o.id,o.name,o.slug,o.owner_user_id,o.status,o.created_at,o.updated_at,om.role AS member_role "
                "FROM organizations o JOIN organization_members om ON om.organization_id=o.id "
                "WHERE o.id=? AND om.user_id=?",
                (organization_id, user_id),
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            item["members"] = [
                dict(member) for member in conn.execute(
                    "SELECT u.username,om.user_id,om.role,om.created_at FROM organization_members om "
                    "JOIN users u ON u.id=om.user_id WHERE om.organization_id=? ORDER BY om.created_at,om.user_id",
                    (organization_id,),
                ).fetchall()
            ]
            return item
        finally:
            conn.close()

    def add_organization_member(self, actor_id, organization_id, username, role="member"):
        if role not in {"admin", "member"}:
            raise ValueError("New organization members may be assigned admin or member.")
        username = (username or "").strip()
        if not username or len(username) > 120:
            raise ValueError("A valid existing username is required.")
        conn = get_connection()
        try:
            self._require_org_role(conn, actor_id, organization_id, {"owner", "admin"})
            target = conn.execute(
                "SELECT id FROM users WHERE username=? AND status='active' LIMIT 1", (username,)
            ).fetchone()
            if not target:
                raise LookupError("Active user not found.")
            conn.execute(
                "INSERT INTO organization_members(organization_id,user_id,role,added_by) VALUES (?,?,?,?) "
                "ON CONFLICT(organization_id,user_id) DO UPDATE SET role=EXCLUDED.role,added_by=EXCLUDED.added_by",
                (organization_id, target["id"], role, actor_id),
            )
            conn.commit()
            return {"organization_id": organization_id, "user_id": target["id"], "username": username, "role": role}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_workspace(self, user_id, organization_id, name, description=""):
        name = (name or "").strip()
        description = (description or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Workspace name must be between 1 and 120 characters.")
        if len(description) > 2000:
            raise ValueError("Workspace description cannot exceed 2000 characters.")
        slug = _slug(name)
        conn = get_connection()
        try:
            self._require_org_role(conn, user_id, organization_id, {"owner", "admin"})
            row = conn.execute(
                "INSERT INTO workspaces(organization_id,name,slug,description,created_by) VALUES (?,?,?,?,?) RETURNING id",
                (organization_id, name, slug, description, user_id),
            ).fetchone()
            workspace_id = row["id"]
            conn.execute(
                "INSERT INTO workspace_members(workspace_id,user_id,role,granted_by) VALUES (?,?,'admin',?)",
                (workspace_id, user_id, user_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_workspace(user_id, workspace_id)

    def list_workspaces(self, user_id, organization_id=None):
        conn = get_connection()
        try:
            sql = (
                "SELECT w.id,w.organization_id,w.name,w.slug,w.description,w.status,w.created_by,w.created_at,w.updated_at,wm.role AS workspace_role "
                "FROM workspaces w JOIN organization_members om ON om.organization_id=w.organization_id AND om.user_id=? "
                "LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=? "
                "WHERE w.status='active' AND (wm.user_id IS NOT NULL OR om.role IN ('owner','admin'))"
            )
            params = [user_id, user_id]
            if organization_id is not None:
                sql += " AND w.organization_id=?"
                params.append(organization_id)
            sql += " ORDER BY w.updated_at DESC,w.id DESC"
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        finally:
            conn.close()

    def get_workspace(self, user_id, workspace_id):
        conn = get_connection()
        try:
            access = self._workspace_access(conn, user_id, workspace_id)
            if not access:
                return None
            row = conn.execute(
                "SELECT id,organization_id,name,slug,description,status,created_by,created_at,updated_at "
                "FROM workspaces WHERE id=?", (workspace_id,),
            ).fetchone()
            item = dict(row)
            item["workspace_role"] = access["role"]
            return item
        finally:
            conn.close()

    def add_workspace_member(self, actor_id, workspace_id, username, role="viewer"):
        if role not in {"admin", "editor", "viewer"}:
            raise ValueError("Workspace role must be admin, editor, or viewer.")
        conn = get_connection()
        try:
            workspace = conn.execute(
                "SELECT id,organization_id FROM workspaces WHERE id=? AND status='active'", (workspace_id,)
            ).fetchone()
            if not workspace:
                raise LookupError("Workspace not found.")
            actor = self._workspace_access(conn, actor_id, workspace_id)
            if not actor or actor["role"] not in {"admin", "owner"}:
                raise PermissionError("Workspace administrator permission is required.")
            target = conn.execute(
                "SELECT id FROM users WHERE username=? AND status='active' LIMIT 1", ((username or "").strip(),)
            ).fetchone()
            if not target:
                raise LookupError("Active user not found.")
            member = conn.execute(
                "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
                (workspace["organization_id"], target["id"]),
            ).fetchone()
            if not member:
                raise ValueError("User must be an organization member before workspace access is granted.")
            conn.execute(
                "INSERT INTO workspace_members(workspace_id,user_id,role,granted_by) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role,granted_by=EXCLUDED.granted_by",
                (workspace_id, target["id"], role, actor_id),
            )
            conn.commit()
            return {"workspace_id": workspace_id, "user_id": target["id"], "username": username, "role": role}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_document(self, user_id, workspace_id, title, body):
        title, body = (title or "").strip(), body if isinstance(body, str) else ""
        if not title or len(title) > 200:
            raise ValueError("Document title must be between 1 and 200 characters.")
        if not body.strip() or len(body) > 100000:
            raise ValueError("Document body must be between 1 and 100000 characters.")
        conn = get_connection()
        try:
            access = self._workspace_access(conn, user_id, workspace_id)
            if not access:
                raise LookupError("Workspace not found.")
            if access["role"] not in {"admin", "editor", "owner"}:
                raise PermissionError("Viewer role cannot create workspace documents.")
            row = conn.execute(
                "INSERT INTO workspace_documents(workspace_id,created_by,title,body) VALUES (?,?,?,?) RETURNING id",
                (workspace_id, user_id, title, body),
            ).fetchone()
            conn.commit()
            return self.get_document(user_id, workspace_id, row["id"])
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_documents(self, user_id, workspace_id):
        conn = get_connection()
        try:
            if not self._workspace_access(conn, user_id, workspace_id):
                raise LookupError("Workspace not found.")
            rows = conn.execute(
                "SELECT id,workspace_id,created_by,title,body,version,status,created_at,updated_at "
                "FROM workspace_documents WHERE workspace_id=? AND status='active' ORDER BY updated_at DESC,id DESC",
                (workspace_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_document(self, user_id, workspace_id, document_id):
        conn = get_connection()
        try:
            if not self._workspace_access(conn, user_id, workspace_id):
                return None
            row = conn.execute(
                "SELECT id,workspace_id,created_by,title,body,version,status,created_at,updated_at "
                "FROM workspace_documents WHERE id=? AND workspace_id=? AND status='active'",
                (document_id, workspace_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_document(self, user_id, workspace_id, document_id, title, body):
        title, body = (title or "").strip(), body if isinstance(body, str) else ""
        if not title or len(title) > 200 or not body.strip() or len(body) > 100000:
            raise ValueError("Title and body are required and must fit workspace limits.")
        conn = get_connection()
        try:
            access = self._workspace_access(conn, user_id, workspace_id)
            if not access:
                return None
            if access["role"] not in {"admin", "editor", "owner"}:
                raise PermissionError("Viewer role cannot edit workspace documents.")
            row = conn.execute(
                "UPDATE workspace_documents SET title=?,body=?,version=version+1,updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND workspace_id=? AND status='active' RETURNING id",
                (title, body, document_id, workspace_id),
            ).fetchone()
            conn.commit()
            return self.get_document(user_id, workspace_id, document_id) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _require_org_role(conn, user_id, organization_id, allowed_roles):
        row = conn.execute(
            "SELECT role FROM organization_members WHERE organization_id=? AND user_id=?",
            (organization_id, user_id),
        ).fetchone()
        if not row or row["role"] not in allowed_roles:
            raise PermissionError("Organization owner/admin permission is required.")

    @staticmethod
    def _workspace_access(conn, user_id, workspace_id):
        row = conn.execute(
            "SELECT w.id,w.organization_id,om.role AS org_role,wm.role AS workspace_role "
            "FROM workspaces w JOIN organization_members om ON om.organization_id=w.organization_id AND om.user_id=? "
            "LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=? "
            "WHERE w.id=? AND w.status='active' AND om.role IN ('owner','admin','member') "
            "AND (wm.user_id IS NOT NULL OR om.role IN ('owner','admin'))",
            (user_id, user_id, workspace_id),
        ).fetchone()
        if not row:
            return None
        return {"role": row["workspace_role"] or row["org_role"], "organization_id": row["organization_id"]}
