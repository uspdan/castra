"""Pure (no DB) validation of a single challenge directory.

``load_directory`` is the unit the loader composes over: it parses the
manifest, hashes the canonical form, and verifies that every declared
artifact's on-disk SHA-256 matches the manifest. It does **not**
touch the database — :mod:`.upsert` does that.

Phase 9 additions:
    * Manifest profile name must be in
      :data:`app.services.orchestration.profiles.PROFILES`.
      Unknown profile → :class:`.errors.UnknownProfile` (load failure).
    * Missing ``container.digest`` is permitted at load time but a
      warning is attached to the result so the CLI can surface it.
      The launcher refuses to start an instance whose digest is null.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from bluerange_spec import (
    ChallengeManifest,
    load_manifest,
    manifest_sha256,
    sha256_file,
)

from app.services.orchestration import profiles as orchestration_profiles

from .errors import ArtifactMismatch, UnknownProfile


@dataclass(frozen=True)
class LoadedManifest:
    """Result of loading + verifying a challenge directory.

    ``raw`` is the manifest as parsed (pre-Pydantic) so callers can
    persist it verbatim or compute a hash without re-serialising
    through the model. ``warnings`` carries non-fatal complaints the
    loader wants surfaced (e.g. missing container digest).
    """

    directory: Path
    manifest: ChallengeManifest
    raw: Dict[str, Any]
    manifest_digest: str
    warnings: List[str] = field(default_factory=list)


def load_directory(directory: Path | str) -> LoadedManifest:
    """Parse, validate, and integrity-check a challenge directory.

    Raises :class:`bluerange_spec.ManifestNotFound`,
    :class:`bluerange_spec.ManifestParseError`,
    :class:`bluerange_spec.ManifestValidationError`,
    :class:`ArtifactMismatch`, or :class:`UnknownProfile` on failure.
    """

    directory = Path(directory)
    manifest, raw = load_manifest(directory)
    digest = manifest_sha256(raw)
    _validate_profile_known(manifest)
    _verify_artifacts(directory, manifest)
    warnings = _collect_warnings(manifest)
    return LoadedManifest(
        directory=directory,
        manifest=manifest,
        raw=raw,
        manifest_digest=digest,
        warnings=warnings,
    )


def _validate_profile_known(manifest: ChallengeManifest) -> None:
    name = manifest.container.profile
    if name not in orchestration_profiles.PROFILES:
        raise UnknownProfile(
            profile=name,
            known=orchestration_profiles.names(),
        )


def _verify_artifacts(directory: Path, manifest: ChallengeManifest) -> None:
    for artifact in manifest.artifacts:
        path = directory / artifact.path
        if not path.is_file():
            raise ArtifactMismatch(
                path=artifact.path,
                expected=artifact.sha256,
                actual="<missing>",
            )
        actual = sha256_file(path)
        if actual != artifact.sha256:
            raise ArtifactMismatch(
                path=artifact.path,
                expected=artifact.sha256,
                actual=actual,
            )


def _collect_warnings(manifest: ChallengeManifest) -> List[str]:
    warnings: List[str] = []
    if not manifest.container.digest:
        warnings.append(
            "container.digest is not set; this challenge will not be "
            "launchable until the digest is added (Phase 9 refuses to "
            "start un-pinned images)."
        )
    return warnings
