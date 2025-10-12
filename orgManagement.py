from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from sqlalchemy.sql.sqltypes import Integer
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid
import logging
from database import get_db
from models import Organization, User, Subscription, UsageLog, Role, ApiKey, Profile
from auth import get_password_hash, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Constants
VTO_ENDPOINTS = [
    '/api/vto/upload',
    '/api/vto/apply_eyeshadow',
    '/api/vto/apply_lipstick',
    '/api/vto/live_makeup',
    '/api/vto/apply_foundation',
    '/api/vto/apply_eyebrow'
]

class OrganizationCreate(BaseModel):
    name: str
    contact_email: str
    domain: str
    subscription_id: int
    services: List[str] = ["vto_makeup"]
    contact_person: str | None = None
    address: str | None = None
    phone: str | None = None

class OrganizationUpdate(BaseModel):
    name: str
    contact_email: str
    domain: str
    subscription_id: int
    services: List[str] = ["vto_makeup"]
    contact_person: str | None = None
    address: str | None = None
    phone: str | None = None

class OrganizationResponse(BaseModel):
    id: int
    name: str
    domain: str
    contact_email: str
    subscription_id: int
    api_usage: int
    api_due: int
    status: str
    services: List[str]
    subscription_plan: str
    api_key: str
    created_at: datetime
    updated_at: datetime
    admin_username: str
    admin_password: str | None = None
    contact_person: str | None
    address: str | None
    phone: str | None
    monthlyUsage: List[dict]

    class Config:
        from_attributes = True

