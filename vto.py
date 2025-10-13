from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request, Header, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import httpx
import logging
import hashlib
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from database import get_db
from models import (
    ApiKey, Organization, UsageLog, Subscription, User, TryonSession, 
    Role, RoleName, GuestUsage
)
import os
from constants import VTO_ENDPOINTS
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# VTO_SERVICE_URL = "http://localhost:8001"
# # VTO_SERVICE_URL = "https://vto.onrender.com"

load_dotenv()

# Auto-detect environment and set VTO service URL
if os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER"):
    # Production environment (Render.com, etc.)
    VTO_SERVICE_URL = "https://vto.onrender.com"
    print("🚀 Using PRODUCTION VTO service:", VTO_SERVICE_URL)
else:
    # Development/Local environment
    VTO_SERVICE_URL = "http://localhost:8001"
    print("🔧 Using LOCAL VTO service:", VTO_SERVICE_URL)


router = APIRouter(prefix="/api/vto", tags=["VTO"])

# --- Define Static API Keys ---
SUPER_ADMIN_API_KEY = "OptimoSight987654321"
GUEST_API_KEY = "OptimosightGuest999"
GUEST_LIMIT = 2000
RESET_PERIOD_HOURS = 24

# --- Valid Categories ---
VALID_CATEGORIES = ["lipstick", "eyeshadow", "eyeliner", "foundation", "contour", "concealer", "blush"]

# --- Helper Functions ---
def generate_fingerprint(request: Request) -> tuple[str, str, str]:
    """Generate a unique fingerprint for the guest user"""
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
        request.headers.get("x-real-ip", "") or
        request.client.host
    )
    
    user_agent = request.headers.get("user-agent", "")
    
    fingerprint_data = {
        "ip": client_ip,
        "user_agent": user_agent,
        "accept_language": request.headers.get("accept-language", ""),
        "accept_encoding": request.headers.get("accept-encoding", ""),
    }
    
    fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
    fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
    user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()
    
    return fingerprint_hash, client_ip, user_agent_hash

async def get_or_create_guest_usage(request: Request, db: Session) -> GuestUsage:
    """Get or create guest usage record"""
    fingerprint_hash, client_ip, user_agent_hash = generate_fingerprint(request)
    
    guest_usage = db.query(GuestUsage).filter(
        GuestUsage.fingerprint_hash == fingerprint_hash
    ).first()
    
    if not guest_usage:
        guest_usage = db.query(GuestUsage).filter(
            GuestUsage.ip_address == client_ip,
            GuestUsage.last_visit > datetime.utcnow() - timedelta(hours=RESET_PERIOD_HOURS)
        ).first()
    
    if not guest_usage:
        guest_usage = GuestUsage(
            fingerprint_hash=fingerprint_hash,
            ip_address=client_ip,
            user_agent_hash=user_agent_hash,
            usage_count=0
        )
        db.add(guest_usage)
        db.commit()
        db.refresh(guest_usage)
    else:
        guest_usage.fingerprint_hash = fingerprint_hash
        guest_usage.user_agent_hash = user_agent_hash
        guest_usage.last_visit = datetime.utcnow()
        db.commit()
    
    return guest_usage

# Pydantic models for tracking requests
class ColorUpdateRequest(BaseModel):
    category: str
    color: str
    action: str = "color_update"
    org_id: Optional[int] = None

class MakeupApplicationRequest(BaseModel):
    category: str
    color: str
    action: str = "makeup_apply"
    org_id: Optional[int] = None

