from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "vj-trading-super-secret-2026-change-in-prod")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# ── Hardcoded users (no registration needed) ──
USERS = {
    "vijay": {
        "username": "vijay",
        "hashed_password": pwd_context.hash(os.environ.get("VIJAY_PASSWORD", "vj@trading2026")),
        "role": "admin"
    },
    "mentor": {
        "username": "mentor",
        "hashed_password": pwd_context.hash(os.environ.get("MENTOR_PASSWORD", "mentor@view2026")),
        "role": "readonly"
    },
    "peer": {
        "username": "peer",
        "hashed_password": pwd_context.hash(os.environ.get("PEER_PASSWORD", "peer@view2026")),
        "role": "readonly"
    }
}

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def authenticate_user(username: str, password: str):
    user = USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = USERS.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
