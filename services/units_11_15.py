"""Initial owner-scoped foundations for specialist planning, evidence, evaluation, routing and lifecycle."""
import json, os
from datetime import datetime, timezone
from database import get_connection
from providers.model_catalog import MODEL_CATALOG

ROLES = {
 "planner": "Break the objective into ordered, testable tasks.",
 "researcher": "Gather evidence from explicitly available sources.",
 "critic": "Identify assumptions, risks and missing evidence.",
 "executor": "Use only approved registered capabilities.",
 "reviewer": "Check outputs against acceptance criteria.",
}
PROVIDER_ENV = {"openai":("OPENAI_API_KEY",),"anthropic":("ANTHROPIC_API_KEY",),
 "google":("GOOGLE_API_KEY","GEMINI_API_KEY"),"groq":("GROQ_API_KEY",),"openrouter":("OPENROUTER_API_KEY",)}
EXPORT_TABLES = ("projects","missions","mission_runs","files","memory","research","evidence","workflows","artifacts","social_content","social_content_versions","logs")


class DecisionLedger:
 def record(self, user_id, decision_type, decision, evidence=None, mission_id=None, workflow_run_id=None, outcome=None):
  if not isinstance(decision_type,str) or not decision_type.strip() or len(decision_type)>100: raise ValueError("decision_type must be 1–100 characters.")
  if not isinstance(decision,dict) or len(json.dumps(decision))>20000: raise ValueError("decision must be an object no larger than 20 KB.")
  evidence=evidence or []
  if not isinstance(evidence,list) or len(evidence)>100: raise ValueError("evidence must be a list of at most 100 items.")
  c=get_connection()
  try:
   if mission_id is not None and not c.execute("SELECT id FROM missions WHERE id=? AND user_id=?",(mission_id,user_id)).fetchone(): raise ValueError("Mission not found for this user.")
   if workflow_run_id is not None and not c.execute("SELECT id FROM workflow_runs WHERE id=? AND user_id=?",(workflow_run_id,user_id)).fetchone(): raise ValueError("Workflow run not found for this user.")
   cur=c.execute("INSERT INTO decision_ledger(user_id,mission_id,workflow_run_id,decision_type,decision_json,evidence_json,outcome) VALUES (?,?,?,?,?,?,?)",
    (user_id,mission_id,workflow_run_id,decision_type,json.dumps(decision,ensure_ascii=False),json.dumps(evidence,ensure_ascii=False),str(outcome)[:2000] if outcome else None))
   rid=cur.lastrowid; c.commit()
   return self.get(user_id,rid)
  finally: c.close()
 def get(self,user_id,rid):
  c=get_connection()
  try:
   row=c.execute("SELECT * FROM decision_ledger WHERE id=? AND user_id=?",(rid,user_id)).fetchone()
   if not row:return None
   d=dict(row)
   for source,target,default in (("decision_json","decision",{}),("evidence_json","evidence",[])):
    try:d[target]=json.loads(d.pop(source) or json.dumps(default))
    except (TypeError,json.JSONDecodeError):d[target]=default;d.pop(source,None)
   return d
  finally:c.close()
 def list(self,user_id,limit=50):
  c=get_connection()
  try: rows=c.execute("SELECT id FROM decision_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",(user_id,max(1,min(100,int(limit))))).fetchall()
  finally:c.close()
  return [self.get(user_id,r["id"]) for r in rows]


class SpecialistPlanner:
 def create(self,user_id,objective,specialists=None):
  objective=(objective or "").strip(); roles=specialists or ["planner","critic","reviewer"]
  if not objective or len(objective)>12000:raise ValueError("Objective must be between 1 and 12000 characters.")
  if not isinstance(roles,list) or not 1<=len(roles)<=5 or len(set(roles))!=len(roles) or any(r not in ROLES for r in roles):raise ValueError("Choose 1–5 unique supported specialist roles.")
  assignments=[{"role":r,"responsibility":ROLES[r],"task":objective,"requires_approval_for_side_effects":r=="executor"} for r in roles]
  c=get_connection()
  try:
   cur=c.execute("INSERT INTO agent_team_runs(user_id,objective,assignments_json,status) VALUES (?,?,?,'planned')",(user_id,objective,json.dumps(assignments,ensure_ascii=False)))
   rid=cur.lastrowid;c.commit()
  finally:c.close()
  return {"id":rid,"objective":objective,"status":"planned","assignments":assignments,"execution_status":"planning_only","note":"Independent specialist model execution is not enabled."}
 def list(self,user_id):
  c=get_connection()
  try:rows=c.execute("SELECT id,objective,assignments_json,status,created_at,updated_at FROM agent_team_runs WHERE user_id=? ORDER BY id DESC LIMIT 50",(user_id,)).fetchall()
  finally:c.close()
  result=[]
  for row in rows:
   d=dict(row)
   try:d["assignments"]=json.loads(d.pop("assignments_json") or "[]")
   except (TypeError,json.JSONDecodeError):d["assignments"]=[];d.pop("assignments_json",None)
   result.append(d)
  return result


