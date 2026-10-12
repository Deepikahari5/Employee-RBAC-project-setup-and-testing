"""User administration (Admin only): list users and change roles."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Role, User
from app.schemas import RoleUpdate, UserOut

router = APIRouter(prefix="/users", tags=["User Administration"])


@router.get("", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.user_id)).all()


@router.patch("/{user_id}/role", response_model=UserOut)
def change_role(
    user_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Only an Admin can assign or change roles. An invalid role value returns 422."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.role == Role.ADMIN and payload.role != Role.ADMIN:
        admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == Role.ADMIN.value))
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last remaining Admin",
            )

    target.role = payload.role.value
    db.commit()
    db.refresh(target)
    return target
