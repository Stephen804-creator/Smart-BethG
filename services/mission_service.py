"""Owner-scoped missions with durable queue dispatch and validated connector plans."""
import json, uuid
from database import get_connection
from services.job_queue import JobQueue
from services.capability_registry import CapabilityRegistry

class MissionService:
    VALID_PRIORITIES={"low","normal","high","urgent"}
    TERMINAL_STATUSES={"completed","cancelled"}

    def create(self,user_id,objective,priority="normal",project_id=None,steps=None):
        objective=(objective or "").strip()
        if not objective or len(objective)>12000: raise ValueError("Mission objective must be between 1 and 12000 characters.")
        if priority not in self.VALID_PRIORITIES: raise ValueError("Invalid mission priority.")
        if project_id is not None and not self._owns_project(user_id,project_id): raise ValueError("Project not found for this user.")
        cleaned=self.validate_steps(steps or [])
        conn=get_connection()
        try:
            cursor=conn.execute("INSERT INTO missions(user_id,project_id,objective,status,priority,plan_json,updated_at) VALUES (?,?,?,'pending',?,?,CURRENT_TIMESTAMP)",
                                (user_id,project_id,objective,priority,json.dumps(cleaned,ensure_ascii=False)))
            mission_id=cursor.lastrowid; conn.commit()
        finally: conn.close()
        return self.get(user_id,mission_id)

    def list_for_user(self,user_id):
        conn=get_connection()
        try:
            rows=conn.execute("SELECT m.id,m.user_id,m.project_id,m.objective,m.status,m.priority,m.plan_json,m.created_at,m.updated_at,p.name AS project_name FROM missions m LEFT JOIN projects p ON p.id=m.project_id WHERE m.user_id=? ORDER BY m.updated_at DESC,m.id DESC",(user_id,)).fetchall()
            return [self._decode_mission(row) for row in rows]
        finally: conn.close()

    def get(self,user_id,mission_id):
        conn=get_connection()
        try:
            row=conn.execute("SELECT m.id,m.user_id,m.project_id,m.objective,m.status,m.priority,m.plan_json,m.created_at,m.updated_at,p.name AS project_name FROM missions m LEFT JOIN projects p ON p.id=m.project_id WHERE m.id=? AND m.user_id=? LIMIT 1",(mission_id,user_id)).fetchone()
            if not row: return None
            mission=self._decode_mission(row)
            runs=conn.execute("SELECT id,mission_id,attempt_number,status,error,started_at,completed_at,result_json,idempotency_key FROM mission_runs WHERE mission_id=? ORDER BY attempt_number DESC",(mission_id,)).fetchall()
            mission["runs"]=[]
            for run in runs:
                item=dict(run)
                try: item["result"]=json.loads(item.pop("result_json")) if item.get("result_json") else None
                except (TypeError,json.JSONDecodeError): item["result"]=None; item.pop("result_json",None)
                mission["runs"].append(item)
            return mission
        finally: conn.close()

    def start_run(self,user_id,mission_id):
        mission=self.get(user_id,mission_id)
        if not mission: return None
        if mission["status"] in self.TERMINAL_STATUSES: raise ValueError("A completed or cancelled mission cannot be started again.")
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE missions SET status='running',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status IN ('pending','failed')",(mission_id,user_id))
            if cursor.rowcount!=1:
                conn.rollback(); raise ValueError("This mission is already running or no longer startable.")
            count=conn.execute("SELECT COUNT(*) AS count FROM mission_runs WHERE mission_id=?",(mission_id,)).fetchone()["count"]
            attempt=int(count)+1; run_key=str(uuid.uuid4())
            run_cursor=conn.execute("INSERT INTO mission_runs(mission_id,attempt_number,status,idempotency_key) VALUES (?,?,'running',?)",(mission_id,attempt,run_key))
            run_id=run_cursor.lastrowid
            conn.execute("INSERT INTO logs(mission_id,user_id,level,event_type,message) VALUES (?,?,'info','mission_run_queued',?)",
                         (mission_id,user_id,f"Mission run {run_id} queued (attempt {attempt})."))
            JobQueue().enqueue_in_transaction(conn,user_id,"mission.execute",
                {"mission_id":mission_id,"run_id":run_id,"step_index":0},
                idempotency_key=f"mission-run:{run_id}:step:0",
                priority={"low":-1,"normal":0,"high":1,"urgent":2}[mission["priority"]])
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: conn.close()
        return self.get(user_id,mission_id)

    def save_progress(self,mission_id,run_id,outputs):
        payload=json.dumps({"outputs":outputs},ensure_ascii=False,default=str)
        if len(payload)>100000: raise ValueError("Mission progress exceeds the 100 KB limit.")
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE mission_runs SET result_json=? WHERE id=? AND mission_id=? AND status='running'",(payload,run_id,mission_id))
            conn.commit(); return cursor.rowcount==1
        finally: conn.close()

    def pause_for_approval(self,user_id,mission_id,run_id,approval_id,outputs):
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE mission_runs SET status='awaiting_approval',result_json=? WHERE id=? AND mission_id=? AND status='running'",
                                (json.dumps({"outputs":outputs,"approval_id":approval_id}),run_id,mission_id))
            if cursor.rowcount!=1: conn.rollback(); raise ValueError("Mission run could not be paused for approval.")
            conn.execute("UPDATE missions SET status='awaiting_approval',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='running'",(mission_id,user_id))
            conn.commit()
        finally: conn.close()

    def resume_after_approval(self,user_id,mission_id,run_id):
        conn=get_connection()
        try:
            conn.execute("UPDATE mission_runs SET status='running',error=NULL WHERE id=? AND mission_id=? AND status='awaiting_approval'",(run_id,mission_id))
            conn.execute("UPDATE missions SET status='running',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='awaiting_approval'",(mission_id,user_id))
            conn.commit()
        finally: conn.close()

    def fail_after_approval(self,user_id,mission_id,run_id,error):
        conn=get_connection()
        try:
            conn.execute("UPDATE mission_runs SET status='failed',error=?,completed_at=CURRENT_TIMESTAMP WHERE id=? AND mission_id=? AND status IN ('awaiting_approval','running')",(str(error)[:4000],run_id,mission_id))
            conn.execute("UPDATE missions SET status='failed',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status IN ('awaiting_approval','running')",(mission_id,user_id))
            conn.commit()
        finally: conn.close()

    def finish_run(self,user_id,mission_id,run_id,status,result=None,error=None):
        if status not in {"completed","failed"}: raise ValueError("Run status must be completed or failed.")
        mission=self.get(user_id,mission_id)
        if not mission: return None
        run=next((item for item in mission["runs"] if item["id"]==run_id),None)
        if not run: return None
        if run["status"]!="running" or mission["status"]!="running": raise ValueError("Only the active run can be completed or failed.")
        if error is not None and len(str(error))>4000: raise ValueError("Run error description exceeds the 4000-character limit.")
        result_json=json.dumps(result,ensure_ascii=False,default=str) if result is not None else None
        if result_json and len(result_json)>100000: raise ValueError("Run result exceeds the 100 KB limit.")
        final_status="completed" if status=="completed" else "failed"; conn=get_connection()
        try:
            cursor=conn.execute("UPDATE mission_runs SET status=?,error=?,result_json=?,completed_at=CURRENT_TIMESTAMP WHERE id=? AND mission_id=? AND status='running'",
                                (status,error,result_json,run_id,mission_id))
            if cursor.rowcount!=1:
                conn.rollback(); raise ValueError("Mission run state changed; refresh and try again.")
            conn.execute("UPDATE missions SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(final_status,mission_id,user_id))
            conn.execute("INSERT INTO logs(mission_id,user_id,level,event_type,message) VALUES (?,?,?,?,?)",
                         (mission_id,user_id,"info" if status=="completed" else "error","mission_run_"+status,f"Mission run {run_id} marked {status}."))
            conn.commit()
        finally: conn.close()
        return self.get(user_id,mission_id)

    def cancel(self,user_id,mission_id):
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE missions SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status IN ('pending','running','failed','awaiting_approval')",(mission_id,user_id))
            if cursor.rowcount!=1:
                conn.rollback(); return False
            conn.execute("UPDATE mission_runs SET status='cancelled',error='Cancelled by owner.',completed_at=CURRENT_TIMESTAMP WHERE mission_id=? AND status IN ('running','awaiting_approval')",(mission_id,))
            conn.execute("INSERT INTO logs(mission_id,user_id,level,event_type,message) VALUES (?,?,'info','mission_cancelled','Mission cancelled by owner.')",(mission_id,user_id))
            conn.commit()
        finally: conn.close()
        return True

    @staticmethod
    def validate_steps(steps):
        if not isinstance(steps,list) or len(steps)>25: raise ValueError("Mission steps must be a list of at most 25 items.")
        registry=CapabilityRegistry(); cleaned=[]
        for index,step in enumerate(steps):
            if not isinstance(step,dict) or not isinstance(step.get("connector_key"),str) or not isinstance(step.get("action"),str):
                raise ValueError(f"Mission step {index+1} requires connector_key and action.")
            args=step.get("arguments",{})
            try: registry.validate_arguments(step["connector_key"],step["action"],args)
            except ValueError as exc: raise ValueError(f"Mission step {index+1}: {exc}") from exc
            cleaned.append({"connector_key":step["connector_key"],"action":step["action"],"arguments":args})
        if len(json.dumps(cleaned,ensure_ascii=False))>100000: raise ValueError("Mission plan exceeds the 100 KB limit.")
        return cleaned

    @staticmethod
    def _decode_mission(row):
        item=dict(row)
        try: item["steps"]=json.loads(item.pop("plan_json") or "[]")
        except (TypeError,json.JSONDecodeError): item["steps"]=[]; item.pop("plan_json",None)
        return item

    @staticmethod
    def _owns_project(user_id,project_id):
        conn=get_connection()
        try: return conn.execute("SELECT id FROM projects WHERE id=? AND user_id=? LIMIT 1",(project_id,user_id)).fetchone() is not None
        finally: conn.close()