@router.post("/organizations/", response_model=OrganizationResponse)
async def create_organization(org: OrganizationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if not role or role.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only SuperAdmins can create organizations")

    if db.query(User).filter(User.email == org.contact_email).first():
        raise HTTPException(status_code=400, detail="An admin user with this email already exists")

    subscription = db.query(Subscription).filter(Subscription.id == org.subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=400, detail="Invalid subscription_id")

    db_org = Organization(
        name=org.name,
        contact_email=org.contact_email,
        domain=org.domain,
        subscription_id=org.subscription_id,
        services=org.services,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_org)
    db.commit()
    db.refresh(db_org)

    # Create Profile
    db_profile = Profile(
        organization_id=db_org.id,
        contact_person=org.contact_person,
        address=org.address,
        phone=org.phone,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_profile)
    db.commit()

    api_key = ApiKey(organization_id=db_org.id, api_key=str(uuid.uuid4()), is_active=True, created_at=datetime.utcnow())
    db.add(api_key)
    db.commit()

    admin_password = "admin123"  # Change in production
    hashed_password = get_password_hash(admin_password)
    admin_role = db.query(Role).filter(Role.role == "admin").first()
    if not admin_role:
        raise HTTPException(status_code=500, detail="Admin role not found")

    admin_user = User(
        uid=str(uuid.uuid4()),
        org_id=db_org.id,
        name=f"Admin for {org.name}",
        email=org.contact_email,
        password_hash=hashed_password,
        role_id=admin_role.id,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    usage_count = db.query(UsageLog).filter(UsageLog.organization_id == db_org.id).count()
    api_due = subscription.api_limit
    status = "Warning" if usage_count > 0.9 * api_due else "Active"

    logger.info(f"Created org {db_org.id}: Email={org.contact_email}, Password={admin_password}")
    return {
        "id": db_org.id,
        "name": db_org.name,
        "domain": db_org.domain,
        "contact_email": org.contact_email,
        "subscription_id": db_org.subscription_id,
        "api_usage": usage_count,
        "api_due": api_due,
        "status": status,
        "services": db_org.services,
        "subscription_plan": subscription.plan_name,
        "api_key": api_key.api_key,
        "created_at": db_org.created_at,
        "updated_at": db_org.updated_at,
        "admin_username": org.contact_email,
        "admin_password": admin_password,
        "contact_person": org.contact_person,
        "address": org.address,
        "phone": org.phone,
        "monthlyUsage": [{"month": datetime.utcnow().strftime('%b'), "apiUsage": 0, "revenue": subscription.price or 0}]
    }

@router.get("/organizations/", response_model=List[OrganizationResponse])
async def get_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.role not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    orgs = db.query(Organization).filter(Organization.id == user.org_id).all() if role.role == "admin" else db.query(Organization).all()
    result = []
    for org in orgs:
        subscription = db.query(Subscription).filter(Subscription.id == org.subscription_id).first()
        api_key = db.query(ApiKey).filter(ApiKey.organization_id == org.id, ApiKey.is_active == True).first()
        profile = db.query(Profile).filter(Profile.organization_id == org.id).first()
        if not profile:
            profile = Profile(
                organization_id=org.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(profile)
            db.commit()
        api_due = subscription.api_limit if subscription else 100000
        usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org.id).count()
        status = "Warning" if usage_count > 0.9 * api_due else "Active"

        # Calculate monthly usage
        monthly_usage_query = (
            db.query(
                func.cast(extract('month', UsageLog.timestamp), Integer).label('month_num'),
                func.count(UsageLog.id.distinct()).label('apiUsage')
            )
            .filter(UsageLog.organization_id == org.id, UsageLog.endpoint.in_(VTO_ENDPOINTS))
            .group_by(func.cast(extract('month', UsageLog.timestamp), Integer))
            .order_by(func.cast(extract('month', UsageLog.timestamp), Integer))
            .all()
        )
        logger.info(f"Monthly usage query for org {org.id}: {monthly_usage_query}")

        month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                       7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
        monthly_usage = [
            {"month": month_names.get(row.month_num, 'Unknown'), "apiUsage": row.apiUsage}
            for row in monthly_usage_query
        ]
        revenue = subscription.price if subscription and subscription.price else 0
        monthly_usage_with_revenue = [
            {"month": m["month"], "apiUsage": m["apiUsage"], "revenue": revenue}
            for m in monthly_usage
        ]
        if not monthly_usage_with_revenue and subscription:
            monthly_usage_with_revenue = [{"month": datetime.utcnow().strftime('%b'), "apiUsage": 0, "revenue": revenue}]
        logger.info(f"Monthly usage with revenue for org {org.id}: {monthly_usage_with_revenue}")

        result.append({
            "id": org.id,
            "name": org.name,
            "domain": org.domain,
            "contact_email": org.contact_email,
            "subscription_id": org.subscription_id,
            "api_usage": usage_count,
            "api_due": api_due,
            "status": status,
            "services": org.services,
            "subscription_plan": subscription.plan_name if subscription else "N/A",
            "api_key": api_key.api_key if api_key else "N/A",
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "admin_username": org.contact_email,
            "contact_person": profile.contact_person,
            "address": profile.address,
            "phone": profile.phone,
            "monthlyUsage": monthly_usage_with_revenue
        })
    logger.info(f"Fetched {len(result)} organizations for user {user.email}")
    return result

@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if role.role != "super_admin" and user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    subscription = db.query(Subscription).filter(Subscription.id == org.subscription_id).first()
    api_key = db.query(ApiKey).filter(ApiKey.organization_id == org.id, ApiKey.is_active == True).first()
    profile = db.query(Profile).filter(Profile.organization_id == org.id).first()
    if not profile:
        profile = Profile(
            organization_id=org.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(profile)
        db.commit()

    # Calculate API usage and due
    api_due = subscription.api_limit if subscription else 100000
    usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org.id).count()
    status = "Warning" if usage_count > 0.9 * api_due else "Active"

    # Calculate monthly usage
    monthly_usage_query = (
        db.query(
            func.cast(extract('month', UsageLog.timestamp), Integer).label('month_num'),
            func.count(UsageLog.id.distinct()).label('apiUsage')
        )
        .filter(UsageLog.organization_id == org.id, UsageLog.endpoint.in_(VTO_ENDPOINTS))
        .group_by(func.cast(extract('month', UsageLog.timestamp), Integer))
        .order_by(func.cast(extract('month', UsageLog.timestamp), Integer))
        .all()
    )
    logger.info(f"Monthly usage query for org {org_id}: {monthly_usage_query}")

    month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                   7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    monthly_usage = [
        {"month": month_names.get(row.month_num, 'Unknown'), "apiUsage": row.apiUsage}
        for row in monthly_usage_query
    ]
    revenue = subscription.price if subscription and subscription.price else 0
    monthly_usage_with_revenue = [
        {"month": m["month"], "apiUsage": m["apiUsage"], "revenue": revenue}
        for m in monthly_usage
    ]
    if not monthly_usage_with_revenue and subscription:
        monthly_usage_with_revenue = [{"month": datetime.utcnow().strftime('%b'), "apiUsage": 0, "revenue": revenue}]
    logger.info(f"Monthly usage with revenue for org {org_id}: {monthly_usage_with_revenue}")

    result = {
        "id": org.id,
        "name": org.name,
        "domain": org.domain,
        "contact_email": org.contact_email,
        "subscription_id": org.subscription_id,
        "api_usage": usage_count,
        "api_due": api_due,
        "status": status,
        "services": org.services,
        "subscription_plan": subscription.plan_name if subscription else "N/A",
        "api_key": api_key.api_key if api_key else "N/A",
        "created_at": org.created_at,
        "updated_at": org.updated_at,
        "admin_username": org.contact_email,
        "contact_person": profile.contact_person,
        "address": profile.address,
        "phone": profile.phone,
        "monthlyUsage": monthly_usage_with_revenue
    }
    logger.info(f"Fetched org {org_id} for user {user.email}: {result}")
    return result

@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(org_id: int, org_update: OrganizationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only SuperAdmins can edit organizations")

    db_org = db.query(Organization).filter(Organization.id == org_id).first()
    if not db_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    subscription = db.query(Subscription).filter(Subscription.id == org_update.subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=400, detail="Invalid subscription_id")

    db_org.name = org_update.name
    db_org.contact_email = org_update.contact_email
    db_org.domain = org_update.domain
    db_org.subscription_id = org_update.subscription_id
    db_org.services = org_update.services
    db_org.updated_at = datetime.utcnow()

    db_profile = db.query(Profile).filter(Profile.organization_id == org_id).first()
    if not db_profile:
        db_profile = Profile(
            organization_id=org_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(db_profile)
    db_profile.contact_person = org_update.contact_person
    db_profile.address = org_update.address
    db_profile.phone = org_update.phone
    db_profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_org)
    db.refresh(db_profile)

    api_key = db.query(ApiKey).filter(ApiKey.organization_id == org_id, ApiKey.is_active == True).first()
    usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org_id).count()
    api_due = subscription.api_limit
    status = "Warning" if usage_count > 0.9 * api_due else "Active"

    # Calculate monthly usage
    monthly_usage_query = (
        db.query(
            func.cast(extract('month', UsageLog.timestamp), Integer).label('month_num'),
            func.count(UsageLog.id.distinct()).label('apiUsage')
        )
        .filter(UsageLog.organization_id == org_id, UsageLog.endpoint.in_(VTO_ENDPOINTS))
        .group_by(func.cast(extract('month', UsageLog.timestamp), Integer))
        .order_by(func.cast(extract('month', UsageLog.timestamp), Integer))
        .all()
    )
    logger.info(f"Monthly usage query for org {org_id}: {monthly_usage_query}")

    month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                   7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    monthly_usage = [
        {"month": month_names.get(row.month_num, 'Unknown'), "apiUsage": row.apiUsage}
        for row in monthly_usage_query
    ]
    revenue = subscription.price if subscription and subscription.price else 0
    monthly_usage_with_revenue = [
        {"month": m["month"], "apiUsage": m["apiUsage"], "revenue": revenue}
        for m in monthly_usage
    ]
    if not monthly_usage_with_revenue and subscription:
        monthly_usage_with_revenue = [{"month": datetime.utcnow().strftime('%b'), "apiUsage": 0, "revenue": revenue}]
    logger.info(f"Monthly usage with revenue for org {org_id}: {monthly_usage_with_revenue}")

    result = {
        "id": db_org.id,
        "name": db_org.name,
        "domain": db_org.domain,
        "contact_email": db_org.contact_email,
        "subscription_id": db_org.subscription_id,
        "api_usage": usage_count,
        "api_due": api_due,
        "status": status,
        "services": db_org.services,
        "subscription_plan": subscription.plan_name,
        "api_key": api_key.api_key if api_key else "N/A",
        "created_at": db_org.created_at,
        "updated_at": db_org.updated_at,
        "admin_username": db_org.contact_email,
        "contact_person": db_profile.contact_person,
        "address": db_profile.address,
        "phone": db_profile.phone,
        "monthlyUsage": monthly_usage_with_revenue
    }
    logger.info(f"Updated org {org_id} for user {user.email}: {result}")
    return result

@router.delete("/organizations/{org_id}", status_code=204)
async def delete_organization(
    org_id: int,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Deleting org {org_id} by user {user.email}, force={force}")
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if role.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only SuperAdmins can delete organizations")

        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            logger.warning(f"Organization {org_id} not found")
            raise HTTPException(status_code=404, detail="Organization not found")

        user_count = db.query(User).filter(User.org_id == org_id).count()
        usage_count = db.query(UsageLog).filter(UsageLog.organization_id == org_id).count()
        api_key_count = db.query(ApiKey).filter(ApiKey.organization_id == org_id).count()
        profile_count = db.query(Profile).filter(Profile.organization_id == org_id).count()

        if user_count > 0 or usage_count > 0 or api_key_count > 0 or profile_count > 0:
            if not force:
                logger.warning(f"Cannot delete org {org_id}: {user_count} users, {usage_count} usage logs, {api_key_count} API keys, {profile_count} profiles")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete organization with associated records: {user_count} users, {usage_count} usage logs, {api_key_count} API keys, {profile_count} profiles"
                )
            else:
                db.query(User).filter(User.org_id == org_id).delete()
                db.query(UsageLog).filter(UsageLog.organization_id == org_id).delete()
                db.query(ApiKey).filter(ApiKey.organization_id == org_id).delete()
                db.query(Profile).filter(Profile.organization_id == org_id).delete()
                db.commit()
                logger.info(f"Deleted {user_count} users, {usage_count} usage logs, {api_key_count} API keys, {profile_count} profiles for org {org_id}")

        db.delete(org)
        db.commit()
        logger.info(f"Organization {org_id} deleted successfully")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting org {org_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete organization: {str(e)}")