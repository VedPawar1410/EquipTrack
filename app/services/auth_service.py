"""Passwords, tokens and role ranking. No FastAPI imports: routers/dependencies map errors to HTTP."""
from datetime import timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.models.user import UserTable
from app.schemas.common import utc_now
from app.schemas.user import Role

# Argon2id with pwdlib's recommended parameters (what FastAPI's docs use; passlib is unmaintained).
_hasher = PasswordHash.recommended()
# Verified against when the username doesn't exist, so "no such user" and "wrong password"
# take the same time and an attacker can't discover valid usernames by timing the response.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

ROLE_RANK = {Role.TECHNICIAN: 1, Role.SUPERVISOR: 2, Role.ADMIN: 3}


class InvalidToken(Exception):
    pass


class NotPermitted(Exception):
    """The user is authenticated but their role doesn't allow this action (HTTP 403)."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)


def authenticate(user: UserTable | None, password: str) -> bool:
    if user is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return verify_password(password, user.hashed_password) and user.is_active


def has_role(role: Role | str, minimum: Role) -> bool:
    return ROLE_RANK[Role(role)] >= ROLE_RANK[minimum]


def create_access_token(user_id: UUID) -> str:
    # Only the user id goes in the token. Role and is_active are re-read from the DB on every
    # request, so a demotion or deactivation applies immediately, not when the token expires.
    now = utc_now()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:  # bad signature, expired, malformed
        raise InvalidToken() from exc
