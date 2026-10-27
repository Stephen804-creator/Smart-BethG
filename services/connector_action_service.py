"""Policy-governed connector action dispatch."""
import uuid
from services.connector_service import ConnectorInstallationService, ConnectorRegistry
from services.policy_engine import PolicyEngine
from services.approval_service import ApprovalService
from services.audit_service import AuditService

class ConnectorActionService:
    def __init__(self,registry=None,installations=None,policy=None,approvals=None,audit=None):
        self.registry=registry or ConnectorRegistry()
        self.installations=installations or ConnectorInstallationService()
        self.policy=policy or PolicyEngine()
        self.approvals=approvals or ApprovalService()
        self.audit=audit or AuditService()

    def request_action(self,user_id,installation_id,action,arguments,context=None):
        installation=self.installations.get_for_user(user_id,installation_id)
        if not installation: return {"status":"not_found","detail":"Connector installation not found."}
        try: capability=self.registry.capabilities.validate_arguments(installation["connector_key"],action,arguments)
        except ValueError as exc: return {"status":"invalid","detail":str(exc)}
        decision=self.policy.evaluate(capability,installation,user_id)
        if decision.decision=="deny":
            self._audit(user_id,capability.permission,"denied",decision.reason)
            return {"status":"denied","detail":decision.reason}
        action_context = dict(context or {})
        action_context.setdefault("idempotency_key", f"connector-action:{installation_id}:{uuid.uuid4().hex}")
        payload={"connector_key":installation["connector_key"],"installation_id":installation_id,
                 "action":action,"arguments":arguments,"context":action_context}
        if decision.requires_approval:
            approval=self.approvals.create(user_id,capability.permission,
                                           f"connector:{installation['connector_key']}:{action}",payload=payload)
            self._audit(user_id,capability.permission,"approval_required",decision.reason)
            return {"status":"approval_required","approval":approval}
        result=self._execute(user_id,installation,capability,arguments,action_context)
        return {"status":"completed" if result.get("success") else "unavailable","result":result}

    def execute_approved(self,user_id,approval_id):
        record=self.approvals.get_for_user(approval_id,user_id)
        if not record: return {"status":"not_found","detail":"Approval not found."}
        if record.get("status")!="approved": return {"status":"invalid_state","detail":"Approval has not been approved."}
        payload=record.get("payload") or {}
        if not all(key in payload for key in ("connector_key","installation_id","action","arguments")):
            return {"status":"unsupported","detail":"This is not a connector-action approval."}
        try: self.approvals.claim_for_execution(approval_id,user_id)
        except Exception as exc: return {"status":"already_claimed","detail":str(exc)[:500]}
        installation=self.installations.get_for_user(user_id,payload["installation_id"])
        capability=self.registry.capabilities.get(payload["connector_key"],payload["action"])
        if not installation or not capability:
            result={"success":False,"status":"unavailable","detail":"Connector or action is no longer available."}
        else:
            decision=self.policy.evaluate(capability,installation,user_id)
            if decision.decision!="approval_required":
                result={"success":False,"status":"denied","detail":"Policy changed after approval; action was not executed."}
            else:
                try:
                    self.registry.capabilities.validate_arguments(payload["connector_key"],payload["action"],payload["arguments"])
                    result=self._execute(user_id,installation,capability,payload["arguments"],payload.get("context") or {})
                except Exception:
                    result={"success":False,"status":"failed","detail":"Connector execution failed."}
        self.approvals.mark_execution_result(approval_id,user_id,"completed" if result.get("success") else "failed",result)
        context=payload.get("context") or {}
        if context.get("mission_id") and context.get("run_id"):
            from services.mission_service import MissionService
            from services.job_queue import JobQueue
            missions=MissionService()
            if result.get("success"):
                missions.resume_after_approval(user_id,context["mission_id"],context["run_id"])
                next_index=int(context.get("step_index",0))+1
                run=missions.get(user_id,context["mission_id"])
                active=next((r for r in run["runs"] if int(r["id"])==int(context["run_id"])),None) if run else None
                progress=active.get("result") if active else {}
                outputs=list(progress.get("outputs",[])) if isinstance(progress,dict) else []
                outputs.append({"step_index":int(context.get("step_index",0)),"connector_key":payload["connector_key"],
                                "action":payload["action"],"result":result})
                missions.save_progress(context["mission_id"],context["run_id"],outputs)
                JobQueue().enqueue(user_id,"mission.execute",
                    {"mission_id":context["mission_id"],"run_id":context["run_id"],"step_index":next_index},
                    idempotency_key=f"mission-run:{context['run_id']}:step:{next_index}",priority=1)
            else:
                missions.fail_after_approval(user_id,context["mission_id"],context["run_id"],"Approved connector action failed.")
        return {"status":"completed" if result.get("success") else result.get("status","failed"),"result":result}

    def _execute(self,user_id,installation,capability,arguments,context):
        adapter=self.registry.adapter(installation["connector_key"])
        if adapter is None:
            self._audit(user_id,capability.permission,"unavailable","No trusted adapter is registered.")
            return {"success":False,"status":"unavailable","detail":"Catalog entry exists, but no trusted runtime adapter is configured."}
        try:
            result=adapter.execute(capability.action,arguments,{"user_id":user_id,"installation_id":installation["id"],
                                                               "idempotency_key":context.get("idempotency_key")})
            if not isinstance(result,dict): raise ValueError("Connector adapter must return an object.")
            self._audit(user_id,capability.permission,"completed" if result.get("success") else "failed","Connector adapter returned.")
            return result
        except Exception as exc:
            self._audit(user_id,capability.permission,"failed",type(exc).__name__)
            return {"success":False,"status":"failed","detail":"Connector execution failed."}

    def _audit(self,user_id,action,decision,details):
        try: self.audit.record(user_id,action,"connector",decision,details=details)
        except Exception: pass
