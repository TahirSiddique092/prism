"""Authentication route handlers for PRISM (Slice 03).

Implements:
- POST /api/auth/register
- POST /api/auth/login
"""
import mysql.connector
from flask import Blueprint, jsonify, request

from .db import create_user, find_user_by_email
from .service import check_password, generate_token, hash_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

GENERIC_AUTH_ERROR = "Invalid email or password"


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user account.
    
    Request: { name, email, password }
    Response: { user_id, token } (HTTP 201)
    Errors:
        400 - Missing required fields or invalid payload
        409 - Email already exists
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON"}), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    # Validate that all required fields are provided and non-empty strings
    if not (isinstance(name, str) and name.strip() and
            isinstance(email, str) and email.strip() and
            isinstance(password, str) and password.strip()):
        return jsonify({"error": "Missing required fields: name, email, and password are required"}), 400

    name = name.strip()
    email = email.strip().lower()

    # Pre-check if email already exists
    try:
        existing_user = find_user_by_email(email)
        if existing_user:
            return jsonify({"error": "Email already exists"}), 409

        # Hash password with bcrypt before persistence — plaintext is never stored or logged
        password_hash = hash_password(password)

        # Insert user into database
        user_id = create_user(name, email, password_hash)

        # Generate 24-hour signed JWT
        token = generate_token(user_id, email)

        return jsonify({
            "user_id": user_id,
            "token": token,
        }), 201

    except mysql.connector.errors.IntegrityError:
        # Catch concurrent race condition / database unique constraint violation
        return jsonify({"error": "Email already exists"}), 409


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate an existing user.
    
    Request: { email, password }
    Response: { user_id, token } (HTTP 200)
    Errors:
        400 - Missing required fields or invalid payload
        401 - Invalid email or password (generic message; does not reveal field)
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON"}), 400

    email = data.get("email")
    password = data.get("password")

    if not (isinstance(email, str) and email.strip() and
            isinstance(password, str) and password.strip()):
        return jsonify({"error": "Missing required fields: email and password are required"}), 400

    email = email.strip().lower()

    user = find_user_by_email(email)

    # Acceptance criterion: Generic message on failure — do not reveal whether email or password was wrong
    if not user:
        return jsonify({"error": GENERIC_AUTH_ERROR}), 401

    if not check_password(password, user["password_hash"]):
        return jsonify({"error": GENERIC_AUTH_ERROR}), 401

    # Generate 24-hour signed JWT
    token = generate_token(user["user_id"], user["email"])

    return jsonify({
        "user_id": user["user_id"],
        "token": token,
    }), 200
