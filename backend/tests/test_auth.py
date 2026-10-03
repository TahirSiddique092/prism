"""Acceptance criteria tests for slice-03: Auth — register and login.

Acceptance criteria verified:
1. Passwords are hashed with bcrypt before insert — plain text is never stored or logged
2. JWT payload contains { user_id, email, exp } — expiry 24 hours
3. Registering with a duplicate email returns 409, not a 500
4. Wrong password returns 401 with a generic message (do not reveal which field is wrong)
5. Token is valid and decodable using JWT_SECRET from env
"""
import datetime
import os
import time
from unittest.mock import MagicMock, patch
import bcrypt
import jwt
import mysql.connector.errors
import pytest

from backend.app import create_app
from backend.modules.auth.routes import GENERIC_AUTH_ERROR
from backend.modules.auth.service import (
    check_password,
    decode_token,
    generate_token,
    get_jwt_secret,
    hash_password,
)


@pytest.fixture
def app():
    """Create application configured for testing."""
    test_app = create_app({"TESTING": True})
    return test_app


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """In-memory simulated database for user store during tests."""
    store = {}
    counter = [1]

    def mock_find_user_by_email(email, conn=None):
        return store.get(email.lower())

    def mock_create_user(name, email, password_hash, conn=None):
        email_key = email.lower()
        if email_key in store:
            raise mysql.connector.errors.IntegrityError("Duplicate entry for key 'email'")
        user_id = counter[0]
        counter[0] += 1
        store[email_key] = {
            "user_id": user_id,
            "name": name,
            "email": email_key,
            "password_hash": password_hash,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
        }
        return user_id

    with patch("backend.modules.auth.routes.find_user_by_email", side_effect=mock_find_user_by_email) as mock_find, \
         patch("backend.modules.auth.routes.create_user", side_effect=mock_create_user) as mock_create:
        yield {"store": store, "find": mock_find, "create": mock_create}


class TestAcceptanceCriterion1PasswordHashing:
    """AC 1: Passwords are hashed with bcrypt before insert — plain text is never stored or logged."""

    def test_hash_password_produces_valid_bcrypt(self):
        password = "SuperSecretPassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert check_password(password, hashed) is True
        assert check_password("WrongPassword!", hashed) is False

    def test_register_passes_only_bcrypt_hash_to_create_user(self, client, mock_db):
        plain_password = "MySecurePlainPassword"
        res = client.post(
            "/api/auth/register",
            json={"name": "Alice", "email": "alice@example.com", "password": plain_password},
        )
        assert res.status_code == 201

        # Verify what was passed to create_user
        mock_db["create"].assert_called_once()
        args = mock_db["create"].call_args[0]
        name_arg, email_arg, hash_arg = args[0], args[1], args[2]

        assert name_arg == "Alice"
        assert email_arg == "alice@example.com"
        assert hash_arg != plain_password
        assert hash_arg.startswith("$2b$") or hash_arg.startswith("$2a$")
        assert bcrypt.checkpw(plain_password.encode("utf-8"), hash_arg.encode("utf-8")) is True


class TestAcceptanceCriterion2And5JWT:
    """AC 2: JWT payload contains { user_id, email, exp } — expiry 24 hours.
    AC 5: Token is valid and decodable using JWT_SECRET from env.
    """

    def test_token_contains_required_payload_and_24h_expiry(self, monkeypatch):
        test_secret = "test-very-secure-jwt-secret-key-32-chars-long"
        monkeypatch.setenv("JWT_SECRET", test_secret)

        now = int(time.time())
        token = generate_token(42, "user42@example.com")

        decoded = decode_token(token)
        assert decoded["user_id"] == 42
        assert decoded["email"] == "user42@example.com"
        assert "exp" in decoded

        # Expiry should be approx 24 hours (86400 seconds) from now (+/- 5 seconds)
        expected_exp = now + 86400
        assert abs(decoded["exp"] - expected_exp) <= 5

    def test_token_decodable_with_env_secret(self, monkeypatch):
        test_secret = "custom-environment-jwt-secret-key-prism-12345"
        monkeypatch.setenv("JWT_SECRET", test_secret)

        token = generate_token(10, "test@test.com")
        # Direct decode using the raw secret confirms compatibility
        decoded = jwt.decode(token, test_secret, algorithms=["HS256"])
        assert decoded["user_id"] == 10
        assert decoded["email"] == "test@test.com"

        # Decoding with invalid secret raises error
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-secret-key-at-least-32-chars-long", algorithms=["HS256"])


