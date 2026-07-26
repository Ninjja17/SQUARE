"""Session middleware — issues anonymous session IDs via HTTP-only cookies."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings

settings = get_settings()
_SESSION_COOKIE = "sq_session"


def _create_session_token(session_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": session_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_session_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(_SESSION_COOKIE)
        session_id = None
        if token:
            session_id = decode_session_token(token)

        new_session = False
        if not session_id:
            session_id = secrets.token_urlsafe(24)
            new_session = True

        request.state.session_id = session_id
        response: Response = await call_next(request)

        if new_session:
            response.set_cookie(
                key=_SESSION_COOKIE,
                value=_create_session_token(session_id),
                httponly=True,
                samesite="lax",
                max_age=settings.SESSION_EXPIRE_HOURS * 3600,
            )
        return response
