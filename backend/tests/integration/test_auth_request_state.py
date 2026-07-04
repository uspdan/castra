"""Integration: ``get_current_user`` must publish the authenticated user
id onto ``request.state`` so downstream per-user rate limiting keys on the
user rather than silently collapsing to client IP.
"""

from __future__ import annotations

from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.services.auth import get_current_user


def _bare_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/challenges/x/submit",
            "query_string": b"",
            "headers": [],
            "client": ("10.0.0.5", 5000),
        }
    )


async def test_get_current_user_sets_request_state_user_id(
    db_session, user_factory, auth_token
) -> None:
    user = await user_factory()
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=auth_token(user)
    )
    request = _bare_request()

    resolved = await get_current_user(request, creds, db_session)

    assert resolved.id == user.id
    assert request.state.user_id == user.id
