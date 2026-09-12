from werkzeug.security import check_password_hash
from database import get_connection

def authenticate_user(username,password):
    c=get_connection();
    if c is None:return None
    try:
        row=c.execute("SELECT id,username,password_hash,status FROM users WHERE username=? LIMIT 1",(username,)).fetchone()
        if not row or row[3]!="active" or not check_password_hash(row[2],password): return None
        return {"id":row[0],"username":row[1]}
    finally:c.close()

def get_user_by_id(user_id):
    c=get_connection();
    if c is None:return None
    try:
        row=c.execute("SELECT id,username,status FROM users WHERE id=? LIMIT 1",(user_id,)).fetchone()
        return {"id":row[0],"username":row[1]} if row and row[2]=="active" else None
    finally:c.close()
