"""Unit tests for the loader's discovery + single-dir validation steps.

Both modules are pure (no DB), so we exercise them under the unit
suite without spinning the testcontainers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.challenge_loader import ArtifactMismatch, discover, load_directory
from bluerange_spec import ManifestNotFound, ManifestValidationError


def _write_minimum_manifest(directory: Path, slug: str = "loader-test-001") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "manifest.yaml"
    manifest.write_text(
        f"""\
spec_version: "1"
slug: {slug}
title: Loader Test
description: A small manifest used in loader unit tests.
team: blue
category: test
difficulty: 1
points: 100
license: MIT
author:
  name: Test
container:
  image: siege/loader-test
  port: 8080
flags:
  - id: f1
    type: exact
    value: "CTF{REDACTED}}"
    points: 100
""",
        encoding="utf-8",
    )
    return manifest


def test_discover_finds_each_dir_once(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write_minimum_manifest(a, "loader-test-a")
    _write_minimum_manifest(b, "loader-test-b")
    results = list(discover([tmp_path]))
    dirs = sorted(r.directory for r in results)
    assert dirs == [a, b]


def test_discover_skips_dirs_without_manifest(tmp_path: Path) -> None:
    (tmp_path / "no-manifest").mkdir()
    _write_minimum_manifest(tmp_path / "ok", "loader-test-ok")
    results = list(discover([tmp_path]))
    assert {r.directory.name for r in results} == {"ok"}


def test_discover_handles_root_pointing_at_single_challenge(tmp_path: Path) -> None:
    one = tmp_path / "one"
    _write_minimum_manifest(one, "loader-test-one")
    results = list(discover([one]))
    assert [r.directory for r in results] == [one]


def test_discover_dedupes_overlapping_roots(tmp_path: Path) -> None:
    one = tmp_path / "one"
    _write_minimum_manifest(one, "loader-test-dup")
    results = list(discover([tmp_path, one]))
    # ``one`` is reachable from tmp_path's listing AND directly via the
    # second root entry; we should only see it once.
    assert len(results) == 1


def test_load_directory_happy_path(tmp_path: Path) -> None:
    _write_minimum_manifest(tmp_path, "loader-test-happy")
    loaded = load_directory(tmp_path)
    assert loaded.manifest.slug == "loader-test-happy"
    assert len(loaded.manifest_digest) == 64


def test_load_directory_no_manifest(tmp_path: Path) -> None:
    with pytest.raises(ManifestNotFound):
        load_directory(tmp_path)


def test_load_directory_validation_error(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(
        "spec_version: '1'\nslug: bad\n", encoding="utf-8"
    )
    with pytest.raises(ManifestValidationError):
        load_directory(tmp_path)


def test_load_directory_artifact_mismatch_when_file_missing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """\
spec_version: "1"
slug: loader-test-art
title: Test
description: Test artefact mismatch path.
team: blue
category: test
difficulty: 1
points: 100
license: MIT
author:
  name: Test
container:
  image: siege/loader-test
  port: 8080
flags:
  - id: f1
    type: exact
    value: "CTF{REDACTED}"
    points: 100
artifacts:
  - path: "artifacts/missing.bin"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
""",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactMismatch) as excinfo:
        load_directory(tmp_path)
    assert excinfo.value.actual == "<missing>"


def test_load_directory_artifact_sha_mismatch(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "data.bin").write_bytes(b"hello world")
    (tmp_path / "manifest.yaml").write_text(
        """\
spec_version: "1"
slug: loader-test-shas
title: Test
description: Test artefact mismatch path.
team: blue
category: test
difficulty: 1
points: 100
license: MIT
author:
  name: Test
container:
  image: siege/loader-test
  port: 8080
flags:
  - id: f1
    type: exact
    value: "CTF{REDACTED}"
    points: 100
artifacts:
  - path: "artifacts/data.bin"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
""",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactMismatch) as excinfo:
        load_directory(tmp_path)
    assert excinfo.value.actual != "<missing>"
    assert excinfo.value.actual != excinfo.value.expected
