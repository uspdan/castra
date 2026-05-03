"""Challenge loader: walks paths, validates manifests, upserts to DB.

Public surface:

- :func:`discover` — yields candidate challenge directories.
- :func:`load_directory` — pure (no DB) validation of a single dir.
- :func:`upsert_manifest` — applies a validated manifest to the DB.
- :func:`run` — orchestration entry-point used by the CLI.

Each helper is small enough to test in isolation and is composed by
the CLI in :mod:`app.tools.load_challenges`.
"""

from .discovery import DiscoveryResult, discover
from .errors import ArtifactMismatch, LoaderError
from .pipeline import LoadOutcome, LoadReport, LoadStatus, run
from .single import LoadedManifest, load_directory
from .upsert import upsert_manifest

__all__ = [
    "ArtifactMismatch",
    "DiscoveryResult",
    "LoadOutcome",
    "LoadReport",
    "LoadStatus",
    "LoadedManifest",
    "LoaderError",
    "discover",
    "load_directory",
    "run",
    "upsert_manifest",
]
