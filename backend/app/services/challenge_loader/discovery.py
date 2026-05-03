"""Walk one or more roots and yield candidate challenge directories.

A candidate is any directory containing a ``manifest.yaml``,
``manifest.yml``, or ``manifest.json`` at its top level. Roots may
point at a single challenge directory or at a parent that contains
many.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List


_MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "manifest.json")


@dataclass(frozen=True)
class DiscoveryResult:
    directory: Path
    manifest_path: Path


def discover(roots: Iterable[Path | str]) -> Iterator[DiscoveryResult]:
    """Yield :class:`DiscoveryResult` for each manifest found under any root.

    Roots that do not exist are silently skipped — callers control
    whether that's an error. Each directory is yielded at most once,
    even if reachable through multiple roots.
    """

    seen: set[Path] = set()
    for root in roots:
        for result in _scan_root(Path(root)):
            resolved = result.directory.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield result


def _scan_root(root: Path) -> List[DiscoveryResult]:
    if not root.exists():
        return []
    found: List[DiscoveryResult] = []
    if root.is_dir() and _has_manifest(root):
        found.append(_build(root))
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir() and _has_manifest(child):
                found.append(_build(child))
    return found


def _has_manifest(directory: Path) -> bool:
    return any((directory / name).is_file() for name in _MANIFEST_NAMES)


def _build(directory: Path) -> DiscoveryResult:
    for name in _MANIFEST_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return DiscoveryResult(directory=directory, manifest_path=candidate)
    raise AssertionError(f"discover() invariant violated for {directory}")
