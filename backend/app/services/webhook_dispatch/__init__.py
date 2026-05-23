"""``app.services.webhook_dispatch`` public façade.

Decomposed into submodules (R25 audit finding) — each ≤300 lines:

* ``_common``   — sign/secret helpers, HTTP client mgmt, attempt loop.
* ``delivery``  — ``deliver_event`` + subscription-matching helper.
* ``replay``    — ``replay_delivery`` (manual re-dispatch).
* ``retry``     — scheduled retry sweep with backoff.
* ``retention`` — ``prune_old_deliveries``.

External callers keep their existing
``from app.services.webhook_dispatch import X`` imports unchanged.
"""

from ._common import (
    _AttemptOutcome,
    _attempt_one,
    _canonical_body,
    _default_http_client,
    _get_shared_client,
    _new_http_client,
    aclose_shared_client,
    generate_subscription_secret,
    sign_body,
)
# Re-export ``assert_url_safe`` at the package level so existing
# tests can monkeypatch it via
# ``app.services.webhook_dispatch.assert_url_safe`` without having
# to know which submodule holds the import. Patching here propagates
# to ``_common`` (which is the only caller).
from app.services.webhook_ssrf import assert_url_safe  # noqa: F401
from .delivery import deliver_event
from .replay import replay_delivery
from .retention import prune_old_deliveries
from .retry import (
    _is_retriable,
    _next_retry_due_at,
    retry_failed_deliveries,
)


__all__ = [
    "aclose_shared_client",
    "deliver_event",
    "generate_subscription_secret",
    "prune_old_deliveries",
    "replay_delivery",
    "retry_failed_deliveries",
    "sign_body",
]
