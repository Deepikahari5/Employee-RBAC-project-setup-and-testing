import jwt
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.config import ALGORITHM, SECRET_KEY
from app.database import engine

PW = "Passw0rd!"


def login(client, email, password=PW):
    r = client.post("/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def admin_headers(client):
    return login(client, "admin@example.com", "Admin@12345")


def make_user(client, email, role=None, name="Test User"):
    body = {"full_name": name, "email": email, "password": PW}
    headers = {}
    if role:
        body["role"] = role
        headers = admin_headers(client)
    r = client.post("/register", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def emp_body(email="john@example.com", **over):
    body = {
        "employee_name": "John Doe",
        "email": email,
        "phone_number": "9876543210",
        "department": "IT",
        "designation": "Developer",
        "salary": 50000,
        "joining_date": "2024-01-15",
    }
    body.update(over)
    return body


def create_emp(client, **kw):
    r = client.post("/employees", json=emp_body(**kw), headers=admin_headers(client))
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ auth
def test_register_defaults_to_employee_and_hides_password(client):
    u = make_user(client, "a@example.com")
    assert u["role"] == "Employee"
    assert "password" not in u and "hashed_password" not in u


def test_password_is_hashed_in_database(client):
    make_user(client, "a@example.com")
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT hashed_password FROM users WHERE email='a@example.com'")).scalar()
    assert stored != PW and stored.startswith("$2")


def test_register_duplicate_email(client):
    make_user(client, "a@example.com")
    r = client.post("/register", json={"full_name": "X Y", "email": "A@example.com", "password": PW})
    assert r.status_code == 409


def test_register_weak_password_and_bad_email(client):
    assert client.post("/register", json={"full_name": "X Y", "email": "a@example.com", "password": "short"}).status_code == 422
    assert client.post("/register", json={"full_name": "X Y", "email": "a@example.com", "password": "onlyletters"}).status_code == 422
    assert client.post("/register", json={"full_name": "X Y", "email": "nope", "password": PW}).status_code == 422


def test_cannot_self_register_as_admin(client):
    r = client.post("/register", json={"full_name": "Evil", "email": "e@example.com", "password": PW, "role": "Admin"})
    assert r.status_code == 401


def test_non_admin_cannot_register_privileged_user(client):
    make_user(client, "m@example.com", role="Manager")
    h = login(client, "m@example.com")
    r = client.post("/register", json={"full_name": "Evil", "email": "e@example.com", "password": PW, "role": "Admin"}, headers=h)
    assert r.status_code == 403


def test_login_valid_and_invalid(client):
    make_user(client, "a@example.com")
    assert client.post("/login", data={"username": "a@example.com", "password": PW}).status_code == 200
    assert client.post("/login", data={"username": "a@example.com", "password": "Wrong123"}).status_code == 401
    assert client.post("/login", data={"username": "ghost@example.com", "password": PW}).status_code == 401


def test_users_me(client):
    make_user(client, "a@example.com", name="Alice A")
    r = client.get("/users/me", headers=login(client, "a@example.com"))
    assert r.status_code == 200 and r.json()["email"] == "a@example.com"


def test_missing_invalid_expired_token(client):
    assert client.get("/employees").status_code == 401
    assert client.get("/employees", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET_KEY, algorithm=ALGORITHM
    )
    r = client.get("/employees", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    forged = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-key", algorithm=ALGORITHM)
    assert client.get("/employees", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# ------------------------------------------------------------------ roles
def test_role_change_rules(client):
    emp = make_user(client, "e@example.com")
    make_user(client, "m@example.com", role="Manager")
    # non-admins can't change roles (including their own)
    assert client.patch(f"/users/{emp['user_id']}/role", json={"role": "Admin"}, headers=login(client, "e@example.com")).status_code == 403
    assert client.patch(f"/users/{emp['user_id']}/role", json={"role": "Admin"}, headers=login(client, "m@example.com")).status_code == 403
    # invalid role
    ah = admin_headers(client)
    assert client.patch(f"/users/{emp['user_id']}/role", json={"role": "SuperUser"}, headers=ah).status_code == 422
    # admin can
    r = client.patch(f"/users/{emp['user_id']}/role", json={"role": "Manager"}, headers=ah)
    assert r.status_code == 200 and r.json()["role"] == "Manager"
    assert client.patch("/users/9999/role", json={"role": "Manager"}, headers=ah).status_code == 404


def test_cannot_remove_last_admin(client):
    ah = admin_headers(client)
    me = client.get("/users/me", headers=ah).json()
    assert client.patch(f"/users/{me['user_id']}/role", json={"role": "Employee"}, headers=ah).status_code == 400


# -------------------------------------------------------------- employees
def test_admin_crud(client):
    ah = admin_headers(client)
    e = create_emp(client)
    eid = e["employee_id"]
    assert client.get("/employees", headers=ah).json()[0]["employee_id"] == eid
    assert client.get(f"/employees/{eid}", headers=ah).status_code == 200
    r = client.put(f"/employees/{eid}", json={"salary": 60000, "designation": "Senior Developer"}, headers=ah)
    assert r.status_code == 200 and r.json()["salary"] == 60000
    assert client.delete(f"/employees/{eid}", headers=ah).status_code == 204
    assert client.get(f"/employees/{eid}", headers=ah).status_code == 404
    assert client.delete(f"/employees/{eid}", headers=ah).status_code == 404


def test_manager_permissions(client):
    e = create_emp(client)
    make_user(client, "m@example.com", role="Manager")
    mh = login(client, "m@example.com")
    assert client.post("/employees", json=emp_body("x@example.com"), headers=mh).status_code == 403
    assert client.delete(f"/employees/{e['employee_id']}", headers=mh).status_code == 403
    assert client.get("/employees", headers=mh).status_code == 200
    assert client.get(f"/employees/{e['employee_id']}", headers=mh).status_code == 200
    r = client.put(f"/employees/{e['employee_id']}", json={"department": "HR"}, headers=mh)
    assert r.status_code == 200 and r.json()["department"] == "HR"


def test_employee_can_only_see_own(client):
    mine = create_emp(client, email="me@example.com", employee_name="Me Myself")
    other = create_emp(client, email="other@example.com", employee_name="Other One")
    make_user(client, "me@example.com")
    h = login(client, "me@example.com")
    assert client.get(f"/employees/{mine['employee_id']}", headers=h).status_code == 200
    assert client.get(f"/employees/{other['employee_id']}", headers=h).status_code == 403
    assert client.get("/employees/99999", headers=h).status_code == 403
    listing = client.get("/employees", headers=h).json()
    assert [x["email"] for x in listing] == ["me@example.com"]
    assert client.post("/employees", json=emp_body("n@example.com"), headers=h).status_code == 403
    assert client.put(f"/employees/{mine['employee_id']}", json={"salary": 1}, headers=h).status_code == 403
    assert client.delete(f"/employees/{mine['employee_id']}", headers=h).status_code == 403


def test_employee_validation_and_duplicates(client):
    ah = admin_headers(client)
    create_emp(client)
    assert client.post("/employees", json=emp_body(), headers=ah).status_code == 409
    assert client.post("/employees", json=emp_body("a@example.com", salary=-5), headers=ah).status_code == 422
    assert client.post("/employees", json=emp_body("b@example.com", salary=0), headers=ah).status_code == 422
    assert client.post("/employees", json=emp_body("c@example.com", phone_number="abc"), headers=ah).status_code == 422
    assert client.post("/employees", json=emp_body("d@example.com", joining_date="not-a-date"), headers=ah).status_code == 422
    # update into a duplicate email
    other = create_emp(client, email="o@example.com")
    assert client.put(f"/employees/{other['employee_id']}", json={"email": "john@example.com"}, headers=ah).status_code == 409
    assert client.put(f"/employees/{other['employee_id']}", json={}, headers=ah).status_code == 422


def test_filters(client):
    create_emp(client, email="a@example.com", department="IT", designation="Developer", salary=40000)
    create_emp(client, email="b@example.com", department="IT", designation="Tester", salary=90000)
    create_emp(client, email="c@example.com", department="HR", designation="Developer", salary=70000)
    ah = admin_headers(client)
    emails = lambda r: sorted(x["email"] for x in r.json())
    assert emails(client.get("/employees?department=it", headers=ah)) == ["a@example.com", "b@example.com"]
    assert emails(client.get("/employees?designation=Developer", headers=ah)) == ["a@example.com", "c@example.com"]
    assert emails(client.get("/employees?min_salary=30000&max_salary=80000", headers=ah)) == ["a@example.com", "c@example.com"]
    assert emails(client.get("/employees?department=IT&min_salary=50000", headers=ah)) == ["b@example.com"]
    assert client.get("/employees?min_salary=90000&max_salary=100", headers=ah).status_code == 422


def test_me_endpoints(client):
    create_emp(client, email="me@example.com")
    make_user(client, "me@example.com")
    h = login(client, "me@example.com")
    assert client.get("/employees/me", headers=h).json()["email"] == "me@example.com"
    r = client.patch("/employees/me/phone", json={"phone_number": "+91 98765 00000"}, headers=h)
    assert r.status_code == 200 and r.json()["phone_number"] == "+919876500000"
    assert client.patch("/employees/me/phone", json={"phone_number": "12"}, headers=h).status_code == 422
    # user with no employee record
    make_user(client, "norecord@example.com")
    assert client.get("/employees/me", headers=login(client, "norecord@example.com")).status_code == 404