async def get_api_key(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    """Enhanced API key validation with guest usage tracking"""
    api_key = x_api_key or request.query_params.get("api_key")
    
    logger.info(f"API key authentication attempt: {api_key}")
    
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    
    if api_key == GUEST_API_KEY:
        logger.info("Guest user access - checking usage limits")
        guest_usage = await get_or_create_guest_usage(request, db)
        
        if guest_usage.usage_count >= GUEST_LIMIT:
            if guest_usage.last_visit < datetime.utcnow() - timedelta(hours=RESET_PERIOD_HOURS):
                guest_usage.usage_count = 0
                guest_usage.last_visit = datetime.utcnow()
                db.commit()
                logger.info("Guest usage reset after 24 hours")
            else:
                logger.warning(f"Guest usage limit exceeded: {guest_usage.usage_count}/{GUEST_LIMIT}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
                    detail={
                        "message": "Guest usage limit reached. Please subscribe to continue.",
                        "usage_count": guest_usage.usage_count,
                        "limit": GUEST_LIMIT,
                        "reset_time": (guest_usage.last_visit + timedelta(hours=RESET_PERIOD_HOURS)).isoformat()
                    }
                )
        
        return type('obj', (object,), {
            'api_key': api_key,
            'organization_id': None,
            'id': None,
            'is_super_admin': False,
            'is_guest': True,
            'guest_usage': guest_usage
        })()
    
    if api_key == SUPER_ADMIN_API_KEY:
        first_org = db.query(Organization).first()
        if not first_org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organizations found")
        
        logger.info(f"Super admin access granted for organization: {first_org.id}")
        return type('obj', (object,), {
            'api_key': api_key,
            'organization_id': first_org.id,
            'id': None,
            'is_super_admin': True,
            'is_guest': False
        })()
    
    key = db.query(ApiKey).filter(ApiKey.api_key == api_key, ApiKey.is_active == True).first()
    if not key:
        logger.warning(f"Invalid API key attempt: {api_key}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key")
    
    org = db.query(Organization).filter(Organization.id == key.organization_id).first()
    if not org:
        logger.warning(f"API key {api_key} has invalid organization_id: {key.organization_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organization")
    
    logger.info(f"API key validated for organization: {org.id} - {org.name}")
    key.is_super_admin = False
    key.is_guest = False
    return key

async def increment_guest_usage_if_needed(
    auth_info,
    db: Session,
    request: Request
):
    """Increment guest usage count if this is a guest user"""
    if hasattr(auth_info, 'is_guest') and auth_info.is_guest:
        guest_usage = getattr(auth_info, 'guest_usage', None)
        if guest_usage:
            guest_usage.usage_count += 1
            guest_usage.last_visit = datetime.utcnow()
            db.commit()
            logger.info(f"Guest usage incremented to: {guest_usage.usage_count}/{GUEST_LIMIT}")
            if guest_usage.usage_count >= GUEST_LIMIT:
                logger.warning("Guest usage limit reached after increment")
                return True
    return False

async def log_usage(
    db: Session,
    endpoint: str,
    organization_id: int,
    api_key_id: Optional[int],
    response_status: int,
    request_data: dict,
    processing_time_ms: int,
    request: Request = None,
    is_super_admin: bool = False,
    is_guest: bool = False
):
    """Log API usage for non-Super Admin and non-Guest users only"""
    if is_super_admin or is_guest:
        logger.info(f"Skipping usage log for Super Admin/Guest at endpoint: {endpoint}")
        return
    
    if endpoint not in VTO_ENDPOINTS:
        return
    try:
        usage_log = UsageLog(
            organization_id=organization_id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            request_data=json.dumps(request_data),
            response_status=response_status,
            processing_time_ms=processing_time_ms,
            timestamp=datetime.utcnow(),
        )
        db.add(usage_log)
        db.commit()
        logger.debug(f"Logged usage: endpoint={endpoint}, org_id={organization_id}, api_key_id={api_key_id}")
        if request:
            request.state.usage_logged = True
    except Exception as e:
        logger.error(f"Error logging usage: {str(e)}")
        db.rollback()

async def log_tryon_session(
    db: Session,
    organization_id: int,
    request_data: dict,
    processing_time_ms: int,
    endpoint: str,
    request: Request,
    api_key_id: Optional[int] = None,
    is_super_admin: bool = False,
    is_guest: bool = False
):
    """Log a session to TryonSession table for non-Super Admin and non-Guest users only"""
    if is_super_admin or is_guest:
        logger.info(f"Skipping TryonSession log for Super Admin/Guest at endpoint: {endpoint}")
        return
    
    try:
        user = db.query(User).filter(User.org_id == organization_id, User.is_active == True).first()
        if not user:
            logger.warning(f"No active user found for org_id={organization_id}, skipping TryonSession log")
            return
        
        duration_seconds = int(processing_time_ms / 1000) or 1
        category = request_data.get("category", "makeup")
        product_name = request_data.get("product_name", "Virtual Try-On")
        
        if endpoint.startswith("/api/vto/live_makeup_page/"):
            endpoint_category = endpoint.replace("/api/vto/live_makeup_page/", "")
            color = request_data.get("color", "Unknown")
            product_name = f"Live {endpoint_category.capitalize()} - {color}"
        
        elif endpoint.startswith("/api/vto/apply_"):
            endpoint_category = endpoint.replace("/api/vto/apply_", "")
            product_name = f"{request_data.get('product_name', endpoint_category.capitalize())} {request_data.get('color', 'Unknown')}"
        elif endpoint == "/api/vto/upload":
            product_name = "Image Upload"
        elif endpoint == "/api/vto/live_makeup":
            product_name = f"Live Makeup {request_data.get('color', 'Unknown')}"
        elif endpoint == "/api/vto/live_makeup_apply":
            product_name = f"{request_data.get('category', 'Makeup')} - {request_data.get('color', 'Unknown')}"
        elif endpoint == "/api/vto/track_color_update":
            product_name = f"Color Update: {request_data.get('category', 'Makeup')} - {request_data.get('color', 'Unknown')}"
        elif endpoint == "/api/vto/track_makeup_application":
            product_name = f"Makeup Try-On: {request_data.get('category', 'Makeup')} - {request_data.get('color', 'Unknown')}"

        user_agent = request.headers.get("User-Agent", "").lower()
        device_type = (
            "mobile" if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent
            else "desktop"
        )
        country = request.headers.get("X-Geo-Country", None)

        session = TryonSession(
            user_id=user.id,
            organization_id=organization_id,
            image_url=request_data.get("filename"),
            duration_seconds=duration_seconds,
            device_type=device_type,
            country=country,
            product_name=product_name,
            category=category,
            converted=False,
            created_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        logger.debug(f"Logged TryonSession: org_id={organization_id}, user_id={user.id}, product={product_name}")
    except Exception as e:
        logger.error(f"Error logging TryonSession: {str(e)}")
        db.rollback()

def check_access(db: Session, org_id: int, api_limit: int, required_service: str = "vto_makeup", is_super_admin: bool = False, is_guest: bool = False):
    """Verify organization access and API limit (skip for Super Admin and Guest)"""
    if is_super_admin or is_guest:
        return
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not found")
    
    if required_service not in org.services:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Organization not subscribed to {required_service} service")
    
    usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org_id).count()
    if usage_count >= api_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="API rate limit exceeded")

