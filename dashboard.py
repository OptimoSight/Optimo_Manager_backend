from sqlalchemy import func, extract
from sqlalchemy.sql import case
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Integer  # Add this import
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from database import get_db
from models import Organization, Subscription, UsageLog, Role, User, TryonSession
from auth import get_current_user
from constants import VTO_ENDPOINTS
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
# VTO_ENDPOINTS = ['/api/vto/upload', '/api/vto/apply_eyeshadow', '/api/vto/apply_lipstick', '/api/vto/live_makeup']

@router.get("/dashboard")
async def get_dashboard(
    org_id: int = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.debug(f"Starting get_dashboard for user: {user.email}, org_id: {org_id}")
    try:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role:
            logger.error(f"Role not found for role_id: {user.role_id}")
            raise HTTPException(status_code=500, detail="User role not found")
        role_name = role.role.lower()
        logger.info(f"User role: {role_name}")

        if role_name == "super_admin" and org_id:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if not org:
                logger.warning(f"Organization not found for org_id: {org_id}")
                raise HTTPException(status_code=404, detail="Organization not found")
            plan = db.query(Subscription).filter(Subscription.id == org.subscription_id).first()
            api_limit = plan.api_limit if plan else 100000
            usage_count = db.query(func.count(UsageLog.id)).filter(
            UsageLog.organization_id == org.id,
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
            ).scalar() or 0
            api_usage = usage_count
            api_due = api_limit
            alert = "API usage nearing limit" if usage_count > 0.9 * api_limit else None

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
            month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                           7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
            monthly_usage = [
                {"month": month_names.get(row.month_num, 'Unknown'), "apiUsage": row.apiUsage}
                for row in monthly_usage_query
            ] if monthly_usage_query else []

            revenue = plan.price if plan else 0
            monthly_revenue = [
                {"month": m["month"], "revenue": revenue} for m in monthly_usage
            ] if monthly_usage else []
            if not monthly_revenue and revenue > 0:
                monthly_revenue = [{"month": datetime.utcnow().strftime('%b'), "revenue": revenue}]

            total_success = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.organization_id == org.id,
                UsageLog.endpoint.in_(VTO_ENDPOINTS),
                UsageLog.response_status == 200
            ).scalar()
            conversion_rate = (total_success / api_usage * 100) if api_usage > 0 else 0

            return {
                "serviceName": "Virtual Try-on Makeup API",
                "subscriptionPlan": plan.plan_name if plan else "None",
                "apiUsage": api_usage,
                "apiDue": api_due,
                "alert": alert,
                "revenue": revenue,
                "monthlyUsage": monthly_usage,
                "monthlyRevenue": monthly_revenue,
                "conversionRate": round(conversion_rate, 1)
            }

        elif role_name == "super_admin":
            total_orgs = db.query(Organization).count() or 0
            api_usage = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.endpoint.in_(VTO_ENDPOINTS)
            ).scalar() or 0

            revenue_query = db.query(
                func.sum(
                    func.coalesce(
                        case(
                            (Subscription.billing_period == 'yearly', Subscription.price / 12),
                            else_=Subscription.price
                        ),
                        0
                    )
                )
            ).select_from(Subscription).join(
                Organization,
                Organization.subscription_id == Subscription.id,
                isouter=True
            ).scalar()
            revenue = revenue_query or 0

            total_success = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.endpoint.in_(VTO_ENDPOINTS),
                UsageLog.response_status == 200
            ).scalar()
            conversion_rate = (total_success / api_usage * 100) if api_usage > 0 else 0

            return {
                "serviceName": "Virtual Try-on Makeup API",
                "totalOrganizations": total_orgs,
                "apiUsage": api_usage,
                "revenue": round(revenue, 2),
                "conversionRate": round(conversion_rate, 1)
            }

        elif role_name == "admin":
            org = db.query(Organization).filter(Organization.id == user.org_id).first()
            if not org:
                logger.warning(f"No organization found for org_id: {user.org_id}")
                return {
                    "serviceName": "Virtual Try-on Makeup API",
                    "subscriptionPlan": "None",
                    "apiUsage": 0,
                    "apiDue": 0,
                    "revenue": 0,
                    "monthlyUsage": [],
                    "monthlyRevenue": [],
                    "conversionRate": 0
                }
            plan = db.query(Subscription).filter(Subscription.id == org.subscription_id).first()
            api_usage = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.organization_id == user.org_id,
                UsageLog.endpoint.in_(VTO_ENDPOINTS)
            ).scalar() or 0
            api_limit = plan.api_limit if plan else 100000
            api_due = max(0, api_limit - api_usage)
            alert = "Low API limit!" if api_usage >= api_limit * 0.9 else None

            monthly_usage_query = (
                db.query(
                    func.cast(extract('month', UsageLog.timestamp), Integer).label('month_num'),
                    func.count(UsageLog.id.distinct()).label('apiUsage')
                )
                .filter(UsageLog.organization_id == user.org_id, UsageLog.endpoint.in_(VTO_ENDPOINTS))
                .group_by(func.cast(extract('month', UsageLog.timestamp), Integer))
                .order_by(func.cast(extract('month', UsageLog.timestamp), Integer))
                .all()
            )
            month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                           7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
            monthly_usage = [
                {"month": month_names.get(row.month_num, 'Unknown'), "apiUsage": row.apiUsage}
                for row in monthly_usage_query
            ] if monthly_usage_query else []

            revenue = plan.price if plan else 0
            monthly_revenue = [
                {"month": m["month"], "revenue": revenue} for m in monthly_usage
            ] if monthly_usage else []
            if not monthly_revenue and revenue > 0:
                monthly_revenue = [{"month": datetime.utcnow().strftime('%b'), "revenue": revenue}]

            total_success = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.organization_id == user.org_id,
                UsageLog.endpoint.in_(VTO_ENDPOINTS),
                UsageLog.response_status == 200
            ).scalar()
            conversion_rate = (total_success / api_usage * 100) if api_usage > 0 else 0

            return {
                "serviceName": "Virtual Try-on Makeup API",
                "subscriptionPlan": plan.plan_name if plan else "None",
                "apiUsage": api_usage,
                "apiDue": api_due,
                "alert": alert,
                "revenue": revenue,
                "monthlyUsage": monthly_usage,
                "monthlyRevenue": monthly_revenue,
                "conversionRate": round(conversion_rate, 1)
            }

        else:  # Guest
            api_usage = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.user_id == user.id,
                UsageLog.endpoint.in_(VTO_ENDPOINTS)
            ).scalar() or 0
            api_due = max(0, 100000 - api_usage)
            total_success = db.query(func.count(UsageLog.id.distinct())).filter(
                UsageLog.user_id == user.id,
                UsageLog.endpoint.in_(VTO_ENDPOINTS),
                UsageLog.response_status == 200
            ).scalar()
            conversion_rate = (total_success / api_usage * 100) if api_usage > 0 else 0

            return {
                "serviceName": "Virtual Try-on Makeup API (Guest)",
                "apiUsage": api_usage,
                "apiDue": api_due,
                "conversionRate": round(conversion_rate, 1)
            }

    except Exception as e:
        logger.error(f"Error in get_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/debug-usage-logs")
async def debug_usage_logs(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to return raw usage_logs counts for verification."""
    try:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if not role or role.role.lower() != "super_admin":
            raise HTTPException(status_code=403, detail="Only SuperAdmin can access this endpoint")

        total_logs = db.query(func.count(UsageLog.id)).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        ).scalar() or 0

        distinct_logs = db.query(func.count(UsageLog.id.distinct())).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        ).scalar() or 0

        logs_by_endpoint = db.query(
            UsageLog.endpoint,
            func.count(UsageLog.id).label('count')
        ).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        ).group_by(UsageLog.endpoint).all()

        recent_logs = db.query(UsageLog).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        ).order_by(UsageLog.timestamp.desc()).limit(10).all()

        return {
            "total_logs": total_logs,
            "distinct_logs": distinct_logs,
            "logs_by_endpoint": [{"endpoint": e, "count": c} for e, c in logs_by_endpoint],
            "recent_logs": [
                {
                    "id": log.id,
                    "organization_id": log.organization_id,
                    "endpoint": log.endpoint,
                    "timestamp": log.timestamp.isoformat(),
                    "response_status": log.response_status
                } for log in recent_logs
            ]
        }
    except Exception as e:
        logger.error(f"Error in debug_usage_logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")