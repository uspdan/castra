"""``app.models`` public façade.

The package shape lets each domain live in its own ≤200-line file
(R25 audit finding) while preserving the single-import surface
every caller relies on: ``from app.models import User, Challenge,
Solve, ...``.

Submodule layout:

* ``_base``        — ``Base``, enums, ``utcnow``.
* ``user``         — ``User``, ``Streak``, password-reset and
                     email-verification tokens, MFA recovery codes.
* ``challenge``    — ``Challenge`` + its associated rows:
                     ``ChallengeFlag``, ``ChallengeArtifact``,
                     ``ChallengeFeedback``, ``ChallengeInstance``,
                     ``HintUnlock``.
* ``activity``     — ``Solve``, ``SolvedFlag``, ``Writeup``,
                     ``LearningPath``.
* ``audit``        — ``AuditLedger`` (append-only hash chain).
* ``competition``  — ``Competition``.
* ``notification`` — ``Notification``.
* ``webhook``      — ``WebhookSubscription``, ``WebhookDelivery``.

Importing this package triggers the import of every submodule so
SQLAlchemy's metadata sees every table; downstream callers can
keep doing ``from app.models import X``.
"""

from app.models._base import (
    Base,
    InstanceStatus,
    TeamType,
    UserRole,
    utcnow,
)
from app.models.activity import (
    LearningPath,
    Solve,
    SolvedFlag,
    Writeup,
)
from app.models.audit import AuditLedger
from app.models.challenge import (
    Challenge,
    ChallengeArtifact,
    ChallengeFeedback,
    ChallengeFlag,
    ChallengeInstance,
    HintUnlock,
)
from app.models.competition import Competition
from app.models.notification import Notification
from app.models.user import (
    EmailVerificationToken,
    MfaRecoveryCode,
    PasswordResetToken,
    Streak,
    User,
)
from app.models.webhook import WebhookDelivery, WebhookSubscription


__all__ = [
    "AuditLedger",
    "Base",
    "Challenge",
    "ChallengeArtifact",
    "ChallengeFeedback",
    "ChallengeFlag",
    "ChallengeInstance",
    "Competition",
    "EmailVerificationToken",
    "HintUnlock",
    "InstanceStatus",
    "LearningPath",
    "MfaRecoveryCode",
    "Notification",
    "PasswordResetToken",
    "Solve",
    "SolvedFlag",
    "Streak",
    "TeamType",
    "User",
    "UserRole",
    "WebhookDelivery",
    "WebhookSubscription",
    "Writeup",
    "utcnow",
]
