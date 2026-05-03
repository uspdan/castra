"""Hash-chained audit ledger (Phase 2).

Public surface:
    from app.services.audit import append, EventType, ActorType, AuditError

The legacy ``audit_logs`` table and its writers are unrelated and are not
re-exported from here.
"""

from app.services.audit.events import ActorType, EventType, AuditError
from app.services.audit.ledger import append

__all__ = ["append", "EventType", "ActorType", "AuditError"]
