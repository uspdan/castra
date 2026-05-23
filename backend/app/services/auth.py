from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
settings = get_settings()

ALGORITHM = "HS256"

# R21 audit finding — bind every issued token to this product so a
# token minted by a different service that happens to share
# ``SECRET_KEY`` cannot cross-validate here.
JWT_ISSUER = "siege-range"
JWT_AUDIENCE = "siege-range-api"

# R9 audit finding — when the login lookup returns no user, run a
# bcrypt verify against a fixed dummy hash so the request still
# pays the bcrypt cost. Without this, an unknown email returns in
# ~6 ms while a known email takes ~186 ms, leaking account
# existence via the response timing.
#
# The dummy is computed once at import time. The password it hashes
# is unguessable in the sense that no real user has it as their
# password (and even if they did, ``ghost_login_check`` is only
# ever called when ``user is None``).
_DUMMY_BCRYPT_HASH = pwd_context.hash("siege-range-ghost-login-check-v1")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def ghost_login_check(plain_password: str) -> None:
    """Constant-time stand-in for bcrypt on the unknown-user branch.

    Always returns ``None`` and always pays the bcrypt round so the
    response time of a login against an unknown email matches the
    response time against a known email with a wrong password.

    See :data:`_DUMMY_BCRYPT_HASH` and audit finding R9.
    """

    # We discard the result — the contract is "burn the same
    # number of bcrypt rounds we would have if the user existed".
    pwd_context.verify(plain_password, _DUMMY_BCRYPT_HASH)


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def check_account_lockout(email: str, redis_client) -> None:
    key = f"login_failures:{email}"
    failures = await redis_client.get(key)
    if failures and int(failures) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
        )


async def record_failed_login(email: str, redis_client) -> None:
    key = f"login_failures:{email}"
    await redis_client.incr(key)
    await redis_client.expire(key, 900)


async def clear_failed_logins(email: str, redis_client) -> None:
    key = f"login_failures:{email}"
    await redis_client.delete(key)
