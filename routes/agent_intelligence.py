"""Authenticated APIs for Units 11–15 foundations."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from api.dependencies import get_current_user
from services.units_11_15 import DecisionLedger, SpecialistPlanner, AgentEvaluator, CostAwareRouter, AccountLifecycle

router = APIRouter(prefix="/agent-system", tags=["agent-system"])

class DecisionInput(BaseModel):
    decision_type: str = Field(min_length=1, max_length=100)
    decision: dict
    evidence: list[dict] = Field(default_factory=list, max_length=100)
    mission_id: int | None = Field(default=None, ge=1)
    workflow_run_id: int | None = Field(default=None, ge=1)
    outcome: str | None = Field(default=None, max_length=2000)

class TeamPlanInput(BaseModel):
    objective: str = Field(min_length=1, max_length=12000)
    specialists: list[str] = Field(default_factory=lambda: ["planner", "critic", "reviewer"], min_length=1, max_length=5)

class EvaluationInput(BaseModel):
    subject_type: str
    subject_id: str | None = Field(default=None, max_length=200)
    output: str | dict | list
    criteria: list[str] = Field(default_factory=lambda: ["non_empty", "bounded_size", "structured_output"], max_length=10)

class RoutePreviewInput(BaseModel):
    task_type: str = Field(default="general", max_length=100)
    complexity: str = "balanced"
    max_cost_usd: float | None = Field(default=None, ge=0, le=1000)
    prefer_provider: str | None = Field(default=None, max_length=40)

class LifecycleRequest(BaseModel):
    request_type: str

@router.post("/decisions")
def record_decision(payload: DecisionInput, user=Depends(get_current_user)):
    try:
        return DecisionLedger().record(user["id"], payload.decision_type, payload.decision, payload.evidence,
                                       payload.mission_id, payload.workflow_run_id, payload.outcome)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.get("/decisions")
def list_decisions(limit: int = 50, user=Depends(get_current_user)):
    return {"decisions": DecisionLedger().list(user["id"], limit)}

@router.post("/specialist-plans")
def create_specialist_plan(payload: TeamPlanInput, user=Depends(get_current_user)):
    try:
        return SpecialistPlanner().create(user["id"], payload.objective, payload.specialists)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.get("/specialist-plans")
def list_specialist_plans(user=Depends(get_current_user)):
    return {"plans": SpecialistPlanner().list(user["id"])}

@router.post("/evaluations")
def evaluate_output(payload: EvaluationInput, user=Depends(get_current_user)):
    try:
        return AgentEvaluator().evaluate(user["id"], payload.subject_type, payload.subject_id, payload.output, payload.criteria)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.post("/model-route-preview")
def model_route_preview(payload: RoutePreviewInput, user=Depends(get_current_user)):
    return CostAwareRouter().preview(payload.task_type, payload.complexity, payload.max_cost_usd, payload.prefer_provider)

@router.get("/account/data-export")
def export_account_data(user=Depends(get_current_user)):
    data = AccountLifecycle().export(user["id"])
    if data is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return JSONResponse(content=data, headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="smart-bethg-data-export.json"'})

@router.post("/account/lifecycle-requests")
def create_lifecycle_request(payload: LifecycleRequest, user=Depends(get_current_user)):
    try:
        return AccountLifecycle().request(user["id"], payload.request_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.get("/account/lifecycle-requests")
def list_lifecycle_requests(user=Depends(get_current_user)):
    return {"requests": AccountLifecycle().list(user["id"])}