async def process_vto_request(
    client: httpx.AsyncClient,
    endpoint: str,
    files: dict,
    data: dict,
    start_time: datetime
) -> tuple[bytes, int]:
    """Helper to process VTO requests and calculate processing time."""
    try:
        response = await client.post(f"{VTO_SERVICE_URL}/{endpoint}", files=files, data=data)
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return response.content, processing_time_ms
    except Exception as e:
        logger.error(f"Error in VTO /{endpoint}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing VTO request: {str(e)}")

# --- VTO ENDPOINTS WITH GUEST TRACKING ---

@router.get("/live_makeup_page/{category}")
async def vto_live_makeup_page(
    category: str, 
    request: Request, 
    api_key: Optional[str] = Query(None),
    color: Optional[str] = Query(None), 
    db: Session = Depends(get_db), 
    auth_info=Depends(get_api_key)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    
    try:
        start_time = datetime.now()
        
        if is_guest:
            limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
            if limit_reached:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Guest usage limit reached. Please subscribe to continue."
                )
        
        if not is_super and not is_guest:
            subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
            if subscription:
                check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)
        
        data = {"action": "page_view", "category": category, "color": color or "default"}
        html_path = "/home/pranab/OS/OptimoSight/Service_manager_v2Live/service_manager_backend_v2Live/frontend/liveMakeup.html"
        
        if not os.path.exists(html_path):
            raise HTTPException(status_code=404, detail="Live makeup page not found")
        
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        await log_usage(db, f"/api/vto/live_makeup_page/{category}", auth_info.organization_id, getattr(auth_info, 'id', None), 200, data, processing_time_ms, request, is_super, is_guest)
        await log_tryon_session(db, auth_info.organization_id, data, processing_time_ms, f"/api/vto/live_makeup_page/{category}", request, getattr(auth_info, 'id', None), is_super, is_guest)
        
        return FileResponse(html_path)
        
    except Exception as e:
        logger.error(f"Error in live_makeup_page for category {category}: {str(e)}")
        raise

