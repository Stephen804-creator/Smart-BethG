from repositories.task_repository import TaskRepository
class TaskService:
 def __init__(self): self.repo=TaskRepository()
 def create(self,user_id,request,workspace): return {"task_id":self.repo.create(user_id,request,"queued",workspace),"status":"queued"}
 def list_tasks(self,user_id): return self.repo.list(user_id)
