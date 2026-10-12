"""Application settings, read from environment variables with safe dev defaults."""
import os

SECRET_KEY = os.getenv(
    "SECRET_KEY", "dev-only-secret-change-me-use-a-long-random-string-in-production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./employee_rbac.db")

# Bootstrap admin (created on startup if it does not exist).
ADMIN_NAME = os.getenv("ADMIN_NAME", "System Admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@12345")
