from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import get_db
from models import User, Role
import logging


logger = logging.getLogger(__name__)

SECRET_KEY = ""  # Replace with a secure key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

async def get_current_user_role(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = await get_current_user(token, db)
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return role.role

def check_super_admin(user: User, db: Session):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if not role:
        logger.error(f"Role not found for user {user.email}")
        raise HTTPException(status_code=500, detail="User role not found")
    if role.role != "super_admin":
        logger.warning(f"Unauthorized access by {user.email} (role: {role.role})")
        raise HTTPException(status_code=403, detail="Only SuperAdmins can access this endpoint")
    return role

def check_authorization(user: User, org_id: int, db: Session):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.role != "super_admin" and user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")