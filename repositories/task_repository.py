from database import get_connection
class TaskRepository:
 def create(self,user_id,request,status,workspace):
  c=get_connection(); cur=c.execute("INSERT INTO tasks(user_id,request,status,workspace) VALUES(?,?,?,?)",(user_id,request,status,workspace)); c.commit(); i=cur.lastrowid; c.close(); return i
 def list(self,user_id):
  c=get_connection(); rows=c.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall(); c.close(); return [dict(r) for r in rows]
