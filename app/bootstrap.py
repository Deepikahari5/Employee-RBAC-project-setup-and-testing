

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.models import Role, User
from app.security import hash_password

logger = logging.getLogger(__name__)


def seed_admin(db: Session) -> None:
    exists = db.scalar(select(User).where(User.email == config.ADMIN_EMAIL))
    if exists:
        return
    db.add(
        User(
            full_name=config.ADMIN_NAME,
            email=config.ADMIN_EMAIL,
            hashed_password=hash_password(config.ADMIN_PASSWORD),
            role=Role.ADMIN.value,
        )
    )
    db.commit()
    logger.warning(
        "Seeded admin account %s. Change ADMIN_PASSWORD / SECRET_KEY before deploying.",
        config.ADMIN_EMAIL,
    )
