"""FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.bootstrap import seed_admin
from app.database import Base, SessionLocal, engine
from app.routers import auth, employees, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_admin(db)
    yield


app = FastAPI(
    title="Employee Management API (JWT + RBAC)",
    description=(
        "Employee management with JWT authentication and role-based access control.\n\n"
        "Click **Authorize** and log in with your email + password to test protected endpoints."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(employees.router)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.warning("Integrity error on %s: %s", request.url.path, exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "A record with the same unique value already exists"},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred. Please try again later."},
    )


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok"}
