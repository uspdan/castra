"""Loader helpers for reading manifest files from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from pydantic import ValidationError

from .manifest import ChallengeManifest


_MANIFEST_FILES = ("manifest.yaml", "manifest.yml", "manifest.json")


class LoadError(Exception):
    """Base class for manifest load errors."""


class ManifestNotFound(LoadError):
    """No manifest file under the candidate names exists."""


class ManifestParseError(LoadError):
    """Manifest exists but is not parseable as YAML/JSON."""


class ManifestValidationError(LoadError):
    """Manifest parses but fails Pydantic validation."""

    def __init__(self, message: str, errors: list) -> None:
        super().__init__(message)
        self.errors = errors


def load_manifest(directory: Path | str) -> Tuple[ChallengeManifest, Dict[str, Any]]:
    """Load and validate a manifest from a challenge directory.

    Returns ``(manifest, raw_dict)``. ``raw_dict`` is the parsed-but-
    unvalidated payload, kept so callers can hash the canonical form
    independently of the Pydantic round-trip.
    """

    directory = Path(directory)
    path = _resolve_manifest_path(directory)
    text = path.read_text(encoding="utf-8")
    return load_manifest_text(text, source_hint=str(path))


def load_manifest_text(
    text: str, source_hint: str | None = None
) -> Tuple[ChallengeManifest, Dict[str, Any]]:
    """Parse and validate manifest content from a string."""

    raw = _parse_text(text, source_hint)
    return _validate(raw, source_hint), raw


def _resolve_manifest_path(directory: Path) -> Path:
    if not directory.is_dir():
        raise ManifestNotFound(f"not a directory: {directory}")
    for name in _MANIFEST_FILES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise ManifestNotFound(
        f"no manifest found in {directory} (expected one of {_MANIFEST_FILES})"
    )


def _parse_text(text: str, source_hint: str | None) -> Dict[str, Any]:
    stripped = text.lstrip()
    is_json = stripped.startswith("{")
    try:
        if is_json:
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        where = f" ({source_hint})" if source_hint else ""
        raise ManifestParseError(f"manifest is not valid YAML/JSON{where}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestParseError("manifest top level must be a mapping")
    return data


def _validate(raw: Dict[str, Any], source_hint: str | None) -> ChallengeManifest:
    try:
        return ChallengeManifest.model_validate(raw)
    except ValidationError as exc:
        where = f" ({source_hint})" if source_hint else ""
        raise ManifestValidationError(
            f"manifest failed validation{where}",
            errors=exc.errors(include_url=False),
        ) from exc
