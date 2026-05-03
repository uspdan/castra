"""Application configuration.

Loaded once at startup via ``get_settings()`` (cached). Validation runs
inside ``Settings.__init__`` — any violation surfaces as a Pydantic
``ValidationError`` and is converted by ``main.py`` into a structured
JSON message on stderr followed by ``sys.exit(1)``. **No silent
fallbacks for security-critical values.**
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings


# Values that have ever shipped as placeholder defaults in this repo, or
# that are obvious "please replace me" strings. Any startup that resolves
# SECRET_KEY or ADMIN_PASSWORD to one of these is rejected.
_PLACEHOLDER_VALUES = frozenset(
    {
        "change-me-in-production-use-a-random-64-char-string",
        "change-me",
        "changeme",
        "placeholder",
        "please-change-me",
        "Admin123!@#",
        "admin",
        "password",
        "password123",
        "Passw0rd!",
        "TODO_REPLACE",
        "secret",
    }
)


AppEnv = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    APP_ENV: AppEnv = "development"

    DATABASE_URL: str = "postgresql+asyncpg://siege:siege_secret@db:5432/siege_range"
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT signing key. 64+ hex chars recommended. No default.",
    )
    ADMIN_EMAIL: str = "admin@siege.local"
    ADMIN_PASSWORD: str = Field(
        ...,
        min_length=12,
        description="Bootstrap admin password. No default.",
    )

    # CORS: comma-separated explicit origins. Empty in production is an
    # error (rejected in ``_check_cors_for_env``); empty in dev falls
    # back to local Vite/React ports.
    ALLOWED_ORIGINS: str = ""

    DOCKER_HOST: str = "tcp://orchestrator:2376"
    REDIS_URL: str = "redis://redis:6379/0"
    CONTAINER_TIMEOUT: int = 7200
    # Phase 12 (slice 9) — SLACK_WEBHOOK_URL / TEAMS_WEBHOOK_URL
    # removed. Operators now configure outbound webhooks via the v1
    # admin surface (`POST /api/v1/webhooks`); see slice-5/6/7 notes.
    # Phase 12 (slice 17) — path the egress-proxy reads its allowlist
    # from. The launcher renders the union of every active
    # ``egress-proxied`` instance's FQDN list here on each launch /
    # teardown, then SIGHUPs the proxy. Operators who don't share a
    # volume with the proxy should leave this at the default and
    # accept that the signal step harmlessly fails until they bind a
    # writable shared mount.
    EGRESS_FILTER_PATH: Optional[str] = None
    SCORING_MODE: str = "static"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("SECRET_KEY", "ADMIN_PASSWORD")
    @classmethod
    def _reject_placeholders(cls, v: str, info) -> str:
        if v in _PLACEHOLDER_VALUES:
            raise ValueError(
                f"{info.field_name} is set to a known placeholder value. "
                "Generate a real secret (see .env.example) before booting."
            )
        return v

    @model_validator(mode="after")
    def _check_cors_for_env(self) -> "Settings":
        if self.APP_ENV == "production" and not self.ALLOWED_ORIGINS.strip():
            raise ValueError(
                "ALLOWED_ORIGINS must be set explicitly when APP_ENV=production"
            )
        return self

    def allowed_origins_list(self) -> List[str]:
        """Parsed CORS origin list. Dev falls back to local Vite/React ports."""

        raw = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if raw:
            return raw
        if self.APP_ENV == "development":
            return ["http://localhost:3000", "http://localhost:5173"]
        return []

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


def _emit_fatal_and_exit(exc: ValidationError) -> None:
    sys.stderr.write(
        json.dumps(
            {
                "level": "fatal",
                "event": "config.invalid",
                "errors": [
                    {
                        "field": ".".join(str(p) for p in err.get("loc", ())),
                        "msg": err.get("msg"),
                        "type": err.get("type"),
                    }
                    for err in exc.errors()
                ],
                "hint": (
                    "Set required values in .env (see .env.example). "
                    "SECRET_KEY and ADMIN_PASSWORD must be real secrets."
                ),
            }
        )
        + "\n"
    )
    sys.exit(1)


@lru_cache()
def _build_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Cached settings entrypoint with structured fail-fast on errors.

    Tests that need to inspect ``ValidationError`` should construct
    ``Settings()`` directly; this entrypoint is the boot path and
    converts any error into a single JSON line on stderr followed by
    ``sys.exit(1)``.
    """

    try:
        return _build_settings()
    except ValidationError as exc:  # pragma: no cover — exercised at boot only
        _emit_fatal_and_exit(exc)
        raise  # unreachable, satisfies type-checkers
