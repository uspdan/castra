"""Unit tests for :mod:`app.services.flag_dispatch`.

Exercises both the v1 (per-flag rows) and legacy (flag_hash column)
paths without touching the DB — :class:`Challenge` and
:class:`ChallengeFlag` instances are constructed in-memory.
"""

from __future__ import annotations

from app.models import Challenge, ChallengeFlag, TeamType
from app.services.flag_dispatch import dispatch_submission
from app.validators.exact import hash_exact_value


def _bare_challenge(slug: str = "c1") -> Challenge:
    return Challenge(
        slug=slug,
        title="t",
        description="d",
        category="web",
        team=TeamType.red,
        difficulty=1,
        points=100,
        docker_image="alpine:3.19",
        docker_port=80,
    )


class TestLegacyPath:
    async def test_correct_submission_via_flag_hash(self):
        c = _bare_challenge()
        c.flag_hash = hash_exact_value("CTF{REDACTED}")
        c.flag_definitions = []
        result = await dispatch_submission("CTF{REDACTED}", c)
        assert result.correct is True
        assert result.flag_id == "legacy"
        assert result.validator_name == "exact"

    async def test_wrong_submission_returns_false(self):
        c = _bare_challenge()
        c.flag_hash = hash_exact_value("expected-value")
        c.flag_definitions = []
        result = await dispatch_submission("some-other-thing", c)
        assert result.correct is False
        assert result.flag_id is None

    async def test_no_flag_hash_returns_false(self):
        c = _bare_challenge()
        c.flag_hash = None
        c.flag_definitions = []
        result = await dispatch_submission("anything", c)
        assert result.correct is False


class TestV1Path:
    async def test_exact_flag_matches(self):
        c = _bare_challenge()
        flag = ChallengeFlag(
            flag_id="primary",
            flag_type="exact",
            points=100,
            value_hash=hash_exact_value("CTF{REDACTED}"),
            config={"case_sensitive": True},
        )
        c.flag_definitions = [flag]
        c.flag_hash = None
        result = await dispatch_submission("CTF{REDACTED}", c)
        assert result.correct is True
        assert result.flag_id == "primary"

    async def test_regex_flag_matches(self):
        c = _bare_challenge()
        flag = ChallengeFlag(
            flag_id="r1",
            flag_type="regex",
            points=100,
            config={"pattern": r"FLAG\{[a-z]+\}", "case_sensitive": True},
        )
        c.flag_definitions = [flag]
        c.flag_hash = None
        result = await dispatch_submission("FLAG{matched}", c)
        assert result.correct is True
        assert result.flag_id == "r1"

    async def test_multi_part_flag_matches(self):
        c = _bare_challenge()
        flag = ChallengeFlag(
            flag_id="m1",
            flag_type="multi_part",
            points=100,
            config={"parts": ["alpha", "bravo"], "ordered": True},
        )
        c.flag_definitions = [flag]
        c.flag_hash = None
        result = await dispatch_submission("alpha||bravo", c)
        assert result.correct is True

    async def test_first_matching_flag_wins(self):
        # Two flags configured; submission matches the second.
        c = _bare_challenge()
        first = ChallengeFlag(
            flag_id="f1",
            flag_type="exact",
            points=50,
            value_hash=hash_exact_value("first-expected"),
            config={"case_sensitive": True},
        )
        second = ChallengeFlag(
            flag_id="f2",
            flag_type="exact",
            points=50,
            value_hash=hash_exact_value("second-expected"),
            config={"case_sensitive": True},
        )
        c.flag_definitions = [first, second]
        c.flag_hash = None
        result = await dispatch_submission("second-expected", c)
        assert result.correct is True
        assert result.flag_id == "f2"

    async def test_unknown_validator_skipped_not_500(self):
        # If an admin loads a manifest with a flag_type the platform
        # doesn't have a plugin for, we shouldn't 500 the submit
        # endpoint — we should skip and let other flags be tried.
        c = _bare_challenge()
        bogus = ChallengeFlag(
            flag_id="b1",
            flag_type="this_plugin_does_not_exist",
            points=50,
            config={},
        )
        good = ChallengeFlag(
            flag_id="g1",
            flag_type="exact",
            points=50,
            value_hash=hash_exact_value("CTF{REDACTED}"),
            config={"case_sensitive": True},
        )
        c.flag_definitions = [bogus, good]
        c.flag_hash = None
        result = await dispatch_submission("CTF{REDACTED}", c)
        assert result.correct is True
        assert result.flag_id == "g1"
