import sys
import os
import logging
import time
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.routing import APIRouter
from pydantic import BaseModel

# from fastapi.staticfiles import StaticFiles

from database import engine, SessionLocal, get_db
from models import (
    Base, User, Role, RoleName, UsageLog, Organization, Subscription, 
    ApiKey, GuestUsage  # Import GuestUsage from models
)
from auth import get_current_user, create_access_token, verify_password, get_password_hash, OAuth2PasswordRequestForm, check_authorization
from orgManagement import router as org_router
from subscription import router as subscription_router
from analytics import router as analytics_router
from dashboard import router as dashboard_router
from superadmin import seed_super_admin
from vto import router as vto_router
from guest_usage import guest_router  # Import guest_router from guest_usage.py
from constants import VTO_ENDPOINTS, SUPER_ADMIN_API_KEY, GUEST_API_KEY, GUEST_LIMIT, RESET_PERIOD_HOURS
# from utils.guest_usage_utils import get_or_create_guest_usage

from routes.widget_routes import router as widget_router


# ------------------ Logging ------------------
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# ------------------ FastAPI App ------------------
app = FastAPI(title="OptimoSight VTO API", version="2.0.0")

# ------------------ CORS ------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:3000", "https://192.168.50.148:3000", "https://192.168.0.111:3000", "https://localhost:42414", "https://192.168.0.111:42414", "https://127.0.0.1:42414", "https://192.168.50.148:42414", "https://optimosight.github.io", "https://103.174.51.143:42414"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ Middleware ------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Received request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

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
            # Handle guest API key (skip regular logging)
            if api_key_str == GUEST_API_KEY:
                logger.info("Guest API usage - skipping regular usage log")
                return response
                
            # Handle super admin API key
            elif api_key_str == SUPER_ADMIN_API_KEY:
                logger.info("Super admin API usage - skipping regular usage log")
                return response
                
            # Handle regular API key
            else:
                api_key = db.query(ApiKey).filter(ApiKey.api_key == api_key_str, ApiKey.is_active == True).first()
                if api_key:
                    organization_id = api_key.organization_id
                    api_key_id = api_key.id

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

# ------------------ Admin Analytics Endpoint ------------------
@app.get("/api/admin/guest-analytics")
async def get_guest_analytics(db: Session = Depends(get_db)):
    """Get guest usage analytics for admin dashboard"""
    try:
        # Total guest users in last 24 hours
        yesterday = datetime.utcnow() - timedelta(hours=24)
        
        guest_stats = db.query(
            func.count(GuestUsage.id).label('total_guests'),
            func.avg(GuestUsage.usage_count).label('avg_usage'),
            func.sum(GuestUsage.usage_count).label('total_requests'),
            func.count(func.nullif(GuestUsage.usage_count >= GUEST_LIMIT, False)).label('limit_reached_count')
        ).filter(GuestUsage.last_visit >= yesterday).first()
        
        # Peak usage times
        hourly_usage = db.query(
            func.extract('hour', GuestUsage.last_visit).label('hour'),
            func.count(GuestUsage.id).label('users'),
            func.sum(GuestUsage.usage_count).label('requests')
        ).filter(
            GuestUsage.last_visit >= yesterday
        ).group_by(
            func.extract('hour', GuestUsage.last_visit)
        ).all()
        
        return {
            "summary": {
                "total_guest_users": guest_stats.total_guests or 0,
                "average_usage_per_guest": round(guest_stats.avg_usage or 0, 2),
                "total_guest_requests": guest_stats.total_requests or 0,
                "users_reached_limit": guest_stats.limit_reached_count or 0,
                "conversion_potential": guest_stats.limit_reached_count or 0  # Users who hit limit might convert
            },
            "hourly_breakdown": [
                {
                    "hour": int(h.hour),
                    "users": h.users,
                    "requests": h.requests
                } for h in hourly_usage
            ]
        }
    except Exception as e:
        logger.error(f"Error getting guest analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get guest analytics: {str(e)}")

# ------------------ Include Routers ------------------
router = APIRouter()

@router.get("/api-keys")
async def get_api_key(
    org_id: int, 
    is_active: bool = True, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get API key for an organization (for Admin users)"""
    logger.info(f"API keys endpoint called with org_id: {org_id}, is_active: {is_active}")
    check_authorization(current_user, org_id, db)
    
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

@router.get("/super-admin-key")
async def get_super_admin_key(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the static super admin API key (only for super admin users)"""
    # Check if user is super admin
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    if not role or role.role != RoleName.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin users can access this endpoint"
        )
    
    return {"api_key": SUPER_ADMIN_API_KEY}

@router.get("/me")
async def get_current_user_details(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User role not found")
    return {
        "email": current_user.email,
        "role": role.role,
        "org_id": current_user.org_id
    }

# Including all routers to register API endpoints
app.include_router(vto_router)
app.include_router(subscription_router, prefix="/api", tags=["Subscriptions"])
app.include_router(org_router, prefix="/api", tags=["Organizations"])
app.include_router(analytics_router)
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
app.include_router(router, prefix="/api", tags=["Users"])
# app.include_router(guest_router)
app.include_router(guest_router, prefix="/api/guest", tags=["Guest Usage"]) # Include without additional prefix
app.include_router(widget_router, prefix="/widget", tags=["widget"])

logger.info("Included routers: %s", [route.path for route in app.routes if hasattr(route, 'path')])

# ------------------ Database Initialization ------------------
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute("SELECT 1")
        logger.info("Database connected successfully")

        # Create roles
        for role_name in RoleName:
            if not db.query(Role).filter(Role.role == role_name).first():
                db.add(Role(role=role_name, created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
                logger.info(f"Seeded role: {role_name}")
        db.commit()

        # Create subscription plans
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

        # Create super admin API key
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

        # Seed super admin user
        seed_super_admin(db)
        db.commit()
        logger.info("Database seeded successfully")
    except Exception as e:
        logger.error(f"DB init error: {e}")
        db.rollback()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app.router.lifespan_context = lifespan

# ------------------ Auth Models ------------------
class LoginRequest(BaseModel):
    email: str
    password: str

# ------------------ Auth Endpoints ------------------
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

# ------------------ Debug Endpoints ------------------
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

# ------------------ Frontend Serving ------------------
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/api/vto/static", StaticFiles(directory=frontend_path), name="frontend_static")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/vto/")
async def serve_index():
    index_path = os.path.join(frontend_path, "liveMakeup.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend not found")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/vto")
async def redirect_vto():
    return RedirectResponse(url="/api/vto/", status_code=307)

# ------------------ Run HTTPS ------------------
if __name__ == "__main__":
    import uvicorn
    CERT_FILE = './localhost+1.pem'
    KEY_FILE = './localhost+1-key.pem'
    PORT = 42413

    logger.info("Starting FastAPI server with guest usage tracking...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        ssl_certfile=CERT_FILE,
        ssl_keyfile=KEY_FILE
    )