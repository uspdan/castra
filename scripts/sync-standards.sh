#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STANDARDS_REDACTED_PATH="${STANDARDS_REDACTED_PATH:?Set STANDARDS_REDACTED_PATH env var}"

for filename in CLAUDE.md CLAUDE.agent.md LEARNINGS.md; do
  source="${STANDARDS_REDACTED_PATH}/${filename}"
  target="${PROJECT_ROOT}/${filename}"

  if [[ ! -f "${source}" ]]; then
    echo "[SKIP] ${filename} not found in standards repo"
    continue
  fi

  if [[ -f "${target}" ]] && diff -q "${target}" "${source}" > /dev/null 2>&1; then
    echo "[OK] ${filename} is up to date"
  else
    cp "${source}" "${target}"
    echo "[UPDATED] ${filename}"
  fi
done
