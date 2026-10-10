from repositories.audit_repository import Repository


class AuditService:
    def __init__(self):
        self.repo = Repository()

    def list_events(self, user_id):
        return self.repo.list(user_id)

    def list_all_events(self, limit=200):
        return self.repo.list_all(limit)

    def record(self, user_id, action, resource, decision, risk_level=None, details=None, agent_id="smart_bethg"):
        self.repo.create(user_id, agent_id, action, resource, decision, risk_level, details)
