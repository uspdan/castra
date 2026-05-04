"""Outbound email sender.

Sprint 6. Used by the password-reset flow today; will host
verification + future transactional emails. Three modes:

- **Production** (``SMTP_HOST`` set, ``APP_ENV=production``):
  delivers via ``aiosmtplib`` against the configured SMTP server.
  Uses STARTTLS by default; SMTP credentials read from
  ``SMTP_USER`` / ``SMTP_PASSWORD``.

- **Development** (``SMTP_HOST`` unset OR
  ``APP_ENV=development``): logs the message to stderr as a
  structured JSON line. Operators can recover the reset link
  from logs without configuring SMTP. Loud and obvious.

- **Test** (``APP_ENV=test``): captures the message into the
  module-level ``CAPTURED_EMAILS`` list so integration tests can
  assert delivery without a real SMTP. Tests that care call
  :func:`reset_captured_emails` between cases.

Failures are best-effort in dev/test; in production a delivery
failure raises so the caller can audit-emit and surface a 500
back to the client (the password-reset endpoint maps
``EmailDeliveryError`` to a generic 503).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import List

import structlog

from app.config import get_settings


logger = structlog.get_logger()


class EmailDeliveryError(RuntimeError):
    """Raised when production-mode delivery fails."""


@dataclass
class CapturedEmail:
    to: str
    subject: str
    body_text: str


# Test-mode capture buffer. Cleared explicitly via
# ``reset_captured_emails`` from test setup; not cleared between
# function calls so the same test can assert on multiple sends.
CAPTURED_EMAILS: List[CapturedEmail] = []


def reset_captured_emails() -> None:
    CAPTURED_EMAILS.clear()


async def send_email(
    *,
    to: str,
    subject: str,
    body_text: str,
) -> None:
    """Dispatch a single plaintext email.

    See module docstring for mode semantics.
    """

    settings = get_settings()

    if settings.APP_ENV == "test":
        CAPTURED_EMAILS.append(
            CapturedEmail(to=to, subject=subject, body_text=body_text)
        )
        return

    if not settings.SMTP_HOST:
        # Dev fallback. Print one structured JSON line on stderr so
        # the caller's log-shipper picks it up unchanged.
        sys.stderr.write(
            json.dumps(
                {
                    "level": "info",
                    "event": "email.dev_fallback",
                    "to": to,
                    "subject": subject,
                    "body_text": body_text,
                }
            )
            + "\n"
        )
        sys.stderr.flush()
        return

    # Production path.
    try:
        import aiosmtplib
    except ImportError as exc:  # pragma: no cover — checked at install time
        raise EmailDeliveryError(
            "aiosmtplib is not installed; required for SMTP delivery"
        ) from exc

    if not settings.MAIL_FROM:
        raise EmailDeliveryError("MAIL_FROM is not configured")

    message = (
        f"From: {settings.MAIL_FROM}\r\n"
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body_text}\r\n"
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )
    except Exception as exc:  # noqa: BLE001 — wrap as domain error
        logger.error(
            "email.delivery_failed",
            to=to,
            subject=subject,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise EmailDeliveryError(str(exc)) from exc


__all__ = [
    "CapturedEmail",
    "CAPTURED_EMAILS",
    "EmailDeliveryError",
    "reset_captured_emails",
    "send_email",
]
