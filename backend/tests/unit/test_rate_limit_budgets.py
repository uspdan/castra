"""Rate-limit budget gates (audit findings R5 / R7).

The per-IP auth limiter is the control that closed R5 (unlimited
login attempts) and R7 (password-reset mail bombing). Its budget is
configurable so a dev/CI stack can drive an E2E suite from a single
runner IP — which makes the *configuration* part of the control's
attack surface.

Two properties are locked here:

1. **The budget can only be relaxed in development/test.** Staging is
   capped alongside production on purpose: a preprod box carrying real
   credentials is exactly where an "it's only staging" exemption gets
   exploited.
2. **There is no header that switches the limiter off.** An earlier
   iteration shipped an ``X-RateLimit-Bypass`` header keyed on a shared
   secret; the regression test below asserts no such short-circuit
   comes back, because a header that disables the limiter is a
   brute-force key the moment the token leaks.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings


# Baseline kwargs that satisfy every unrelated production validator
# (SECRET_KEY / ADMIN_PASSWORD placeholders, CORS, SMTP), so the only
# thing a given test can trip is the rate-limit ceiling.
_PROD_BASE = {
    "SECRET_KEY": "prod-secret-not-a-placeholder-0123456789abcdef0123",
    "ADMIN_PASSWORD": "ProdAdminPasswordA1!",
    "ALLOWED_ORIGINS": "https://siege.example.com",
    "SMTP_HOST": "smtp.example.com",
    "MAIL_FROM": "noreply@siege.example.com",
    "FRONTEND_URL": "https://siege.example.com",
}


def _settings(app_env: str, **overrides) -> Settings:
    kwargs = dict(_PROD_BASE)
    kwargs["APP_ENV"] = app_env
    kwargs.update(overrides)
    return Settings(**kwargs)


class TestShippedDefaults:
    """The audited numbers are what you get when nobody tunes."""

    def test_defaults_match_the_audited_budgets(self):
        s = _settings("production")
        assert s.RATE_LIMIT_AUTH_PER_MIN == 5
        assert s.RATE_LIMIT_AUTH_BURST_PER_5MIN == 5
        assert s.RATE_LIMIT_FLAG_PER_MIN == 10
        assert s.RATE_LIMIT_GENERAL_PER_MIN == 100

    def test_zero_and_negative_budgets_are_rejected(self):
        # A budget of 0 would 429 every request; a negative one is
        # nonsense. ``ge=1`` should catch both before boot.
        with pytest.raises(ValidationError):
            _settings("development", RATE_LIMIT_AUTH_PER_MIN=0)
        with pytest.raises(ValidationError):
            _settings("development", RATE_LIMIT_AUTH_PER_MIN=-1)


class TestCeilingEnforcement:
    """Only development/test may raise a budget."""

    @pytest.mark.parametrize("app_env", ["production", "staging"])
    @pytest.mark.parametrize(
        "field,over_ceiling",
        [
            ("RATE_LIMIT_AUTH_PER_MIN", 500),
            ("RATE_LIMIT_AUTH_BURST_PER_5MIN", 500),
            ("RATE_LIMIT_FLAG_PER_MIN", 500),
            ("RATE_LIMIT_GENERAL_PER_MIN", 2000),
        ],
    )
    def test_should_refuse_to_boot_when_budget_exceeds_ceiling(
        self, app_env, field, over_ceiling
    ):
        with pytest.raises(ValidationError) as exc:
            _settings(app_env, **{field: over_ceiling})
        assert field in str(exc.value)

    def test_staging_is_capped_not_exempt(self):
        # Regression for the original defect shape: the first version of
        # this guard keyed on ``APP_ENV == "production"`` only, so a
        # staging deploy silently ran with no effective auth limiter.
        with pytest.raises(ValidationError):
            _settings("staging", RATE_LIMIT_AUTH_PER_MIN=500)

    @pytest.mark.parametrize("app_env", ["development", "test"])
    def test_dev_and_test_may_raise_budgets(self, app_env):
        s = _settings(app_env, RATE_LIMIT_AUTH_PER_MIN=500)
        assert s.RATE_LIMIT_AUTH_PER_MIN == 500

    def test_value_exactly_at_ceiling_is_permitted(self):
        s = _settings("production", RATE_LIMIT_AUTH_PER_MIN=20)
        assert s.RATE_LIMIT_AUTH_PER_MIN == 20

    def test_one_over_ceiling_is_refused(self):
        with pytest.raises(ValidationError):
            _settings("production", RATE_LIMIT_AUTH_PER_MIN=21)


class _FakeRedis:
    """Minimal stand-in for the async redis client the limiter uses.

    ``zcard_result`` is what the pipeline reports as the current
    request count, which is what drives the 429 decision.
    """

    def __init__(self, zcard_result: int):
        self._zcard_result = zcard_result
        self.pipeline_used = False
        self.closed = False

    def pipeline(self):
        self.pipeline_used = True
        pipe = MagicMock()
        pipe.zremrangebyscore = AsyncMock()
        pipe.zadd = AsyncMock()
        pipe.zcard = AsyncMock()
        pipe.expire = AsyncMock()
        pipe.execute = AsyncMock(
            return_value=[0, 1, self._zcard_result, True]
        )
        return pipe

    async def close(self):
        self.closed = True


def _request(headers: Optional[dict] = None):
    """A stub good enough for ``client_ip`` + header inspection."""
    req = MagicMock()
    req.headers = headers or {}
    req.client = MagicMock()
    req.client.host = "203.0.113.9"
    req.state = MagicMock(spec=[])  # no user_id attribute
    return req


class TestNoBypassHeader:
    """No request header may short-circuit the limiter."""

    @pytest.fixture
    def fake_redis(self, monkeypatch):
        from app.middleware import rate_limit as rl

        redis = _FakeRedis(zcard_result=999)  # far past any budget
        monkeypatch.setattr(rl, "_get_redis", AsyncMock(return_value=redis))
        return redis

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"x-ratelimit-bypass": "dev-e2e-bypass"},
            {"X-RateLimit-Bypass": "dev-e2e-bypass"},
            {"x-ratelimit-bypass": ""},
        ],
    )
    async def test_should_429_regardless_of_bypass_header(
        self, fake_redis, headers
    ):
        from app.middleware.rate_limit import auth_rate_limit

        with pytest.raises(HTTPException) as exc:
            await auth_rate_limit(_request(headers))
        assert exc.value.status_code == 429
        assert fake_redis.pipeline_used, (
            "limiter must consult redis on every call — a header that "
            "skips the check is a brute-force key (see module docstring)"
        )

    async def test_source_has_no_bypass_token_reference(self):
        # Belt-and-braces: the mechanism should not exist in the module
        # at all, not merely be unreachable.
        from pathlib import Path

        import app.middleware.rate_limit as rl

        source = Path(rl.__file__).read_text()
        assert "BYPASS" not in source.upper(), (
            "rate_limit.py must not carry a bypass mechanism"
        )


class TestBudgetIsHonoured:
    """The limiter uses the configured budget, not a hard-coded one."""

    @pytest.fixture
    def under_budget_redis(self, monkeypatch):
        from app.middleware import rate_limit as rl

        redis = _FakeRedis(zcard_result=7)
        monkeypatch.setattr(rl, "_get_redis", AsyncMock(return_value=redis))
        return redis

    async def test_request_within_configured_budget_passes(
        self, under_budget_redis, monkeypatch
    ):
        # 7 requests seen, budget 10 → allowed.
        from app.middleware import rate_limit as rl

        monkeypatch.setattr(
            rl, "get_settings", lambda: _settings("test", RATE_LIMIT_AUTH_PER_MIN=10)
        )
        await rl.auth_rate_limit(_request())

    async def test_same_count_over_a_smaller_budget_is_refused(
        self, under_budget_redis, monkeypatch
    ):
        # Same 7 requests, budget 5 → 429. Proves the number in
        # settings is what the decision reads.
        from app.middleware import rate_limit as rl

        monkeypatch.setattr(
            rl, "get_settings", lambda: _settings("test", RATE_LIMIT_AUTH_PER_MIN=5)
        )
        with pytest.raises(HTTPException) as exc:
            await rl.auth_rate_limit(_request())
        assert exc.value.status_code == 429
        assert exc.value.headers["X-RateLimit-Limit"] == "5"
