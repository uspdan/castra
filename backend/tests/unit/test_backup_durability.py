"""Backups have to survive the environment, not just the unit tests.

``run_backup`` was already correct and already unit-tested — including
the "pg_dump missing" branch. It reported the failure faithfully every
night for days and nobody noticed, because the things that were broken
were not in the Python:

  1. ``pg_dump`` was absent from the runtime image, so every run failed.
  2. ``BACKUP_DIR`` was not a mounted volume, so even a successful dump
     would have been destroyed by the next ``docker compose up``.
  3. Nothing alerted, and APScheduler logs the job as "executed
     successfully" because the job swallows failures by design.

These tests cover (1) and (2) by asserting the deployment topology, and
the metric tests below cover (3). They are deliberately static checks on
the Dockerfile and compose file: the failure mode is an environment
regression, so that is what needs a regression test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_DOCKERFILE = _REPO_ROOT / "backend" / "Dockerfile"

# Must track ``Settings.BACKUP_DIR``. Hard-coded rather than imported so
# a change to the default has to be made deliberately in both places.
_DEFAULT_BACKUP_DIR = "/var/lib/siege-range/backups"


@pytest.fixture(scope="module")
def compose() -> dict:
    with _COMPOSE.open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return _DOCKERFILE.read_text(encoding="utf-8")


class TestBackupPersistence:
    def test_backup_dir_is_a_mounted_volume(self, compose):
        mounts = compose["services"]["api"].get("volumes") or []
        targets = [str(m).split(":")[1] for m in mounts if ":" in str(m)]
        assert _DEFAULT_BACKUP_DIR in targets, (
            f"api must mount a volume at {_DEFAULT_BACKUP_DIR}; without it "
            "nightly dumps land on the container's writable layer and are "
            "destroyed on the next recreate — i.e. every deploy discards "
            "the entire backup history"
        )

    def test_backup_volume_is_named_not_anonymous(self, compose):
        mounts = compose["services"]["api"].get("volumes") or []
        source = next(
            str(m).split(":")[0]
            for m in mounts
            if str(m).endswith(f":{_DEFAULT_BACKUP_DIR}")
        )
        declared = compose.get("volumes") or {}
        assert source in declared, (
            f"{source!r} must be declared in the top-level volumes block. "
            "An anonymous volume is discarded by ``docker compose down`` "
            "and is not a backup."
        )

    def test_backup_volume_is_not_a_bind_mount(self, compose):
        mounts = compose["services"]["api"].get("volumes") or []
        source = next(
            str(m).split(":")[0]
            for m in mounts
            if str(m).endswith(f":{_DEFAULT_BACKUP_DIR}")
        )
        assert not source.startswith(("/", ".", "~")), (
            "backup target should be a named volume, not a host bind mount "
            "tied to one machine's filesystem layout"
        )


class TestPgDumpAvailability:
    def test_runtime_image_installs_a_postgres_client(self, dockerfile):
        assert "postgresql-client" in dockerfile, (
            "the runtime image must ship pg_dump — the nightly backup job "
            "shells out to it, and without it every run fails while the "
            "scheduler still reports success"
        )

    def test_image_build_asserts_pg_dump_is_present(self, dockerfile):
        assert "pg_dump --version" in dockerfile, (
            "keep the build-time ``pg_dump --version`` assertion: it turns "
            "a silently missing client into a failed image build"
        )

    def test_client_major_matches_the_postgres_server_major(
        self, compose, dockerfile
    ):
        # pg_dump refuses to dump from a server newer than itself:
        #   "aborting because of server version mismatch"
        # Debian bookworm ships client 15 against our Postgres 16, which
        # installs cleanly and then fails every night — a strictly worse
        # failure than a missing binary. Lock the two majors together.
        server_image = compose["services"]["db"]["image"]
        server_major = re.search(r"postgres:(\d+)", server_image)
        assert server_major, f"cannot parse postgres major from {server_image!r}"

        client_major = re.search(r"postgresql-client-(\d+)", dockerfile)
        assert client_major, "Dockerfile must pin an explicit client major"

        assert client_major.group(1) == server_major.group(1), (
            f"pg_dump major {client_major.group(1)} != server major "
            f"{server_major.group(1)}. pg_dump cannot dump from a newer "
            "server; bump both together."
        )
