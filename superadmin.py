import uuid
import logging
from sqlalchemy.orm import Session
from models import User, Role  # Absolute import
from auth import get_password_hash  # Absolute import

logger = logging.getLogger(__name__)

def seed_super_admin(db: Session):
    super_admin_role = db.query(Role).filter(Role.role == "super_admin").first()
    if not super_admin_role:
        logger.error("Super admin role not found during seeding")
        return

    super_admin = db.query(User).filter(User.email == "optimosight@mail.com").first()
    if not super_admin:
        hashed_password = get_password_hash("OptimoSight123")
        super_admin = User(
            uid=str(uuid.uuid4()),
            name="Optimo Admin",
            email="optimosight@mail.com",
            password_hash=hashed_password,
            role_id=super_admin_role.id,
            org_id=None,  # Explicitly None for super_admin
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(super_admin)
        db.commit()
        logger.info("Seeded super admin user")