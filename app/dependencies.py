"""Reusable authentication and authorization dependencies."""
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Authentication: validate the JWT and load the user (401 on any failure)."""
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("Could not validate credentials")

    sub = payload.get("sub")
    if not sub or not str(sub).isdigit():
        raise _unauthorized("Could not validate credentials")

    user = db.get(User, int(sub))
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
) -> Optional[User]:
    """No token -> None. A token that is present but bad still raises 401."""
    if token is None:
        return None
    return get_current_user(token=token, db=db)


def require_roles(*allowed_roles: Role):
    """Authorization: dependency factory that returns the user if their role is allowed (403 otherwise)."""

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in {r.value for r in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return checker


require_admin = require_roles(Role.ADMIN)
require_admin_or_manager = require_roles(Role.ADMIN, Role.MANAGER)
