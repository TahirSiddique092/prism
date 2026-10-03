"""Authentication business logic and security utilities for PRISM.

Handles password hashing via bcrypt and JWT token generation/validation.
Plain text passwords are never stored, returned, or logged.
"""
import datetime
import os
import bcrypt
import jwt

# 24-hour token lifetime as specified in slice-03 acceptance criteria
TOKEN_EXPIRY_HOURS = 24
# Fallback secret for development if JWT_SECRET is not explicitly set in the environment
DEFAULT_DEV_SECRET = "prism-development-jwt-secret-key-at-least-32-chars-long"


def get_jwt_secret() -> str:
    """Retrieve the JWT secret from environment variables."""
    return os.getenv("JWT_SECRET", DEFAULT_DEV_SECRET)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with a generated salt.
    
    Returns the hashed password as a string suitable for storage in MySQL password_hash column.
    Plaintext passwords are never stored or logged.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.
    
    Returns True if valid, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def generate_token(user_id: int, email: str) -> str:
    """Generate a signed JWT token containing user_id, email, and 24-hour expiry.
    
    Payload strictly adheres to slice-03 acceptance criteria:
    { user_id, email, exp }
    """
    secret = get_jwt_secret()
    now = datetime.datetime.now(datetime.timezone.utc)
    exp_time = now + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS)
    
    payload = {
        "user_id": int(user_id),
        "email": email,
        "exp": exp_time,
    }
    
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a signed JWT token using the configured JWT_SECRET.
    
    Raises jwt.ExpiredSignatureError if expired, or jwt.InvalidTokenError if invalid.
    """
    secret = get_jwt_secret()
    return jwt.decode(token, secret, algorithms=["HS256"])
