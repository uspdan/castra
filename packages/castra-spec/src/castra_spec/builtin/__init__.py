"""Baseline validators shipped with the SDK.

These are the red-team fundamentals every standalone author needs:
``exact``, ``regex`` and ``multi_part``. They moved here from the
platform so ``pip install castra-spec`` + ``castra test`` works with
no backend installed. The blue-team validators (sigma, yara,
chain-of-custody, attack-chain, cloud-misconfig, llm-signal) stay
platform-side — they carry heavy dependencies (pysigma, yara-python)
that an authoring laptop should not be forced to install.

Registered under the ``castra.validators`` entry-point group by
this package's pyproject; the platform must NOT register the same
names — the registry treats duplicates as an error by design.
"""
