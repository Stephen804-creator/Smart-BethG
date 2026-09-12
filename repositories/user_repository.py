from database import get_connection
class UserRepository:
 def get(self,user_id):
  c=get_connection();
  try:
   r=c.execute("SELECT id,username,status FROM users WHERE id=?",(user_id,)).fetchone(); return dict(r) if r else None
  finally:c.close()
