"""Employee CRUD with role-based access control.

Access matrix
-------------
                      Admin   Manager   Employee
POST   /employees       Y        -         -
GET    /employees       Y (all)  Y (all)   own record only
GET    /employees/me    Y        Y         Y   (needs an employee record with the same email)
PATCH  /employees/me/phone  Y    Y         Y
GET    /employees/{id}  Y        Y         own record only (403 otherwise)
PUT    /employees/{id}  Y        Y         -
DELETE /employees/{id}  Y        -         -

A login account is linked to an employee record by matching email address.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_admin_or_manager
from app.models import Employee, Role, User
from app.schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate, PhoneUpdate

router = APIRouter(prefix="/employees", tags=["Employees"])


def _own_record(db: Session, user: User) -> Optional[Employee]:
    return db.scalar(select(Employee).where(Employee.email == user.email))


def _email_taken(db: Session, email: str, exclude_id: Optional[int] = None) -> bool:
    stmt = select(Employee.employee_id).where(Employee.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Employee.employee_id != exclude_id)
    return db.scalar(stmt) is not None


def _conflict() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Employee email already exists")


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if _email_taken(db, payload.email):
        raise _conflict()
    employee = Employee(**payload.model_dump())
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict()
    db.refresh(employee)
    return employee


@router.get("", response_model=List[EmployeeOut])
def list_employees(
    department: Optional[str] = Query(None, min_length=1, description="Case-insensitive exact match"),
    designation: Optional[str] = Query(None, min_length=1, description="Case-insensitive exact match"),
    min_salary: Optional[float] = Query(None, ge=0),
    max_salary: Optional[float] = Query(None, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if min_salary is not None and max_salary is not None and min_salary > max_salary:
        raise HTTPException(
            status_code=422,
            detail="min_salary cannot be greater than max_salary",
        )

    stmt = select(Employee)
    if current_user.role == Role.EMPLOYEE:
        stmt = stmt.where(Employee.email == current_user.email)  # only their own record
    if department:
        stmt = stmt.where(func.lower(Employee.department) == department.strip().lower())
    if designation:
        stmt = stmt.where(func.lower(Employee.designation) == designation.strip().lower())
    if min_salary is not None:
        stmt = stmt.where(Employee.salary >= min_salary)
    if max_salary is not None:
        stmt = stmt.where(Employee.salary <= max_salary)

    stmt = stmt.order_by(Employee.employee_id).offset(skip).limit(limit)
    return db.scalars(stmt).all()


# NOTE: /me routes must be declared before /{employee_id}.
@router.get("/me", response_model=EmployeeOut)
def my_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = _own_record(db, current_user)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No employee record is linked to your account",
        )
    return employee


@router.patch("/me/phone", response_model=EmployeeOut)
def update_my_phone(
    payload: PhoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _own_record(db, current_user)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No employee record is linked to your account",
        )
    employee.phone_number = payload.phone_number
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == Role.EMPLOYEE:
        own = _own_record(db, current_user)
        # Same 403 whether or not the requested id exists, so ids can't be probed.
        if own is None or own.employee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own employee details",
            )
        return own

    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_manager),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes and _email_taken(db, changes["email"], exclude_id=employee_id):
        raise _conflict()

    for field, value in changes.items():
        setattr(employee, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    db.delete(employee)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