@router.post("/live_makeup_page/update")
async def vto_live_makeup_update(
    request: Request, 
    auth_info=Depends(get_api_key), 
    db: Session=Depends(get_db)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)

    try:
        start_time = datetime.now()
        
        if is_guest:
            limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
            if limit_reached:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Guest usage limit reached. Please subscribe to continue."
                )
        
        if not is_super and not is_guest:
            subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
            if subscription:
                check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

        request_data = await request.json()
        
        required_fields = ["category", "color"]
        if not is_super and not is_guest:
            required_fields.append("org_id")

        if any(field not in request_data or request_data[field] is None for field in required_fields):
            raise HTTPException(status_code=422, detail="Missing required fields")

        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        original_endpoint = f"/api/vto/live_makeup_page/{request_data['category']}"

        await log_usage(db, original_endpoint, auth_info.organization_id, getattr(auth_info, 'id', None), 200, request_data, processing_time_ms, request, is_super, is_guest)
        await log_tryon_session(db, auth_info.organization_id, request_data, processing_time_ms, original_endpoint, request, getattr(auth_info, 'id', None), is_super, is_guest)

        return {"status": "update_logged", "usage_incremented": is_guest}
    except Exception as e:
        logger.error(f"Error in vto_live_makeup_update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def vto_upload(
    request: Request,
    image: UploadFile = File(...),
    org_id: Optional[int] = Form(None),
    category: str = Form(...),
    auth_info = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()

    # Validate category
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {VALID_CATEGORIES}"
        )

    # Guest usage limit check
    if is_guest:
        limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
        if limit_reached:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest usage limit reached. Please subscribe to continue."
            )

    # Subscription access check for non-super, non-guest users
    if not is_super and not is_guest:
        subscription = (
            db.query(Subscription)
            .join(Organization, Organization.subscription_id == Subscription.id)
            .filter(Organization.id == auth_info.organization_id)
            .first()
        )
        if subscription:
            check_access(
                db,
                auth_info.organization_id,
                subscription.api_limit,
                is_super_admin=is_super,
                is_guest=is_guest
            )

    # Log usage
    request_data = {"filename": image.filename, "org_id": org_id, "category": category}
    processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    await log_usage(
        db,
        "/api/vto/upload",
        auth_info.organization_id,
        getattr(auth_info, 'id', None),
        200,
        request_data,
        processing_time_ms,
        request,
        is_super,
        is_guest
    )
    await log_tryon_session(
        db,
        auth_info.organization_id,
        request_data,
        processing_time_ms,
        "/api/vto/upload",
        request,
        getattr(auth_info, 'id', None),
        is_super,
        is_guest
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # Added timeout
            content = await image.read()
            files = {"file": (image.filename, content, image.content_type)}

            try:
                response = await client.post(
                    f"{VTO_SERVICE_URL}/api/v1/makeup/upload_image",
                    files=files,
                    data={"crop_face": "true"},
                )
            except httpx.ConnectError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Virtual try-on service is not reachable. Please try again later."
                )
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Virtual try-on service timeout. Please try again."
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Connection to virtual try-on service failed: {str(e)}"
                )

            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Virtual try-on service error: {response.text}"
                )

            vto_response = response.json()
            
            # Extract the base64 image from the VTO service response
            processed_image = vto_response.get("image") or vto_response.get("processed_image") or vto_response.get("data")
            
            if not processed_image:
                print("VTO Service Response:", vto_response)
                raise HTTPException(
                    status_code=500, 
                    detail="Could not find processed image in virtual try-on service response"
                )
            
            return {
                "processed_image": processed_image,
            }

    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Image processing failed: {str(e)}"
        )


