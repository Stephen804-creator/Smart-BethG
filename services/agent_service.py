from database import get_connection
class AgentService:
 def list_agents(self,user_id):
  c=get_connection(); rows=c.execute("SELECT * FROM agents WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall(); c.close(); return [dict(r) for r in rows]