class TestAcceptanceCriterion3DuplicateEmail:
    """AC 3: Registering with a duplicate email returns 409, not a 500."""

    def test_duplicate_email_returns_409(self, client, mock_db):
        payload = {"name": "Bob", "email": "bob@example.com", "password": "Password123"}

        # First registration
        res1 = client.post("/api/auth/register", json=payload)
        assert res1.status_code == 201

        # Duplicate registration with same email
        res2 = client.post("/api/auth/register", json=payload)
        assert res2.status_code == 409
        assert "error" in res2.get_json()
        assert "already exists" in res2.get_json()["error"].lower()

    def test_duplicate_email_with_case_insensitivity(self, client, mock_db):
        client.post(
            "/api/auth/register",
            json={"name": "Bob", "email": "bob@example.com", "password": "Password123"},
        )
        res = client.post(
            "/api/auth/register",
            json={"name": "Bob", "email": "BOB@EXAMPLE.COM", "password": "Password123"},
        )
        assert res.status_code == 409

    def test_db_integrity_error_returns_409_not_500(self, client):
        # Simulate race condition where find_user_by_email returns None,
        # but create_user raises IntegrityError
        with patch("backend.modules.auth.routes.find_user_by_email", return_value=None), \
             patch("backend.modules.auth.routes.create_user", side_effect=mysql.connector.errors.IntegrityError("Duplicate")):
            res = client.post(
                "/api/auth/register",
                json={"name": "Race", "email": "race@example.com", "password": "Password123"},
            )
            assert res.status_code == 409
            assert res.status_code != 500


class TestAcceptanceCriterion4LoginAuthentication:
    """AC 4: Wrong password returns 401 with a generic message (do not reveal which field is wrong)."""

    def test_login_successful(self, client, mock_db):
        client.post(
            "/api/auth/register",
            json={"name": "Charlie", "email": "charlie@example.com", "password": "CorrectPassword1"},
        )

        res = client.post(
            "/api/auth/login",
            json={"email": "charlie@example.com", "password": "CorrectPassword1"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert data["user_id"] == 1

        # Token should decode to Charlie's account
        decoded = decode_token(data["token"])
        assert decoded["email"] == "charlie@example.com"
        assert decoded["user_id"] == 1

    def test_wrong_password_returns_401_with_generic_message(self, client, mock_db):
        client.post(
            "/api/auth/register",
            json={"name": "Charlie", "email": "charlie@example.com", "password": "CorrectPassword1"},
        )

        res = client.post(
            "/api/auth/login",
            json={"email": "charlie@example.com", "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        data = res.get_json()
        assert data["error"] == GENERIC_AUTH_ERROR

    def test_nonexistent_email_returns_401_with_identical_generic_message(self, client, mock_db):
        res = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "AnyPassword"},
        )
        assert res.status_code == 401
        data = res.get_json()
        # AC requirement: generic message, does not reveal if email or password was wrong
        assert data["error"] == GENERIC_AUTH_ERROR


class TestEndpointValidationAndErrors:
    """Test 400 Bad Request error cases for missing / invalid fields."""

    @pytest.mark.parametrize("missing_field", ["name", "email", "password"])
    def test_register_missing_fields_returns_400(self, client, missing_field):
        payload = {"name": "Dave", "email": "dave@example.com", "password": "Password123"}
        del payload[missing_field]

        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "error" in res.get_json()

    @pytest.mark.parametrize("empty_val", ["", "   "])
    def test_register_empty_fields_returns_400(self, client, empty_val):
        res = client.post(
            "/api/auth/register",
            json={"name": empty_val, "email": "dave@example.com", "password": "Password123"},
        )
        assert res.status_code == 400

    def test_register_non_json_returns_400(self, client):
        res = client.post(
            "/api/auth/register",
            data="not json",
            content_type="text/plain",
        )
        assert res.status_code == 400

    def test_login_missing_password_returns_400(self, client):
        res = client.post("/api/auth/login", json={"email": "dave@example.com"})
        assert res.status_code == 400

    def test_login_missing_email_returns_400(self, client):
        res = client.post("/api/auth/login", json={"password": "Password123"})
        assert res.status_code == 400

    def test_login_non_json_returns_400(self, client):
        res = client.post(
            "/api/auth/login",
            data="not json",
            content_type="text/plain",
        )
        assert res.status_code == 400
