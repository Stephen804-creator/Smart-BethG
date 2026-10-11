from database import get_connection


class MemoryRepository:
    def create(self, user_id, content, scope="user", scope_ref=None, title=None, source="explicit"):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO memory(user_id, scope, scope_ref, title, content, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, scope, scope_ref, title, content, source),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get(self, memory_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM memory WHERE id=? AND user_id=? LIMIT 1", (memory_id, user_id)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id):
        """Every memory of every scope belonging to this user - the governance view."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM memory WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_by_scope(self, user_id, scope, scope_ref=None):
        conn = get_connection()
        try:
            if scope_ref is None:
                rows = conn.execute(
                    "SELECT * FROM memory WHERE user_id=? AND scope=? ORDER BY id DESC",
                    (user_id, scope),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memory WHERE user_id=? AND scope=? AND scope_ref=? ORDER BY id DESC",
                    (user_id, scope, scope_ref),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_context_candidates(self, user_id, workspace="default", conversation_id=None, terms=None, limit=200):
        """Fetch applicable, owner-scoped memory records for bounded local ranking."""
        import re

        clauses = ["(scope='user')", "(scope='project' AND scope_ref=?)"]
        params = [user_id, workspace or "default"]
        if conversation_id is not None:
            clauses.append("(scope='conversation' AND scope_ref=?)")
            params.append(str(conversation_id))
        where = "user_id=? AND (" + " OR ".join(clauses) + ")"
        terms = [str(term).lower() for term in (terms or []) if term]
        if terms:
            likes = " OR ".join("LOWER(content) LIKE ?" for _ in terms)
            like_params = [f"%{term}%" for term in terms]
            conn = get_connection()
            try:
                if getattr(conn, "is_postgres", False):
                    fts_terms = []
                    for term in terms:
                        fts_terms.extend(re.findall(r"[a-zA-Z0-9]+", term))
                    tsquery = " | ".join(dict.fromkeys(fts_terms))
                    where += " AND (to_tsvector('simple', content) @@ to_tsquery('simple', ?) OR (" + likes + "))"
                    params.extend([tsquery, *like_params])
                else:
                    where += " AND (" + likes + ")"
                    params.extend(like_params)
                params.append(max(1, min(int(limit), 500)))
                rows = conn.execute(
                    "SELECT * FROM memory WHERE " + where + " ORDER BY id DESC LIMIT ?",
                    tuple(params),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        conn = get_connection()
        try:
            params.append(max(1, min(int(limit), 500)))
            rows = conn.execute(
                "SELECT * FROM memory WHERE " + where + " ORDER BY id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def delete(self, memory_id, user_id):
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM memory WHERE id=? AND user_id=?", (memory_id, user_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_all_for_user(self, user_id):
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
