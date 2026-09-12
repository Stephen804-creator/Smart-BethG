import uuid
class ApprovalService:
 def __init__(self): self.pending={}
 def create(self,user_id,action,resource):
  i=str(uuid.uuid4()); self.pending[i]={"id":i,"user_id":user_id,"action":action,"resource":resource,"status":"pending"}; return self.pending[i]
 def list_pending(self,user_id): return [x for x in self.pending.values() if x["user_id"]==user_id and x["status"]=="pending"]
 def decide(self,approval_id,user_id,approved):
  x=self.pending.get(approval_id)
  if not x or x["user_id"]!=user_id: return {"error":"Approval not found."}
  x["status"]="approved" if approved else "rejected"; return x
