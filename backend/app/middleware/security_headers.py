"""Response-time security headers middleware (Phase 3).

Headers applied to every response:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: minimal allowlist (camera/microphone/geolocation off)
    - Strict-Transport-Security: prod-only (1y, includeSubDomains)
    - Content-Security-Policy: locked down — no wildcards, no unsafe-eval

CSP is deliberately *not* applied to the OpenAPI/Swagger surfaces
(``/docs``, ``/redoc``, ``/openapi.json``): both Swagger UI and ReDoc
load assets from a CDN and require inline scripts. Locking those down
is a Phase 12 problem (we'll self-host the Swagger bundle and tighten
this exception then).
"""

from __future__ import annotations

from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


_DOC_PATHS: frozenset[str] = frozenset({"/docs", "/redoc", "/openapi.json"})


_PERMISSIONS_POLICY: str = ", ".join(
    f"{feature}=()"
    for feature in (
        "camera",
        "microphone",
        "geolocation",
        "payment",
        "usb",
        "interest-cohort",
    )
)


_CSP_REPORT_PATH = "/csp-report"


def _build_csp(
    connect_src_extra: Iterable[str] = (),
    *,
    include_report_uri: bool = True,
) -> str:
    """Strict CSP suitable for a Vite-built React SPA.

    - script-src 'self': Vite production builds emit hashed assets, no
      inline scripts. We do **not** allow ``unsafe-eval`` or ``unsafe-inline``.
    - style-src 'self' 'unsafe-inline': Tailwind/React inline style
      attributes are unavoidable in the current build; tracked for
      Phase 12 review.
    - connect-src 'self': API + websocket on the same origin (nginx
      fronts both). Extra entries (e.g. wss://...) can be added by the
      caller if a future deploy splits the origin.

    Sprint 12 Phase B — when ``include_report_uri`` is set, browsers
    POST CSP violations to ``/csp-report`` so we can audit-log them.
    """

    connect_src = " ".join(["'self'", *connect_src_extra]).strip()
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        f"connect-src {connect_src}",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
    if include_report_uri:
        # ``report-uri`` is the legacy directive (still honoured by
        # every browser); ``report-to`` requires a separate
        # Reporting-Endpoints header which isn't worth the extra
        # plumbing today.
        directives.append(f"report-uri {_CSP_REPORT_PATH}")
    return "; ".join(directives)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, is_production: bool) -> None:
        super().__init__(app)
        self._is_production = is_production
        self._csp = _build_csp()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        if self._is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        if request.url.path not in _DOC_PATHS:
            response.headers.setdefault("Content-Security-Policy", self._csp)

        return response
