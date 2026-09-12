from repositories.audit_repository import Repository
class AuditService:
 def __init__(self): self.repo=Repository()
 def list_events(self,user_id): return self.repo.list(user_id)
