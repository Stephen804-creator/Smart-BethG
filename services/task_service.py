from repositories.task_repository import TaskRepository
class TaskService:
 def __init__(self): self.repo=TaskRepository()
 def create(self,user_id,request,workspace): return {"task_id":self.repo.create(user_id,request,"queued",workspace),"status":"queued"}
 def list_tasks(self,user_id): return self.repo.list(user_id)
 def update_status(self,user_id,task_id,status):
  if status not in {
   "queued","running","completed","failed","cancelled","executed",
   "needs_clarification","approval_required","denied","no_provider",
   "search_failed","no_results","unknown_tool","indeterminate","expired"
  }:
   raise ValueError("Invalid task status")
  return self.repo.update_status(user_id,task_id,status)
