from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime

Base = declarative_base()

class RoleName(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    guest = "guest"

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(SQLEnum(RoleName), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(50), unique=True, nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String(50), unique=True, index=True)
    price = Column(Float)
    api_limit = Column(Integer)
    billing_period = Column(String(20))
    features = Column(JSON, nullable=True)
    services = Column(JSON, default=["vto_makeup"])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    contact_email = Column(String(100), unique=True)
    domain = Column(String(100))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    services = Column(JSON, default=["vto_makeup"])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), unique=True, nullable=True)
    contact_person = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    endpoint = Column(String(50), nullable=False)
    request_data = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())

class BillingStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    
class Billing(Base):
    __tablename__ = "billing"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_calls = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(SQLEnum(BillingStatus), nullable=False)
    created_at = Column(DateTime, default=func.now())

class TryonSession(Base):
    __tablename__ = "tryon_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    image_url = Column(String(255), nullable=True)
    duration_seconds = Column(Integer, nullable=False)
    device_type = Column(String(50), nullable=True)  # For device_distribution
    country = Column(String(100), nullable=True)     # For geographic_distribution
    product_name = Column(String(255), nullable=True)  # For most-tried-products
    category = Column(String(100), nullable=True)      # For most-tried-products
    converted = Column(Boolean, default=False, nullable=True)  # For conversion rate
    created_at = Column(DateTime, default=func.now())

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

