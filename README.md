

FastAPI + SQLAlchemy + SQLite. Passwords are hashed with bcrypt, access tokens are JWTs,
and authorization is enforced through reusable FastAPI dependencies.

## Project structure

```
rbac_employee_api/
├── app/
│   ├── main.py            # app, routers, global error handlers, startup (tables + admin seed)
│   ├── config.py          # env-based settings
│   ├── database.py        # engine, session, get_db
│   ├── models.py          # User, Employee, Role enum
│   ├── schemas.py         # Pydantic validation
│   ├── security.py        # bcrypt hashing + JWT create/decode
│   ├── dependencies.py    # get_current_user, get_optional_user, require_roles(...)
│   ├── bootstrap.py       # seeds the first Admin
│   └── routers/
│       ├── auth.py        # POST /register, POST /login, GET /users/me
│       ├── users.py       # GET /users, PATCH /users/{id}/role  (Admin only)
│       └── employees.py   # Employee CRUD + search/filter + /me endpoints
├── tests/                 # pytest suite (17 tests)
├── postman_collection.json
├── employee_rbac.db       # SQLite DB (auto-created; ships with only the seeded Admin)
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional: set environment variables (see `.env.example`), especially `SECRET_KEY` outside local development.

## Run

```bash
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

On first start the tables are created and an Admin account is seeded:

| Email               | Password      |
|---------------------|---------------|
| `admin@example.com` | `Admin@12345` |

Change these with `ADMIN_EMAIL` / `ADMIN_PASSWORD` **before** the first run.

## How roles work

| Action                              | Admin | Manager  | Employee            |
|-------------------------------------|:-----:|:--------:|:-------------------:|
| `POST /employees`                   |  ✅   |  ❌ 403  |  ❌ 403             |
| `GET /employees` (list/search)      |  all  |   all    |  own record only    |
| `GET /employees/{id}`               |  ✅   |   ✅     |  own only, else 403 |
| `PUT /employees/{id}`               |  ✅   |   ✅     |  ❌ 403             |
| `DELETE /employees/{id}`            |  ✅   |  ❌ 403  |  ❌ 403             |
| `GET /employees/me`, `PATCH /employees/me/phone` | ✅ | ✅ | ✅             |
| `GET /users`, `PATCH /users/{id}/role` | ✅ | ❌ 403 | ❌ 403             |

**Assigning roles**
- `POST /register` is public, but the new account is always an `Employee`.
- Sending `"role": "Manager"` or `"Admin"` only works when the request carries an **Admin** token
  (no token → 401, non-admin token → 403). Nobody can grant themselves extra permissions.
- Admins can also change an existing user's role with `PATCH /users/{user_id}/role`
  (invalid role → 422; the last remaining Admin cannot be demoted → 400).

**Linking a login to an employee record:** a user account is linked to an employee record by
**matching email**. To give an Employee-role user access to their own details, an Admin creates the
employee record with the same email the user registered with.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/register` | JSON: `full_name`, `email`, `password`, optional `role` |
| POST | `/login` | **Form data**: `username` (= your email), `password` → `{access_token, token_type}` |
| GET | `/users/me` | Current user |
| GET | `/users` | Admin only |
| PATCH | `/users/{user_id}/role` | Admin only, body `{"role": "Manager"}` |
| POST | `/employees` | Admin only |
| GET | `/employees` | Filters: `department`, `designation`, `min_salary`, `max_salary`, `skip`, `limit` |
| GET | `/employees/me` | Logged-in user's employee profile |
| PATCH | `/employees/me/phone` | Body `{"phone_number": "9876543210"}` |
| GET | `/employees/{employee_id}` | |
| PUT | `/employees/{employee_id}` | Partial updates allowed; at least one field required |
| DELETE | `/employees/{employee_id}` | Returns 204 |

Filter examples:
```
GET /employees?department=IT
GET /employees?designation=Developer
GET /employees?min_salary=30000&max_salary=80000
GET /employees?department=IT&min_salary=50000
```
`department` and `designation` are case-insensitive exact matches. `min_salary > max_salary` returns 422.

## Status codes used

| Code | When |
|------|------|
| 200 / 201 / 204 | Success / created / deleted |
| 401 | Missing, invalid, expired token; wrong email or password |
| 403 | Authenticated but role not allowed / accessing another employee's record |
| 404 | Employee or user not found |
| 409 | Duplicate email |
| 422 | Validation error (bad salary, phone, role, email, weak password, empty update…) |
| 500 | Unexpected database error (generic message; details only in server logs) |

## Testing with Swagger UI

1. Open `/docs` → click **Authorize**.
2. Enter `username` = `admin@example.com`, `password` = `Admin@12345` → **Authorize**.
3. Try the endpoints. To test another role, register a user (as Admin, set `role`), click **Authorize → Logout**, and log in as that user.

## Testing with Postman

1. Import `postman_collection.json`.
2. Start the server, then run the collection with the **Collection Runner**, in order.
3. The first request generates a unique `run_id`, so the collection can be re-run repeatedly. Tokens and IDs are stored in collection variables automatically.
4. The 54 requests cover: registering users with different roles, valid/invalid login, valid/missing/invalid tokens, Admin/Manager/Employee permissions, accessing another employee's details, role changes by non-Admins, invalid roles, duplicate emails, invalid salary, search/filter, `/me` endpoints, and update/delete. Each request has a status-code assertion.

To check an **expired** token manually, set `ACCESS_TOKEN_EXPIRE_MINUTES=1`, log in, wait a minute, and call any protected endpoint (→ 401 "Token has expired").

## Verify passwords are never stored in plain text

```bash
sqlite3 employee_rbac.db "SELECT email, hashed_password FROM users;"
```
Every value starts with `$2b$` (bcrypt). Passwords are never returned by any endpoint.

## Automated tests

```bash
pytest -q
```
Uses a temporary SQLite file, so your real database is untouched.

## Design notes

- **Authentication vs authorization:** `get_current_user` (authentication → 401) validates the JWT and loads the user from the database on every request; `require_roles(...)` (authorization → 403) builds on it. The role is read from the DB, not trusted from the token, so a role change takes effect immediately.
- **Reusable dependencies:** `require_admin`, `require_admin_or_manager`, and `require_roles(Role.X, ...)` can be dropped into any route.
- **Route order:** `/employees/me` is declared before `/employees/{employee_id}` so "me" isn't parsed as an ID.
- **No ID probing:** an Employee requesting someone else's record gets 403 whether or not that ID exists.
- **Login:** identical error for unknown email and wrong password, and a dummy hash check keeps timing similar.
- **Production checklist:** set a strong `SECRET_KEY`, change the seeded Admin password, serve over HTTPS, and consider PostgreSQL/MySQL with Alembic migrations.

## Running in VS Code

1. **File → Open Folder…** and choose `rbac_employee_api`.
2. Open a terminal (**Terminal → New Terminal**) and run:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
   - Then: `pip install -r requirements.txt`
3. Press `Ctrl+Shift+P` → **Python: Select Interpreter** → pick the `.venv` one.
4. Press **F5** (Run and Debug → "Run FastAPI (uvicorn)"), or run `uvicorn app.main:app --reload` in the terminal.
5. Open http://127.0.0.1:8000/docs. Use **Authorize** with `admin@example.com` / `Admin@12345`.
6. Tests: run "Run tests (pytest)" from Run and Debug, or `pytest -q` in the terminal.
