import sys
import os
import logging
import time
import json
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.routing import APIRouter

from database import engine, SessionLocal, get_db
from models import Base, User, Role, RoleName, UsageLog, Organization, Subscription, ApiKey
from auth import (
    get_current_user,
    create_access_token,
    verify_password,
    get_password_hash,
    OAuth2PasswordRequestForm,
    check_authorization,
)
from orgManagement import router as org_router
from subscription import router as subscription_router
from analytics import router as analytics_router
from dashboard import router as dashboard_router
from superadmin import seed_super_admin
from vto import router as vto_router
from constants import VTO_ENDPOINTS

# ==================== Logging ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FastAPI app ====================
app = FastAPI()

# ==================== CORS ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:3000", "https://192.168.50.148:3000", "https://192.168.0.111:3000", "https://localhost:42414", "https://192.168.0.111:42414", "https://127.0.0.1:42414", "https://192.168.50.148:42414", "https://optimosight.github.io","https://103.174.51.143:42414"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Debug Endpoints ====================
@app.get("/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": getattr(route, "methods", None)
        })
    return routes

@app.get("/api/debug/test")
async def debug_test():
    return {"message": "API debug endpoint is working", "timestamp": datetime.utcnow()}

@app.get("/api/debug/db-check")
async def debug_db_check(db: Session = Depends(get_db)):
    try:
        result = db.execute("SELECT 1").first()
        return {"db_status": "connected", "result": result[0] if result else None}
    except Exception as e:
        return {"db_status": "error", "message": str(e)}

@app.get("/api/debug/api-keys")
async def debug_api_keys(db: Session = Depends(get_db)):
    api_keys = db.query(ApiKey).all()
    return {
        "api_keys": [
            {
                "id": key.id,
                "api_key": key.api_key,
                "organization_id": key.organization_id,
                "is_active": key.is_active,
                "created_at": key.created_at.isoformat() if key.created_at else None
            }
            for key in api_keys
        ]
    }

# ==================== API Keys Endpoint ====================
@app.get("/api/api-keys")
async def get_api_key(
    org_id: int, 
    is_active: bool = True, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get API key for an organization (for Admin users)"""
    logger.info(f"API keys endpoint called with org_id: {org_id}, is_active: {is_active}")
    
    # Check authorization - only admin users can access their org's API key
    check_authorization(current_user, org_id, db)
    
    # Query the database for active API key
    api_key = db.query(ApiKey).filter(
        ApiKey.organization_id == org_id,
        ApiKey.is_active == is_active
    ).first()
    
    if not api_key:
        logger.warning(f"No active API key found for organization {org_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active API key found for this organization"
        )
    
    logger.info(f"API key found for organization {org_id}")
    return {"api_key": api_key.api_key}

# ==================== Super Admin Static Key Endpoint ====================
@app.get("/api/super-admin-key")
async def get_super_admin_key(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the static super admin API key (only for super admin users)"""
    # Check if user is super admin
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    if not role or role.role != RoleName.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin users can access this endpoint"
        )
    
    return {"api_key": "OptimoSight987654321"}

