"""Durable mission-step execution through the connector policy boundary."""
from services.mission_service import MissionService
from services.connector_service import ConnectorInstallationService
from services.connector_action_service import ConnectorActionService

class MissionExecutor:
    def __init__(self,missions=None,installations=None,actions=None):
        self.missions=missions or MissionService()
        self.installations=installations or ConnectorInstallationService()
        self.actions=actions or ConnectorActionService()
    def execute(self,job):
        payload=job.get("payload") or {}; user_id=job["user_id"]
        mission_id=int(payload.get("mission_id",0)); run_id=int(payload.get("run_id",0)); step_index=int(payload.get("step_index",0))
        mission=self.missions.get(user_id,mission_id)
        if not mission: return {"status":"not_found"}
        if mission["status"]=="cancelled": return {"status":"cancelled"}
        run=next((item for item in mission["runs"] if int(item["id"])==run_id),None)
        if not run or run["status"]!="running": return {"status":"stale_run"}
        steps=mission.get("steps") or []
        if not steps:
            self.missions.finish_run(user_id,mission_id,run_id,"failed",error="No executable steps were supplied. Add a validated connector action plan.")
            return {"status":"failed","reason":"plan_required"}
        prior=run.get("result") or {}; outputs=prior.get("outputs",[]) if isinstance(prior,dict) else []
        for index in range(step_index,len(steps)):
            step=steps[index]
            installation=next((item for item in self.installations.list_for_user(user_id)
                               if item["connector_key"]==step["connector_key"]),None)
            if not installation:
                self.missions.finish_run(user_id,mission_id,run_id,"failed",result={"outputs":outputs},
                                         error=f"No installation exists for connector '{step['connector_key']}'.")
                return {"status":"failed","step_index":index,"reason":"connector_missing"}
            result=self.actions.request_action(user_id,installation["id"],step["action"],step["arguments"],
                context={"mission_id":mission_id,"run_id":run_id,"step_index":index,
                         "idempotency_key":f"mission-run:{run_id}:step:{index}"})
            if result.get("status")=="approval_required":
                approval=result.get("approval") or {}
                self.missions.pause_for_approval(user_id,mission_id,run_id,approval.get("id"),outputs)
                return {"status":"awaiting_approval","approval_id":approval.get("id"),"step_index":index}
            if result.get("status")!="completed" or not (result.get("result") or {}).get("success"):
                detail=result.get("detail") or (result.get("result") or {}).get("detail") or result.get("status")
                self.missions.finish_run(user_id,mission_id,run_id,"failed",result={"outputs":outputs},
                                         error=f"Step {index+1} did not complete: {detail}.")
                return {"status":"failed","step_index":index}
            outputs.append({"step_index":index,"connector_key":step["connector_key"],"action":step["action"],"result":result["result"]})
            self.missions.save_progress(mission_id,run_id,outputs)
        self.missions.finish_run(user_id,mission_id,run_id,"completed",result={"outputs":outputs})
        return {"status":"completed","steps_completed":len(outputs)}
