"""Loader-specific errors."""

from __future__ import annotations

from dataclasses import dataclass


class LoaderError(Exception):
    """Base class for loader-only errors.

    Manifest parse / validation failures bubble up as the
    ``ManifestParseError`` / ``ManifestValidationError`` types from
    :mod:`bluerange_spec`; callers should catch both of those plus
    ``LoaderError`` to enumerate every failure mode the loader can
    raise.
    """


@dataclass
class ArtifactMismatch(LoaderError):
    """Raised when an artifact's on-disk SHA-256 does not match the manifest."""

    path: str
    expected: str
    actual: str

    def __str__(self) -> str:  # pragma: no cover — string-format only
        return (
            f"artifact {self.path!r}: manifest sha256={self.expected}, "
            f"on-disk sha256={self.actual}"
        )


@dataclass
class UnknownProfile(LoaderError):
    """Manifest references a profile not in the platform's PROFILES registry."""

    profile: str
    known: tuple[str, ...]

    def __str__(self) -> str:  # pragma: no cover — string-format only
        return (
            f"unknown container profile {self.profile!r}; "
            f"known profiles: {', '.join(self.known)}"
        )