# ==================== User Endpoints ====================
@app.get("/me")
async def get_current_user_details(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User role not found")
    return {
        "email": current_user.email,
        "role": role.role,
        "org_id": current_user.org_id
    }

# ==================== Request logging middleware ====================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Received request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# ==================== API usage logging middleware ====================
@app.middleware("http")
async def log_api_usage(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    processing_time = int((time.time() - start_time) * 1000)

    if getattr(request.state, "usage_logged", False):
        return response

    if request.url.path not in VTO_ENDPOINTS:
        return response

    db = next(get_db())
    try:
        user = None
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            try:
                user = await get_current_user(token, db)
            except Exception as e:
                logger.debug(f"No valid user for request: {e}")

        organization_id = None
        api_key_id = None

        api_key_str = request.headers.get("X-API-Key")
        if api_key_str:
            api_key = db.query(ApiKey).filter(ApiKey.api_key == api_key_str, ApiKey.is_active == True).first()
            if api_key:
                organization_id = api_key.organization_id
                api_key_id = api_key.id
            else:
                # Check if it's the super admin static key
                if api_key_str == "OptimoSight987654321":
                    # For super admin, use the first organization
                    first_org = db.query(Organization).first()
                    if first_org:
                        organization_id = first_org.id
                        api_key_id = None  # No specific API key ID for super admin
                else:
                    logger.warning(f"Invalid or inactive API key: {api_key_str}")

        if not organization_id and user:
            role = db.query(Role).filter(Role.id == user.role_id).first()
            if role and role.role != RoleName.super_admin:
                organization_id = user.org_id
                if organization_id:
                    org_exists = db.query(Organization).filter(Organization.id == organization_id).first()
                    if not org_exists:
                        logger.warning(f"Invalid organization_id {organization_id} for user {user.email}")
                        organization_id = None
                    else:
                        api_key = db.query(ApiKey).filter(ApiKey.organization_id == organization_id, ApiKey.is_active == True).first()
                        api_key_id = api_key.id if api_key else None

        if organization_id:
            log = UsageLog(
                organization_id=organization_id,
                api_key_id=api_key_id,
                endpoint=str(request.url.path),
                request_data=json.dumps({"method": request.method}),
                response_status=response.status_code,
                processing_time_ms=processing_time,
                timestamp=datetime.utcnow(),
            )
            db.add(log)
            db.commit()
            logger.debug(f"Logged usage: endpoint={request.url.path}, org_id={organization_id}, api_key_id={api_key_id}")
    except Exception as e:
        logger.error(f"Error logging API usage: {str(e)}")
        db.rollback()
    finally:
        db.close()

    return response

# ==================== VTO frontend routes ====================
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")

# Serve static files
app.mount("/api/vto/static", StaticFiles(directory=frontend_path), name="frontend_static")

# Include VTO API router
app.include_router(vto_router)

# Serve index.html
@app.get("/api/vto/")
async def serve_index():
    index_path = os.path.join(frontend_path, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    with open(index_path, "r") as f:
        return HTMLResponse(content=f.read())

# Redirect for cleaner URL
@app.get("/api/vto")
async def redirect_vto():
    return RedirectResponse(url="/api/vto/", status_code=307)

# ==================== Include backend routers ====================
app.include_router(subscription_router, prefix="/api", tags=["Subscriptions"])
app.include_router(org_router, prefix="/api", tags=["Organizations"])
app.include_router(analytics_router)
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])

# ==================== Database initialization ====================
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute("SELECT 1")
        logger.info("Database connection successful")
        for role_name in RoleName:
            if not db.query(Role).filter(Role.role == role_name).first():
                db.add(Role(role=role_name, created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
                logger.info(f"Seeding role: {role_name}")
        db.commit()
        plans = [
            {"plan_name": "Basic", "price": 99.99, "api_limit": 10000, "billing_period": "monthly"},
            {"plan_name": "Pro", "price": 199.99, "api_limit": 50000, "billing_period": "monthly"},
            {"plan_name": "Enterprise", "price": 499.99, "api_limit": 100000, "billing_period": "yearly"}
        ]
        for plan in plans:
            if not db.query(Subscription).filter(Subscription.plan_name == plan["plan_name"]).first():
                db.add(Subscription(
                    plan_name=plan["plan_name"],
                    price=plan["price"],
                    api_limit=plan["api_limit"],
                    billing_period=plan["billing_period"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                ))
                logger.info(f"Seeded subscription: {plan['plan_name']}")
        db.commit()
        api_key = db.query(ApiKey).filter(ApiKey.organization_id.is_(None), ApiKey.is_active == True).first()
        if not api_key:
            api_key = ApiKey(
                api_key=str(uuid.uuid4()),
                organization_id=None,
                is_active=True,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365)
            )
            db.add(api_key)
            logger.info("Seeded API key for super_admin")
        db.commit()
        seed_super_admin(db)
        db.commit()
        logger.info("Database seeded successfully")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app.router.lifespan_context = lifespan

# ==================== Auth endpoints ====================
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    logger.info(f"Login request: username={form_data.username}")
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = db.query(Role).filter(Role.id == user.role_id).first()
    access_token = create_access_token(data={"sub": user.email, "role": role.role})
    org_id = None if role.role == "super_admin" else user.org_id
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role.role,
        "org_id": org_id
    }

@app.post("/register")
async def register(
    email: str,
    password: str,
    name: str,
    uid: str,
    role: str = "guest",
    org_id: int = None,
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    role_obj = db.query(Role).filter(Role.role == role).first()
    if not role_obj:
        raise HTTPException(status_code=400, detail="Invalid role")
    if role == "admin" and not org_id:
        raise HTTPException(status_code=400, detail="Admin must belong to an organization")
    hashed_password = get_password_hash(password)
    user = User(
        uid=uid,
        org_id=org_id if role == "admin" else None,
        name=name,
        email=email,
        password_hash=hashed_password,
        role_id=role_obj.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully"}

@app.get("/seed-super-admin")
def test_seed_super_admin(db: Session = Depends(get_db)):
    seed_super_admin(db)
    return {"message": "Super_Admin seeding attempted, check logs"}

@app.get("/api/debug/check-api-key/{api_key}")
async def debug_check_api_key(api_key: str, db: Session = Depends(get_db)):
    """Debug endpoint to check if an API key exists and is valid"""
    key = db.query(ApiKey).filter(ApiKey.api_key == api_key).first()
    
    if not key:
        return {"exists": False, "message": "API key not found in database"}
    
    # Check if organization exists
    org = db.query(Organization).filter(Organization.id == key.organization_id).first()
    
    return {
        "exists": True,
        "is_active": key.is_active,
        "organization_id": key.organization_id,
        "organization_exists": org is not None,
        "organization_name": org.name if org else None,
        "created_at": key.created_at,
        "expires_at": key.expires_at,
        "is_expired": key.expires_at and key.expires_at < datetime.utcnow()
    }

@app.get("/api/debug/usage-stats/{org_id}")
async def debug_usage_stats(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check current usage statistics"""
    check_authorization(current_user, org_id, db)
    
    # Get usage count
    usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org_id).count()
    
    # Get subscription limit
    org = db.query(Organization).filter(Organization.id == org_id).first()
    subscription = db.query(Subscription).filter(Subscription.id == org.subscription_id).first() if org else None
    
    return {
        "organization_id": org_id,
        "organization_name": org.name if org else None,
        "usage_count": usage_count,
        "api_limit": subscription.api_limit if subscription else None,
        "remaining_calls": (subscription.api_limit - usage_count) if subscription else None,
        "subscription_plan": subscription.plan_name if subscription else None
    }

# ==================== Run with uvicorn ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=42413)