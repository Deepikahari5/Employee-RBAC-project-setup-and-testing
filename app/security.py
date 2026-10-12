"""Password hashing and JWT helpers."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = hash_password("dummy-password-1")


def create_access_token(user_id: int, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
