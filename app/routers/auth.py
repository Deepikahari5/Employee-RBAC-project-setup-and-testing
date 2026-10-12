"""Authentication endpoints: /register, /login, /users/me."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models import Role, User
from app.schemas import Token, UserCreate, UserOut
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Public sign-up. New accounts are always 'Employee' unless an Admin is logged in and sets a role."""
    requested_role = payload.role or Role.EMPLOYEE

    if requested_role != Role.EMPLOYEE:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to assign a role other than Employee",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an Admin can assign roles",
            )

    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=requested_role.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with email (sent as the OAuth2 'username' field) and password."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    # Always run a hash check so response time doesn't reveal whether the email exists.
    password_ok = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.user_id))


@router.get("/users/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user
