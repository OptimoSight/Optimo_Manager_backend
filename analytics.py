from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer, String
from sqlalchemy.sql import extract
from database import get_db
from models import UsageLog, User, Role, TryonSession
from auth import get_current_user, check_super_admin
from typing import List
from pydantic import BaseModel
from datetime import datetime, date
import logging
import json
from constants import VTO_ENDPOINTS

router = APIRouter(prefix="/api", tags=["Analytics"])
logger = logging.getLogger(__name__)

# Pydantic Models
class MostUsedResponse(BaseModel):
    endpoint: str
    hits: int

    class Config:
        from_attributes = True

class ResponseTimeResponse(BaseModel):
    time: str
    response_time: float

    class Config:
        from_attributes = True

class SuccessRateResponse(BaseModel):
    success_requests: int
    total_requests: int
    success_rate: float

    class Config:
        from_attributes = True

class KeyMetrics(BaseModel):
    total_sessions: int
    unique_users: int
    avg_duration: float
    conversion_rate: float
    status: str | None = None  # Added for context

class DailySession(BaseModel):
    date: str
    total_sessions: int
    unique_users: int
    avg_duration: float
    peak_usage_hour: str | None

class DailySessionResponse(BaseModel):
    data: List[DailySession]
    status: str | None = None  # Added for context

class MostTriedProduct(BaseModel):
    product_name: str
    category: str | None
    try_on_count: int

class MostTriedProductResponse(BaseModel):
    data: List[MostTriedProduct]
    status: str | None = None  # Added for context

class DeviceDistribution(BaseModel):
    device_type: str
    sessions: int
    percentage: float

class DeviceDistributionResponse(BaseModel):
    data: List[DeviceDistribution]
    status: str | None = None  # Added for context

class GeographicDistribution(BaseModel):
    country: str
    sessions: int

class GeographicDistributionResponse(BaseModel):
    data: List[GeographicDistribution]
    status: str | None = None  # Added for context

def check_authorization(user: User, org_id: int, db: Session):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.role != "super_admin" and user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

@router.get("/most-used", response_model=List[MostUsedResponse])
async def get_most_used(
    org_id: int = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching most-used APIs for user {user.email}, org_id={org_id}")
        if org_id:
            check_authorization(user, org_id, db)  # Allows admin for own org or super_admin
        else:
            check_super_admin(user, db)  # Global view requires super_admin
        query = db.query(
            UsageLog.endpoint,
            func.count(UsageLog.id).label("hits")
        ).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        )
        if org_id:
            query = query.filter(UsageLog.organization_id == org_id)
        most_used = query.group_by(
            UsageLog.endpoint
        ).order_by(
            func.count(UsageLog.id).desc()
        ).limit(5).all()

        return [{"endpoint": endpoint, "hits": hits} for endpoint, hits in most_used]
    except HTTPException:
        raise  # Propagate auth errors (e.g., 403) without changing to 500
    except Exception as e:
        logger.error(f"Error in /most-used: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/response-time", response_model=List[ResponseTimeResponse])
async def get_response_time(
    org_id: int = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching response times for user {user.email}, org_id={org_id}")
        if org_id:
            check_authorization(user, org_id, db)  # Allows admin for own org or super_admin
        else:
            check_super_admin(user, db)
        row_count = db.query(func.count(UsageLog.id)).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS),
            UsageLog.processing_time_ms.isnot(None)
        ).scalar()
        logger.info(f"Usage logs count with non-null processing_time_ms: {row_count}")

        if row_count == 0:
            logger.info("No valid usage logs found, returning empty list")
            return []

        time_expr = func.to_char(
            func.date_trunc('hour', UsageLog.timestamp),
            'YYYY-MM-DD HH24:00:00'
        )
        query = db.query(
            time_expr.label("time"),
            func.avg(func.coalesce(UsageLog.processing_time_ms, 0)).label("response_time")
        ).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS),
            UsageLog.processing_time_ms.isnot(None)
        )
        if org_id:
            query = query.filter(UsageLog.organization_id == org_id)
        response_times = query.group_by(
            time_expr
        ).order_by(
            time_expr
        ).limit(24).all()

        logger.info(f"Response times fetched: {len(response_times)} records")
        return [{"time": str(time), "response_time": round(float(response_time), 2)} for time, response_time in response_times]
    except Exception as e:
        logger.error(f"Error in /response-time: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/recent-activities", response_model=List[dict])
