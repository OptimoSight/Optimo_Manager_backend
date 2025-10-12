import sys
import os
import uuid
import secrets
from datetime import datetime
import logging
from sqlalchemy import MetaData
from database import engine, SessionLocal
from models import Base, Role, User, RoleName, Subscription, Organization, ApiKey
from auth import get_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_and_seed_db():
    """Drops all tables, recreates them, and seeds initial data."""
    metadata = MetaData()
    metadata.reflect(bind=engine)

    logger.info("Dropping all existing tables...")
    metadata.drop_all(bind=engine)
    logger.info("All tables dropped successfully.")

    logger.info("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")

    db = SessionLocal()
    try:
        # Seed roles
        logger.info("Seeding roles...")
        for role_name in RoleName:
            if not db.query(Role).filter(Role.role == role_name).first():
                db.add(Role(role=role_name))
                logger.info(f"Seeded role: {role_name}")
        db.commit()
        logger.info("Roles seeded successfully.")

        # Seed Super_Admin user
        logger.info("Seeding Super_Admin user...")
        super_admin_email = "optimosight@mail.com"
        super_admin_password = "OptimoSight123"
        super_admin_name = "Optimo Admin"

        if not db.query(User).filter(User.email == super_admin_email).first():
            super_admin_role = db.query(Role).filter(Role.role == "super_admin").first()
            if not super_admin_role:
                raise Exception("Super_Admin role not found after seeding roles")

            super_admin_uid = str(uuid.uuid4())
            hashed_password = get_password_hash(super_admin_password)

            super_admin_user = User(
                uid=super_admin_uid,
                name=super_admin_name,
                email=super_admin_email,
                password_hash=hashed_password,
                role_id=super_admin_role.id,
                org_id=None
            )
            db.add(super_admin_user)
            db.commit()
            db.refresh(super_admin_user)
            logger.info(f"Default Super_Admin user '{super_admin_email}' created with UID: {super_admin_uid}")
        else:
            logger.info(f"Super_Admin user '{super_admin_email}' already exists, skipping creation.")

        # Seed Subscription Plans
        logger.info("Seeding subscription plans...")
        subscription_plans = [
            {
                "plan_name": "Free",
                "api_limit": 1000,
                "price": 0.0,
                "billing_period": "monthly",
                "features": {"makeup_categories": "Basic"}
            },
            {
                "plan_name": "Starter",
                "api_limit": 100000,
                "price": 49.0,
                "billing_period": "monthly",
                "features": {"makeup_categories": "Basic,Advanced", "white_labeling": True}
            },
            {
                "plan_name": "Pro",
                "api_limit": 1000000,
                "price": 199.0,
                "billing_period": "monthly",
                "features": {"makeup_categories": "All", "advanced_analytics": True}
            },
            {
                "plan_name": "Enterprise",
                "api_limit": 0,
                "price": 0.0,
                "billing_period": "monthly",
                "features": {"makeup_categories": "All", "custom_branding": True, "advanced_analytics": True}
            }
        ]

        for plan_data in subscription_plans:
            if not db.query(Subscription).filter(Subscription.plan_name == plan_data["plan_name"]).first():
                plan = Subscription(**plan_data)
                db.add(plan)
                logger.info(f"Seeded subscription plan: {plan_data['plan_name']}")
        db.commit()
        logger.info("Subscription plans seeded successfully.")

        # Seed Organizations
        logger.info("Seeding organizations...")
        if not db.query(Organization).filter(Organization.name == "Ainoviq It Ltd.").first():
            subscription = db.query(Subscription).filter(Subscription.plan_name == "Free").first()
            if not subscription:
                raise Exception("Free subscription plan not found after seeding subscriptions")
            org = Organization(
                name="Ainoviq It Ltd.",
                contact_email="a@mail.com",
                domain="ainoviqit.com",
                subscription_id=subscription.id,
                services=["vto_makeup"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            logger.info("Seeded organization: Ainoviq it ltd")

            # Seed Admin User for Organization
            logger.info("Seeding admin user for organization...")
            admin_email = "admin@test.com"
            admin_password = "admin123"
            admin_name = "Ainoviq Admin"

            if not db.query(User).filter(User.email == admin_email).first():
                admin_role = db.query(Role).filter(Role.role == "admin").first()
                if not admin_role:
                    raise Exception("Admin role not found after seeding roles")

                admin_uid = str(uuid.uuid4())
                hashed_password = get_password_hash(admin_password)

                admin_user = User(
                    uid=admin_uid,
                    name=admin_name,
                    email=admin_email,
                    password_hash=hashed_password,
                    role_id=admin_role.id,
                    org_id=org.id
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)
                logger.info(f"Default Admin user '{admin_email}' created with UID: {admin_uid}")
            else:
                logger.info(f"Admin user '{admin_email}' already exists, skipping creation.")

            # Seed API Key for Organization
            logger.info("Seeding API key for organization...")
            if not db.query(ApiKey).filter(ApiKey.organization_id == org.id).first():
                api_key_value = secrets.token_urlsafe(32)
                api_key = ApiKey(
                    organization_id=org.id,
                    api_key=api_key_value,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    expires_at=None
                )
                db.add(api_key)
                db.commit()
                logger.info(f"Seeded API key for organization: Test Org")
            else:
                logger.info("API key for organization 'Test Org' already exists, skipping creation.")
        else:
            logger.info("Organization 'Test Org' already exists, skipping creation.")

    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()
        logger.info("Database refresh and seeding process completed.")

if __name__ == "__main__":
    refresh_and_seed_db()