"""Locked DTOs for the public API v1 contract.

Phase 12 (slice 1) deliverable: every response model under
``/api/v1/`` is a pydantic ``BaseModel`` with
``ConfigDict(extra="forbid")`` so internal columns can never leak by
accident, and every field has an explicit type so the OpenAPI schema
is the contract clients depend on.

These models intentionally diverge from the dict shapes returned by
the legacy routers — those still serve the existing frontend until
Phase 12 (slice 2) wires the front-door over to v1. Stability is the
v1 promise; the legacy shapes can drift, the v1 ones cannot.
"""

from .auth import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthRefreshResponse,
    AuthRegisterRequest,
    AuthTokenPairResponse,
    AuthUser,
)
from .challenges import (
    PublicChallengeDetail,
    PublicChallengeListItem,
    PublicChallengeListResponse,
    PublicChallengePrerequisite,
    PublicHint,
    PublicTopSolver,
)
from .coverage import AttackCoverageEntry, AttackCoverageResponse
from .hints import HintUnlockResponse
from .leaderboard import (
    TeamLeaderboardEntry,
    TeamLeaderboardResponse,
    WeeklyLeaderboardEntry,
    WeeklyLeaderboardResponse,
)
from .me import MeResponse
from .progress import ChallengeProgressResponse, FlagProgressEntry
from .scoreboard import ScoreboardEntry, ScoreboardResponse
from .submission import SubmitFlagRequest, SubmitFlagResponse

__all__ = [
    "AttackCoverageEntry",
    "AuthLoginRequest",
    "AuthLogoutRequest",
    "AuthLogoutResponse",
    "AuthRefreshRequest",
    "AuthRefreshResponse",
    "AuthRegisterRequest",
    "AuthTokenPairResponse",
    "AuthUser",
    "AttackCoverageResponse",
    "ChallengeProgressResponse",
    "FlagProgressEntry",
    "HintUnlockResponse",
    "MeResponse",
    "PublicChallengeDetail",
    "PublicChallengeListItem",
    "PublicChallengeListResponse",
    "PublicChallengePrerequisite",
    "PublicHint",
    "PublicTopSolver",
    "ScoreboardEntry",
    "ScoreboardResponse",
    "TeamLeaderboardEntry",
    "TeamLeaderboardResponse",
    "WeeklyLeaderboardEntry",
    "WeeklyLeaderboardResponse",
    "SubmitFlagRequest",
    "SubmitFlagResponse",
]