@router.post("/apply_{category}")
async def vto_apply_makeup(
    category: str,
    request: Request, 
    image: UploadFile = File(...), 
    color: str = Form(...), 
    org_id: Optional[int] = Form(None), 
    product_name: str = Form(...), 
    auth_info = Depends(get_api_key), 
    db: Session = Depends(get_db)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()

    # Validate path category (makeup type)
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid makeup type. Must be one of {VALID_CATEGORIES}"
        )

    if is_guest:
        limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
        if limit_reached:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest usage limit reached. Please subscribe to continue."
            )

    if not is_super and not is_guest:
        subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
        if subscription:
            check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

    async with httpx.AsyncClient() as client:
        files = {"image": (image.filename, await image.read(), image.content_type)}
        data = {
            "style_name": category,  # Use path category as style_name for VTO backend
            "product_name": product_name,
            "shade_color": color
        }
        response = await client.post(f"{VTO_SERVICE_URL}/api/v1/makeup/try", files=files, data=data)
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        json_resp = response.json()
        image_base64 = json_resp.get("image_base64")
        if not image_base64:
            raise HTTPException(status_code=500, detail="No image returned from service")

        if image_base64.startswith("data:image"):
            image_base64 = image_base64.split(",")[1]
        content = base64.b64decode(image_base64)
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        request_data = {"filename": image.filename, "color": color, "org_id": org_id, "category": category, "product_name": product_name}
        endpoint = f"/api/vto/apply_{category}"
        await log_usage(db, endpoint, auth_info.organization_id, getattr(auth_info, 'id', None), 200, request_data, processing_time_ms, request, is_super, is_guest)
        await log_tryon_session(db, auth_info.organization_id, request_data, processing_time_ms, endpoint, request, getattr(auth_info, 'id', None), is_super, is_guest)

        return StreamingResponse(BytesIO(content), media_type="image/jpeg")

@router.post("/live_makeup")
async def vto_live_makeup(request: Request, auth_info = Depends(get_api_key), db: Session = Depends(get_db)):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()

    if is_guest:
        limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
        if limit_reached:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest usage limit reached. Please subscribe to continue."
            )

    if not is_super and not is_guest:
        subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
        if subscription:
            check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

    async with httpx.AsyncClient() as client:
        try:
            data = await request.json()
            required_fields = ["frame", "color", "category"]
            if not is_super and not is_guest:
                required_fields.append("org_id")
            
            if not all(key in data for key in required_fields):
                raise HTTPException(status_code=400, detail="Missing required fields")
            
            response = await client.post(f"{VTO_SERVICE_URL}/live_makeup", json=data)
            response.raise_for_status()

            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            await log_usage(db, "/api/vto/live_makeup", auth_info.organization_id, getattr(auth_info, 'id', None), response.status_code, data, processing_time_ms, request, is_super, is_guest)
            await log_tryon_session(db, auth_info.organization_id, data, processing_time_ms, "/api/vto/live_makeup", request, getattr(auth_info, 'id', None), is_super, is_guest)

            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Error in VTO /live_makeup: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing VTO request: {str(e)}")

@router.post("/live_makeup_apply")
async def vto_live_makeup_apply(request: Request, auth_info = Depends(get_api_key), db: Session = Depends(get_db)):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()

    if is_guest:
        limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
        if limit_reached:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest usage limit reached. Please subscribe to continue."
            )

    if not is_super and not is_guest:
        subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
        if subscription:
            check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

    async with httpx.AsyncClient() as client:
        try:
            data = await request.json()
            required_fields = ["category", "color"]
            if not is_super and not is_guest:
                required_fields.append("org_id")
            
            if not all(key in data for key in required_fields):
                raise HTTPException(status_code=400, detail="Missing required fields")
            
            response = await client.post(f"{VTO_SERVICE_URL}/live_makeup_apply", json=data)
            response.raise_for_status()

            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            await log_usage(db, "/api/vto/live_makeup_apply", auth_info.organization_id, getattr(auth_info, 'id', None), response.status_code, data, processing_time_ms, request, is_super, is_guest)
            await log_tryon_session(db, auth_info.organization_id, data, processing_time_ms, "/api/vto/live_makeup_apply", request, getattr(auth_info, 'id', None), is_super, is_guest)

            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Error in VTO /live_makeup_apply: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing VTO request: {str(e)}")

