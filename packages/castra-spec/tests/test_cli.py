"""The ``castra`` CLI — the standalone author loop.

These run the real commands in-process (``main(argv)``), covering the
loop the docs promise: new → validate → test. The claim under test is
that this works with no backend installed — which CI approximates by
the package suite running before anything imports ``app.*``, and the
extraction guarantees structurally (castra_spec has no ``app`` imports;
``test_no_app_imports`` pins that).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from castra_spec.cli import main


@pytest.fixture
def scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["new", "demo"]) == 0
    manifest = tmp_path / "demo" / "manifest.yaml"
    # Make the scaffold a real, passing challenge.
    manifest.write_text(
        manifest.read_text().replace("TODO-real-flag", "demo-flag")
    )
    return tmp_path / "demo"


class TestNew:
    def test_scaffold_validates_out_of_the_box(self, scaffold):
        # The scaffold must be a *working* example, not a broken
        # template — an author's first contact with the tool should
        # not be an error message.
        assert main(["validate", str(scaffold)]) == 0

    def test_refuses_to_clobber_a_nonempty_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "exists"
        target.mkdir()
        (target / "keep.txt").write_text("do not delete")
        assert main(["new", str(target)]) == 2
        assert (target / "keep.txt").read_text() == "do not delete"

    def test_scaffold_artifact_sha_is_real(self, scaffold):
        import hashlib

        text = (scaffold / "manifest.yaml").read_text()
        declared = re.search(r'sha256: "([0-9a-f]{64})"', text).group(1)
        actual = hashlib.sha256(
            (scaffold / "artifacts" / "evidence.log").read_bytes()
        ).hexdigest()
        assert declared == actual


class TestValidate:
    def test_invalid_manifest_exits_1(self, scaffold):
        manifest = scaffold / "manifest.yaml"
        manifest.write_text(
            manifest.read_text().replace('team: blue', 'team: chartreuse')
        )
        assert main(["validate", str(scaffold)]) == 1


class TestTest:
    def test_scaffold_tests_pass(self, scaffold):
        assert main(["test", str(scaffold)]) == 0

    def test_failing_case_exits_1(self, scaffold):
        manifest = scaffold / "manifest.yaml"
        # Flip the expected outcome of the passing case → harness must
        # report a failure and the CLI must propagate exit 1. Replace
        # the bare line rather than a multi-line block: the scaffold's
        # indentation is an implementation detail, and an unmatched
        # multi-line replace() silently changes nothing — which made
        # the first version of this test pass vacuously.
        text = manifest.read_text()
        assert text.count("expected: pass") == 1
        manifest.write_text(text.replace("expected: pass", "expected: fail", 1))
        assert main(["test", str(scaffold)]) == 1


class TestStandaloneGuarantee:
    def test_no_app_imports_anywhere_in_the_sdk(self):
        # The extraction's structural invariant: the SDK must never
        # import the platform. One backend import sneaking in makes
        # ``pip install castra-spec`` drag FastAPI or fail outright.
        import castra_spec

        root = Path(castra_spec.__file__).parent
        offenders = []
        for py in root.rglob("*.py"):
            for i, line in enumerate(py.read_text().splitlines(), 1):
                if re.match(r"^\s*(from|import)\s+app[.\s]", line):
                    offenders.append(f"{py.relative_to(root)}:{i}: {line.strip()}")
        assert not offenders, "\n".join(offenders)

    def test_cli_fallback_env_is_setdefault_not_override(self, monkeypatch, tmp_path):
        # An author who explicitly disabled the re fallback keeps their
        # setting; the CLI must not stomp it.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SIEGE_ALLOW_RE_FALLBACK", "0")
        main(["new", "envcheck"])
        assert os.environ["SIEGE_ALLOW_RE_FALLBACK"] == "0"
