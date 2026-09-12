from database import get_connection
class ProviderService:
 def list_providers(self,user_id):
  c=get_connection(); rows=c.execute("SELECT id,name,model,status FROM providers WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall(); c.close(); return [dict(r) for r in rows]
