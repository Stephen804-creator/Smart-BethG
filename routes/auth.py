from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.auth_service import authenticate_user
from api.dependencies import get_current_user
router=APIRouter(prefix="/auth",tags=["auth"])
class LoginRequest(BaseModel): username:str; password:str
@router.post("/login")
def login(payload:LoginRequest):
    user=authenticate_user(payload.username,payload.password)
    if not user: return {"authenticated":False,"error":"Invalid credentials."}
    return {"authenticated":True,"user":user}
@router.get("/me")
def me(user=Depends(get_current_user)): return user
