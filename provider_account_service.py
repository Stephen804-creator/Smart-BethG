from database import get_connection
class ProviderAccountService:
 def add(self,user_id,name,model,credential_ref):
  c=get_connection(); cur=c.execute("INSERT INTO providers(user_id,name,model,credential_ref) VALUES(?,?,?,?)",(user_id,name,model,credential_ref)); c.commit(); i=cur.lastrowid; c.close(); return {"id":i,"name":name,"model":model,"status":"active"}
 def list(self,user_id):
  c=get_connection(); rows=c.execute("SELECT id,name,model,status FROM providers WHERE user_id=?",(user_id,)).fetchall(); c.close(); return [dict(r) for r in rows]
