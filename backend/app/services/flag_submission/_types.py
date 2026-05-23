"""Submission-domain errors + result dataclass."""

from __future__ import annotations

from dataclasses import dataclass


class SubmissionError(Exception):
    """Base for submission-domain errors. Routers map these to 4xx."""


class ChallengeNotFound(SubmissionError):
    """No active, released challenge with the given slug."""


class AlreadySolved(SubmissionError):
    """The user has already solved this challenge."""


class PrerequisitesNotMet(SubmissionError):
    """The user has not solved one or more prerequisite challenges.

    Carries the list of missing prerequisite slugs so the API
    layer can surface them to the client (the UI renders a "you
    need: …" hint instead of the generic 412 message).
    """

    def __init__(self, missing_slugs: tuple[str, ...] = ()):
        super().__init__()
        self.missing_slugs: tuple[str, ...] = tuple(missing_slugs)


@dataclass(frozen=True)
class SubmissionResult:
    correct: bool
    points_awarded: int | None = None
    is_first_blood: bool | None = None
    flag_id: str | None = None


__all__ = [
    "AlreadySolved",
    "ChallengeNotFound",
    "PrerequisitesNotMet",
    "SubmissionError",
    "SubmissionResult",
]
