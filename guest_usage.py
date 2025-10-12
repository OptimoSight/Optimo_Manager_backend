from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request, Header, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import httpx
import logging
from datetime import datetime, timedelta
from io import BytesIO
from models import ApiKey, Organization, UsageLog, Subscription, User, TryonSession, Role, RoleName, GuestUsage
import json
import base64
import os
from constants import VTO_ENDPOINTS, SUPER_ADMIN_API_KEY, GUEST_API_KEY
import hashlib
from database import get_db, Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Database model for guest usage tracking
class GuestUsage(Base):
    __tablename__ = "guest_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    fingerprint_hash = Column(String(64), index=True)
    ip_address = Column(String(45), index=True)  # IPv6 support
    user_agent_hash = Column(String(64))
    usage_count = Column(Integer, default=0)
    first_visit = Column(DateTime, default=datetime.utcnow)
    last_visit = Column(DateTime, default=datetime.utcnow)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Router for guest usage endpoints
guest_router = APIRouter(tags=["Guest Usage"])

# Configuration
GUEST_LIMIT = 200
RESET_PERIOD_HOURS = 24

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

async def get_or_create_guest_usage(
    request: Request, 
    db: Session = Depends(get_db)
) -> GuestUsage:
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

@guest_router.get("/usage")
async def get_guest_usage(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    """Get current guest usage count"""
    logger.info(f"Guest usage request received from IP: {request.client.host}")
    if x_api_key != GUEST_API_KEY:
        logger.warning(f"Invalid API key: {x_api_key}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Guest API key required")
    try:
        guest_usage = await get_or_create_guest_usage(request, db)
        
        if guest_usage.last_visit < datetime.utcnow() - timedelta(hours=RESET_PERIOD_HOURS):
            guest_usage.usage_count = 0
            guest_usage.last_visit = datetime.utcnow()
            db.commit()
            logger.info(f"Guest usage reset for IP: {guest_usage.ip_address}")
        
        return {
            "usage_count": guest_usage.usage_count,
            "limit": GUEST_LIMIT,
            "remaining": max(0, GUEST_LIMIT - guest_usage.usage_count),
            "limit_reached": guest_usage.usage_count >= GUEST_LIMIT,
            "reset_time": (guest_usage.last_visit + timedelta(hours=RESET_PERIOD_HOURS)).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting guest usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get guest usage: {str(e)}"
        )

@guest_router.post("/increment")
async def increment_guest_usage(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    """Increment guest usage count"""
    logger.info(f"Guest increment request received from IP: {request.client.host}")
    if x_api_key != GUEST_API_KEY:
        logger.warning(f"Invalid API key: {x_api_key}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Guest API key required")
    try:
        guest_usage = await get_or_create_guest_usage(request, db)
        
        if guest_usage.usage_count >= GUEST_LIMIT:
            logger.warning(f"Guest usage limit exceeded for IP: {guest_usage.ip_address}")
            return {
                "success": False,
                "limit_reached": True,
                "usage_count": guest_usage.usage_count,
                "limit": GUEST_LIMIT,
                "message": "Guest usage limit reached"
            }
        
        guest_usage.usage_count += 1
        guest_usage.last_visit = datetime.utcnow()
        db.commit()
        
        logger.info(f"Guest usage incremented to {guest_usage.usage_count}/{GUEST_LIMIT} for IP: {guest_usage.ip_address}")
        
        return {
            "success": True,
            "usage_count": guest_usage.usage_count,
            "limit": GUEST_LIMIT,
            "remaining": max(0, GUEST_LIMIT - guest_usage.usage_count),
            "limit_reached": guest_usage.usage_count >= GUEST_LIMIT
        }
    except Exception as e:
        logger.error(f"Error incrementing guest usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to increment guest usage: {str(e)}"
        )

@guest_router.post("/reset")
async def reset_guest_usage(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None)
):
    """Reset guest usage (admin only or after time period)"""
    logger.info(f"Guest reset request received from IP: {request.client.host}")
    if x_api_key != SUPER_ADMIN_API_KEY:
        logger.warning(f"Invalid API key for reset: {x_api_key}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Super admin access required")
    try:
        guest_usage = await get_or_create_guest_usage(request, db)
        guest_usage.usage_count = 0
        guest_usage.last_visit = datetime.utcnow()
        db.commit()
        
        logger.info(f"Guest usage reset for IP: {guest_usage.ip_address}")
        
        return {
            "success": True,
            "usage_count": 0,
            "limit": GUEST_LIMIT,
            "message": "Guest usage reset successfully"
        }
    except Exception as e:
        logger.error(f"Error resetting guest usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset guest usage: {str(e)}"
        )

async def track_guest_usage_middleware(
    request: Request,
    db: Session = Depends(get_db)
):
    """Middleware to track guest usage for VTO endpoints"""
    api_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
    
    if api_key == GUEST_API_KEY:
        guest_usage = await get_or_create_guest_usage(request, db)
        
        if guest_usage.usage_count >= GUEST_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Guest usage limit reached. Please subscribe to continue."
            )
        
        guest_usage.usage_count += 1
        guest_usage.last_visit = datetime.utcnow()
        db.commit()
    
    return guest_usage if api_key == GUEST_API_KEY else None