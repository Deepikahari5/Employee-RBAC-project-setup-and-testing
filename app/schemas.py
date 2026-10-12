"""Pydantic request/response schemas with validation."""
import re
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import Role

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Salary = Annotated[float, Field(gt=0, le=1_000_000_000)]

_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_phone(value: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", value)
    if not _PHONE_RE.match(cleaned):
        raise ValueError("Phone number must contain 7-15 digits, optionally starting with '+'")
    return cleaned


# ---------------------------------------------------------------- Auth / Users
class UserCreate(BaseModel):
    full_name: Name
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    # Only an authenticated Admin may supply a role other than "Employee".
    role: Optional[Role] = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: EmailStr
    role: Role
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleUpdate(BaseModel):
    role: Role


# -------------------------------------------------------------------- Employees
class EmployeeCreate(BaseModel):
    employee_name: Name
    email: EmailStr
    phone_number: str
    department: ShortText
    designation: ShortText
    salary: Salary
    joining_date: date

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class EmployeeUpdate(BaseModel):
    employee_name: Optional[Name] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    department: Optional[ShortText] = None
    designation: Optional[ShortText] = None
    salary: Optional[Salary] = None
    joining_date: Optional[date] = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, v):
        return _normalize_email(v) if v is not None else v

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, v):
        return _normalize_phone(v) if v is not None else v

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        return self


class PhoneUpdate(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    employee_name: str
    email: EmailStr
    phone_number: str
    department: str
    designation: str
    salary: float
    joining_date: date
    created_at: datetime
