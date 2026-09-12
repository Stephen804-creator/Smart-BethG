from fastapi import APIRouter
from pydantic import BaseModel
from services.auth_service import authenticate_user
router=APIRouter(prefix="/auth",tags=["authentication"])
class LoginPayload(BaseModel): username:str; password:str
@router.post("/login")
def login(p:LoginPayload):
    user=authenticate_user(p.username,p.password)
    if not user: return {"authenticated":False}
    return {"authenticated":True,"user":user}