class AgentEvaluator:
 RUBRIC_VERSION="deterministic-v1"
 def evaluate(self,user_id,subject_type,subject_id,output,criteria=None):
  if subject_type not in {"mission","workflow","artifact","response"}:raise ValueError("Unsupported evaluation subject type.")
  if not isinstance(output,(str,dict,list)):raise ValueError("Output must be text, an object, or a list.")
  text=output if isinstance(output,str) else json.dumps(output,ensure_ascii=False)
  criteria=criteria or ["non_empty","bounded_size","structured_output"]
  allowed={"non_empty","bounded_size","structured_output","contains_citations"}
  if not isinstance(criteria,list) or len(criteria)>10 or any(x not in allowed for x in criteria):raise ValueError("Unsupported evaluation criteria.")
  findings=[]
  for criterion in criteria:
   passed={"non_empty":bool(text.strip()),"bounded_size":len(text)<=100000,"structured_output":isinstance(output,(dict,list)),
    "contains_citations":("http://" in text or "https://" in text or "source" in text.lower())}[criterion]
   findings.append({"criterion":criterion,"passed":passed,"weight":1})
  score=sum(f["passed"] for f in findings)/max(1,len(findings));c=get_connection()
  try:
   cur=c.execute("INSERT INTO agent_evaluations(user_id,subject_type,subject_id,rubric_version,score,findings_json,evaluator_type) VALUES (?,?,?,?,?,?, 'deterministic')",
    (user_id,subject_type,str(subject_id)[:200] if subject_id is not None else None,self.RUBRIC_VERSION,score,json.dumps(findings)))
   rid=cur.lastrowid;c.commit()
  finally:c.close()
  return {"id":rid,"subject_type":subject_type,"subject_id":subject_id,"rubric_version":self.RUBRIC_VERSION,"score":score,"findings":findings,
   "evaluator_type":"deterministic","warning":"This score is not proof of factual correctness."}


class CostAwareRouter:
 def preview(self,task_type="general",complexity="balanced",max_cost_usd=None,prefer_provider=None):
  tier=complexity if complexity in {"fast","balanced","capable"} else ("capable" if task_type in {"code_review","architecture","complex_reasoning"} else "balanced")
  providers=[prefer_provider] if prefer_provider in MODEL_CATALOG else list(MODEL_CATALOG); candidates=[]
  for provider in providers:
   if not any(os.getenv(k,"").strip() for k in PROVIDER_ENV.get(provider,())):continue
   for model in MODEL_CATALOG[provider]["models"]:
    if model.get("tier")!=tier:continue
    p=model.get("pricing_usd_per_million") or {};estimate=(float(p.get("input",0))+float(p.get("output",0)))/1000
    if max_cost_usd is not None and estimate>max(0,float(max_cost_usd)):continue
    candidates.append({"provider":provider,"model":model["id"],"label":model.get("label"),"tier":tier,"estimated_usd_per_1k_in_and_out_tokens":round(estimate,8)})
  candidates.sort(key=lambda x:(x["estimated_usd_per_1k_in_and_out_tokens"],x["provider"],x["model"]))
  if not candidates:return {"mode":"unavailable","tier":tier,"selected":None,"provider_call_made":False,"reason":"No configured provider meets the tier and cost ceiling."}
  return {"mode":"auto","tier":tier,"selected":candidates[0],"alternatives":candidates[1:5],"provider_call_made":False,
   "budget_reserved":False,"warning":"Catalog estimate only; this preview makes no provider call and reserves no usage budget."}


class AccountLifecycle:
 def export(self,user_id):
  c=get_connection()
  try:
   user=c.execute("SELECT id,username,status,role,created_at FROM users WHERE id=?",(user_id,)).fetchone()
   if not user:return None
   result={"exported_at":datetime.now(timezone.utc).isoformat(),"account":dict(user),"data":{}}
   for table in EXPORT_TABLES:
    cols=c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position",(table,)).fetchall()
    if "user_id" not in [r["column_name"] for r in cols]:continue
    rows=c.execute(f"SELECT * FROM {table} WHERE user_id=? ORDER BY 1 LIMIT 10000",(user_id,)).fetchall()
    result["data"][table]=[dict(r) for r in rows]
   return result
  finally:c.close()
 def request(self,user_id,request_type):
  if request_type not in {"data_export","account_deletion"}:raise ValueError("Unsupported lifecycle request.")
  c=get_connection()
  try:
   cur=c.execute("INSERT INTO account_lifecycle_requests(user_id,request_type,status,details_json) VALUES (?,?,'pending','{}')",(user_id,request_type))
   rid=cur.lastrowid;c.commit()
  finally:c.close()
  note=("Deletion is not performed automatically; verified confirmation, recovery safeguards and operational review are still required."
        if request_type=="account_deletion" else "Request recorded; use the data-export endpoint to generate the current owner-scoped package.")
  return {"id":rid,"request_type":request_type,"status":"pending","note":note}
 def list(self,user_id):
  c=get_connection()
  try:rows=c.execute("SELECT id,request_type,status,details_json,created_at,updated_at FROM account_lifecycle_requests WHERE user_id=? ORDER BY id DESC LIMIT 50",(user_id,)).fetchall()
  finally:c.close()
  result=[]
  for row in rows:
   d=dict(row)
   try:d["details"]=json.loads(d.pop("details_json") or "{}")
   except (TypeError,json.JSONDecodeError):d["details"]={};d.pop("details_json",None)
   result.append(d)
  return result
