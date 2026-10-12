"""Database models."""
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.EMPLOYEE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(100), index=True)
    designation: Mapped[str] = mapped_column(String(100), index=True)
    salary: Mapped[float] = mapped_column(Float)
    joining_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
