from database import get_connection
class Repository:
 def list(self,user_id):
  c=get_connection(); rows=c.execute("SELECT * FROM approvals WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall(); c.close(); return [dict(r) for r in rows]
