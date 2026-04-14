"""Auth router — login and token refresh."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from ..auth.jwt_handler import create_access_token, verify_token

router = APIRouter()
security = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Demo user store (replace with real DB in production)
DEMO_USERS = {
    "analyst": {"password": "demo123", "role": "analyst", "tenant_id": "acme"},
    "admin": {"password": "admin123", "role": "admin", "tenant_id": "acme"},
}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = DEMO_USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["tenant_id"] != req.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    token = create_access_token(
        data={
            "sub": req.username,
            "tenant_id": req.tenant_id,
            "role": user["role"],
        }
    )
    return TokenResponse(access_token=token, expires_in=3600)


@router.post("/verify")
async def verify(token: str = Depends(security)):
    payload = verify_token(token.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"valid": True, "payload": payload}