async def get_recent_activities(
    org_id: int = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching recent activities for user {user.email}, org_id={org_id}")
        if org_id:
            check_authorization(user, org_id, db)  # Allows admin for own org or super_admin
        else:
            check_super_admin(user, db)
        query = db.query(UsageLog).filter(UsageLog.endpoint.in_(VTO_ENDPOINTS))
        if org_id:
            query = query.filter(UsageLog.organization_id == org_id)
        recent_logs = query.order_by(UsageLog.timestamp.desc()).limit(10).all()

        def parse_request_data(data):
            try:
                return json.loads(data) if data else {}
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in request_data: {data}")
                return {}

        return [
            {
                "id": log.id,
                "organization_id": log.organization_id,
                "endpoint": log.endpoint,
                "request_data": parse_request_data(log.request_data),
                "response_status": log.response_status,
                "processing_time_ms": log.processing_time_ms,
                "timestamp": log.timestamp
            }
            for log in recent_logs
        ]
    except Exception as e:
        logger.error(f"Error in /recent-activities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/success-rate", response_model=SuccessRateResponse)
async def get_success_rate(
    org_id: int = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching success rate for user {user.email}, org_id={org_id}")
        if org_id:
            check_authorization(user, org_id, db)  # Allows admin for own org or super_admin
        else:
            check_super_admin(user, db)
        query = db.query(func.count(UsageLog.id)).filter(UsageLog.endpoint.in_(VTO_ENDPOINTS))
        if org_id:
            query = query.filter(UsageLog.organization_id == org_id)
        total_requests = query.scalar() or 0
        success_query = db.query(func.count(UsageLog.id)).filter(
            UsageLog.endpoint.in_(VTO_ENDPOINTS),
            UsageLog.response_status == 200
        )
        if org_id:
            success_query = success_query.filter(UsageLog.organization_id == org_id)
        success_requests = success_query.scalar() or 0

        success_rate = (success_requests / total_requests * 100) if total_requests > 0 else 0
        return {
            "success_requests": success_requests,
            "total_requests": total_requests,
            "success_rate": round(success_rate, 2)
        }
    except Exception as e:
        logger.error(f"Error in /success-rate: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/analytics", response_model=List[dict])
async def get_organization_analytics(
    org_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching analytics for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)
        logs = db.query(
            extract('year', UsageLog.timestamp).label('year'),
            extract('month', UsageLog.timestamp).label('month'),
            func.count(UsageLog.id).label('api_usage'),
            func.avg(UsageLog.processing_time_ms).label('avg_response_time'),
            func.sum(func.cast(UsageLog.response_status == 200, Integer)).label('success_count'),
            func.count(UsageLog.id).label('total_count')
        ).filter(
            UsageLog.organization_id == org_id,
            UsageLog.endpoint.in_(VTO_ENDPOINTS)
        ).group_by(
            extract('year', UsageLog.timestamp),
            extract('month', UsageLog.timestamp)
        ).order_by(
            extract('year', UsageLog.timestamp),
            extract('month', UsageLog.timestamp)
        ).all()

        return [
            {
                "month": f"{int(year)}-{int(month):02d}",
                "api_usage": int(api_usage),
                "avg_response_time": round(avg_response_time, 2) if avg_response_time else 0,
                "success_rate": round((success_count / total_count * 100) if total_count else 0, 2)
            }
            for year, month, api_usage, avg_response_time, success_count, total_count in logs
        ]
    except Exception as e:
        logger.error(f"Error in /organizations/{org_id}/analytics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/report/key-metrics", response_model=KeyMetrics)
async def get_key_metrics(
    org_id: int,
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching key metrics for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)

        query = db.query(
            func.count(TryonSession.id).label("total_sessions"),
            func.count(func.distinct(TryonSession.user_id)).label("unique_users"),
            func.avg(TryonSession.duration_seconds).label("avg_duration")
        ).filter(
            TryonSession.organization_id == org_id,
            TryonSession.created_at >= start_date,
            TryonSession.created_at <= end_date
        )

        result = query.first()
        if not result or result.total_sessions == 0:
            return KeyMetrics(
                total_sessions=0,
                unique_users=0,
                avg_duration=0.0,
                conversion_rate=0.0,
                status="No sessions found for the specified organization and date range"
            )

        # Conversion rate is not available since 'converted' field doesn't exist
        logger.warning("TryonSession.converted not available; setting conversion_rate to 0")
        conversion_rate = 0.0

        return KeyMetrics(
            total_sessions=result.total_sessions or 0,
            unique_users=result.unique_users or 0,
            avg_duration=round(float(result.avg_duration or 0), 2),
            conversion_rate=conversion_rate,
            status="Success"
        )
    except Exception as e:
        logger.error(f"Error in /key-metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/report/daily-sessions", response_model=DailySessionResponse)
async def get_daily_sessions(
    org_id: int,
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching daily sessions for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)

        query = db.query(
            func.date(TryonSession.created_at).label("date"),
            func.count(TryonSession.id).label("total_sessions"),
            func.count(func.distinct(TryonSession.user_id)).label("unique_users"),
            func.avg(TryonSession.duration_seconds).label("avg_duration"),
            func.max(TryonSession.created_at).label("peak_usage_hour")
        ).filter(
            TryonSession.organization_id == org_id,
            TryonSession.created_at >= start_date,
            TryonSession.created_at <= end_date
        ).group_by(
            func.date(TryonSession.created_at)
        ).order_by(
            func.date(TryonSession.created_at)
        )

        results = query.all()
        if not results:
            return DailySessionResponse(
                data=[],
                status="No daily sessions found for the specified organization and date range"
            )

        return DailySessionResponse(
            data=[
                DailySession(
                    date=str(r.date),
                    total_sessions=r.total_sessions or 0,
                    unique_users=r.unique_users or 0,
                    avg_duration=round(float(r.avg_duration or 0), 2),
                    peak_usage_hour=r.peak_usage_hour.strftime("%H:%M") if r.peak_usage_hour else None
                )
                for r in results
            ],
            status="Success"
        )
    except Exception as e:
        logger.error(f"Error in /daily-sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/report/most-tried-products", response_model=MostTriedProductResponse)
async def get_most_tried_products(
    org_id: int,
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching most tried products for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)

        # Product_name and category are not available in TryonSession
        logger.warning("TryonSession.product_name and category not available; returning empty product list")
        return MostTriedProductResponse(
            data=[],
            status="Product data not available due to missing schema fields"
        )
    except Exception as e:
        logger.error(f"Error in /most-tried-products: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/report/device-distribution", response_model=DeviceDistributionResponse)
async def get_device_distribution(
    org_id: int,
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching device distribution for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)

        total_sessions_query = db.query(
            func.count(TryonSession.id).label("total")
        ).filter(
            TryonSession.organization_id == org_id,
            TryonSession.created_at >= start_date,
            TryonSession.created_at <= end_date
        )

        total_sessions = total_sessions_query.scalar() or 1  # Avoid division by zero

        query = db.query(
            TryonSession.device_type,
            func.count(TryonSession.id).label("sessions")
        ).filter(
            TryonSession.organization_id == org_id,
            TryonSession.created_at >= start_date,
            TryonSession.created_at <= end_date,
            TryonSession.device_type.isnot(None)
        ).group_by(
            TryonSession.device_type
        )

        results = query.all()
        if not results:
            return DeviceDistributionResponse(
                data=[],
                status="No device distribution data found; ensure device_type is populated"
            )

        return DeviceDistributionResponse(
            data=[
                DeviceDistribution(
                    device_type=r.device_type,
                    sessions=r.sessions,
                    percentage=round((r.sessions / total_sessions * 100), 2)
                )
                for r in results
            ],
            status="Success"
        )
    except Exception as e:
        logger.error(f"Error in /device-distribution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/organizations/{org_id}/report/geographic-distribution", response_model=GeographicDistributionResponse)
async def get_geographic_distribution(
    org_id: int,
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Fetching geographic distribution for org_id={org_id}, user={user.email}")
        check_authorization(user, org_id, db)

        query = db.query(
            TryonSession.country,
            func.count(TryonSession.id).label("sessions")
        ).filter(
            TryonSession.organization_id == org_id,
            TryonSession.created_at >= start_date,
            TryonSession.created_at <= end_date,
            TryonSession.country.isnot(None)
        ).group_by(
            TryonSession.country
        ).order_by(
            func.count(TryonSession.id).desc()
        )

        results = query.all()
        if not results:
            return GeographicDistributionResponse(
                data=[],
                status="No geographic distribution data found; ensure country is populated"
            )

        return GeographicDistributionResponse(
            data=[
                GeographicDistribution(
                    country=r.country,
                    sessions=r.sessions
                )
                for r in results
            ],
            status="Success"
        )
    except Exception as e:
        logger.error(f"Error in /geographic-distribution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")