"""Owner-scoped job status API; only trusted worker processes execute jobs."""
from fastapi import APIRouter,Depends,HTTPException,Query
from api.dependencies import get_current_user,get_job_queue
router=APIRouter(prefix="/jobs",tags=["jobs"])

@router.get("")
def list_jobs(limit:int=Query(default=50,ge=1,le=100),user=Depends(get_current_user),service=Depends(get_job_queue)):
    return {"jobs":service.list_for_user(user["id"],limit)}

@router.get("/{job_id}")
def get_job(job_id:str,user=Depends(get_current_user),service=Depends(get_job_queue)):
    job=service.get_for_user(user["id"],job_id)
    if not job: raise HTTPException(status_code=404,detail="Job not found.")
    return job

@router.delete("/{job_id}")
def cancel_job(job_id:str,user=Depends(get_current_user),service=Depends(get_job_queue)):
    if not service.cancel(user["id"],job_id): raise HTTPException(status_code=409,detail="Only a queued job can be cancelled.")
    return {"cancelled":True}