@router.post("/track_color_update")
async def vto_track_color_update(
    request: Request,
    color_update: ColorUpdateRequest,
    auth_info = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()
    
    try:
        if is_guest:
            limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
            if limit_reached:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Guest usage limit reached. Please subscribe to continue."
                )

        if not is_super and not is_guest:
            subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
            if subscription:
                check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

        request_data = color_update.dict()
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        await log_usage(db, "/api/vto/track_color_update", auth_info.organization_id, getattr(auth_info, 'id', None), 200, request_data, processing_time_ms, request, is_super, is_guest)
        await log_tryon_session(db, auth_info.organization_id, request_data, processing_time_ms, "/api/vto/track_color_update", request, getattr(auth_info, 'id', None), is_super, is_guest)

        return {
            "status": "color_update_tracked",
            "category": color_update.category,
            "color": color_update.color,
            "usage_incremented": is_guest
        }
    except Exception as e:
        logger.error(f"Error in track_color_update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/track_makeup_application")
async def vto_track_makeup_application(
    request: Request,
    makeup_app: MakeupApplicationRequest,
    auth_info = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    is_super = getattr(auth_info, 'is_super_admin', False)
    is_guest = getattr(auth_info, 'is_guest', False)
    start_time = datetime.now()
    
    try:
        if is_guest:
            limit_reached = await increment_guest_usage_if_needed(auth_info, db, request)
            if limit_reached:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Guest usage limit reached. Please subscribe to continue."
                )

        if not is_super and not is_guest:
            subscription = db.query(Subscription).join(Organization, Organization.subscription_id == Subscription.id).filter(Organization.id == auth_info.organization_id).first()
            if subscription:
                check_access(db, auth_info.organization_id, subscription.api_limit, is_super_admin=is_super, is_guest=is_guest)

        request_data = makeup_app.dict()
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        await log_usage(db, "/api/vto/track_makeup_application", auth_info.organization_id, getattr(auth_info, 'id', None), 200, request_data, processing_time_ms, request, is_super, is_guest)
        await log_tryon_session(db, auth_info.organization_id, request_data, processing_time_ms, "/api/vto/track_makeup_application", request, getattr(auth_info, 'id', None), is_super, is_guest)

        return {
            "status": "makeup_application_tracked",
            "category": makeup_app.category,
            "color": makeup_app.color,
            "usage_incremented": is_guest
        }
    except Exception as e:
        logger.error(f"Error in track_makeup_application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/guest-usage-status")
async def get_guest_usage_status(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    if x_api_key != GUEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Guest API key required")
    
    try:
        guest_usage = await get_or_create_guest_usage(request, db)
        
        if guest_usage.last_visit < datetime.utcnow() - timedelta(hours=RESET_PERIOD_HOURS):
            guest_usage.usage_count = 0
            guest_usage.last_visit = datetime.utcnow()
            db.commit()
        
        return {
            "usage_count": guest_usage.usage_count,
            "limit": GUEST_LIMIT,
            "remaining": max(0, GUEST_LIMIT - guest_usage.usage_count),
            "limit_reached": guest_usage.usage_count >= GUEST_LIMIT,
            "reset_time": (guest_usage.last_visit + timedelta(hours=RESET_PERIOD_HOURS)).isoformat(),
            "fingerprint": guest_usage.fingerprint_hash[:8] + "...",
            "ip_address": guest_usage.ip_address
        }
    except Exception as e:
        logger.error(f"Error getting guest usage status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get guest usage status: {str(e)}"
        )

@router.post("/reset-guest-usage")
async def reset_guest_usage(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    if x_api_key != SUPER_ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Super admin access required")
    
    try:
        guest_usage = await get_or_create_guest_usage(request, db)
        guest_usage.usage_count = 0
        guest_usage.last_visit = datetime.utcnow()
        db.commit()
        
        return {
            "status": "reset_successful",
            "usage_count": 0,
            "limit": GUEST_LIMIT,
            "fingerprint": guest_usage.fingerprint_hash[:8] + "..."
        }
    except Exception as e:
        logger.error(f"Error resetting guest usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset guest usage: {str(e)}"
        )