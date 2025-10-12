# subscription.py - MODIFIED to allow public access
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import Subscription, Organization, User, Role
from auth import get_current_user
import logging

router = APIRouter(tags=["Subscriptions"])
logger = logging.getLogger(__name__)

class SubscriptionCreate(BaseModel):
    plan_name: str
    api_limit: int
    price: float
    billing_period: str
    features: Optional[dict] = None

class SubscriptionResponse(BaseModel):
    id: int
    plan_name: str
    api_limit: int
    price: float
    billing_period: str
    features: Optional[dict] = None
    created_at: datetime

    class Config:
        orm_mode = True

@router.post("/subscriptions/", response_model=SubscriptionResponse)
async def create_subscription(
    plan: SubscriptionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role:
            logger.error(f"Role not found for user {user.email} with role_id {user.role_id}")
            raise HTTPException(status_code=500, detail="User role not found")
        if role.role != "super_admin":
            logger.warning(f"Unauthorized attempt by {user.email} with role {role.role}")
            raise HTTPException(status_code=403, detail="Only SuperAdmins can create subscriptions")

        db_plan = Subscription(**plan.dict(), created_at=datetime.utcnow())
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        logger.info(f"Subscription created: {db_plan.plan_name}")
        return db_plan
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# MODIFIED: Allow public access to view subscriptions
@router.get("/subscriptions/", response_model=List[SubscriptionResponse])
async def get_subscriptions(
    db: Session = Depends(get_db)
):
    """
    Get all available subscription plans (public endpoint)
    """
    try:
        logger.info("Fetching subscriptions (public access)")
        subscriptions = db.query(Subscription).all()
        logger.info(f"Returning {len(subscriptions)} subscriptions")
        return subscriptions
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# NEW: Public endpoint for guest users to view plans
@router.get("/subscriptions/public", response_model=List[SubscriptionResponse])
async def get_public_subscriptions(
    db: Session = Depends(get_db)
):
    """
    Public endpoint for viewing subscription plans (no auth required)
    """
    try:
        logger.info("Fetching public subscriptions")
        subscriptions = db.query(Subscription).all()
        logger.info(f"Returning {len(subscriptions)} public subscriptions")
        return subscriptions
    except Exception as e:
        logger.error(f"Error fetching public subscriptions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.post("/organizations/{org_id}/subscribe/{plan_id}")
async def subscribe_organization(
    org_id: int,
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role:
            logger.error(f"Role not found for user {user.email} with role_id {user.role_id}")
            raise HTTPException(status_code=500, detail="User role not found")
        if role.role not in ["super_admin", "admin"]:
            logger.warning(f"Unauthorized attempt by {user.email} with role {role.role}")
            raise HTTPException(status_code=403, detail="Not authorized")

        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            logger.warning(f"Organization {org_id} not found")
            raise HTTPException(status_code=404, detail="Organization not found")
        if role.role == "admin" and org.id != user.org_id:
            logger.warning(f"Admin {user.email} attempted to subscribe org {org_id} not owned")
            raise HTTPException(status_code=403, detail="Admins can only subscribe their own organization")

        plan = db.query(Subscription).filter(Subscription.id == plan_id).first()
        if not plan:
            logger.warning(f"Plan {plan_id} not found")
            raise HTTPException(status_code=404, detail="Plan not found")
        
        org.subscription_id = plan_id
        org.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(org)
        logger.info(f"Org {org_id} subscribed to plan {plan_id}")
        return {"message": f"Organization {org_id} subscribed to plan {plan_id}"}
    except Exception as e:
        logger.error(f"Error subscribing org {org_id} to plan {plan_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")