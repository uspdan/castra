#!/usr/bin/env bash
# scripts/bootstrap-standards.sh
#
# Initializes the engineering standards + memory system in a project.
# Run once when setting up a new project or retrofitting an existing one.
#
# Usage: ./scripts/bootstrap-standards.sh [standards-repo-path]
#
# If standards-repo-path is provided (local path), files are copied from there.
# Otherwise, skeleton files are created from embedded templates.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STANDARDS_SOURCE="${1:-}"
DATE=$(date +%Y-%m-%d)

echo "=== Engineering Standards Bootstrap ==="
echo "Project root: ${PROJECT_ROOT}"
echo ""

# --- Helper ---
create_if_missing() {
  local filepath="$1"
  local description="$2"
  if [[ -f "${filepath}" ]]; then
    echo "[SKIP] ${filepath} already exists"
    return 1
  else
    echo "[CREATE] ${filepath} — ${description}"
    return 0
  fi
}

# --- 1. Directory structure ---
echo "--- Setting up directories ---"
mkdir -p "${PROJECT_ROOT}/.memory-backups"
mkdir -p "${PROJECT_ROOT}/docs/adr"
mkdir -p "${PROJECT_ROOT}/docs/runbooks"
mkdir -p "${PROJECT_ROOT}/docs/memory-archive"
mkdir -p "${PROJECT_ROOT}/scripts"

# --- 2. .gitignore additions ---
echo "--- Checking .gitignore ---"
GITIGNORE="${PROJECT_ROOT}/.gitignore"
touch "${GITIGNORE}"

declare -a IGNORE_ENTRIES=(
  ".memory-backups/"
  ".env"
  ".env.local"
  ".env.*.local"
)

for entry in "${IGNORE_ENTRIES[@]}"; do
  if ! grep -qxF "${entry}" "${GITIGNORE}" 2>/dev/null; then
    echo "${entry}" >> "${GITIGNORE}"
    echo "[ADD] ${entry} → .gitignore"
  fi
done

# --- 3. CLAUDE.md (universal standards) ---
if [[ -n "${STANDARDS_SOURCE}" && -f "${STANDARDS_SOURCE}/CLAUDE.md" ]]; then
  cp "${STANDARDS_SOURCE}/CLAUDE.md" "${PROJECT_ROOT}/CLAUDE.md"
  echo "[COPY] CLAUDE.md from ${STANDARDS_SOURCE}"
elif create_if_missing "${PROJECT_ROOT}/CLAUDE.md" "Universal engineering standards"; then
  echo "# CLAUDE.md — placeholder" > "${PROJECT_ROOT}/CLAUDE.md"
  echo "" >> "${PROJECT_ROOT}/CLAUDE.md"
  echo "> Pull the canonical version: run ./scripts/sync-standards.sh" >> "${PROJECT_ROOT}/CLAUDE.md"
  echo "[WARN] CLAUDE.md created as placeholder — sync from standards repo to populate"
fi

# --- 4. LEARNINGS.md (cross-project learnings) ---
if [[ -n "${STANDARDS_SOURCE}" && -f "${STANDARDS_SOURCE}/LEARNINGS.md" ]]; then
  cp "${STANDARDS_SOURCE}/LEARNINGS.md" "${PROJECT_ROOT}/LEARNINGS.md"
  echo "[COPY] LEARNINGS.md from ${STANDARDS_SOURCE}"
elif create_if_missing "${PROJECT_ROOT}/LEARNINGS.md" "Cross-project learnings"; then
  cat > "${PROJECT_ROOT}/LEARNINGS.md" << 'LEARNINGS_EOF'
# LEARNINGS.md — Cross-Project Engineering Learnings

> Synced from the central standards repo. Do not edit directly in project repos.
> Promote learnings from CLAUDE.memory.md via the agent workflow.

---

## UNIVERSAL GOTCHAS

_No entries yet. Learnings are promoted here from project memory files._

---

## UNIVERSAL PATTERNS

_No entries yet._

---

## DEPENDENCY ADVISORIES

_No entries yet._

---

## ANTI-PATTERNS

_No entries yet._
LEARNINGS_EOF
fi

# --- 5. CLAUDE.agent.md (agent prompt) ---
if [[ -n "${STANDARDS_SOURCE}" && -f "${STANDARDS_SOURCE}/CLAUDE.agent.md" ]]; then
  cp "${STANDARDS_SOURCE}/CLAUDE.agent.md" "${PROJECT_ROOT}/CLAUDE.agent.md"
  echo "[COPY] CLAUDE.agent.md from ${STANDARDS_SOURCE}"
elif create_if_missing "${PROJECT_ROOT}/CLAUDE.agent.md" "Standards agent prompt"; then
  echo "[WARN] CLAUDE.agent.md not found in standards source — copy manually"
fi

# --- 6. CLAUDE.memory.md (project memory) ---
if create_if_missing "${PROJECT_ROOT}/CLAUDE.memory.md" "Project memory"; then
  cat > "${PROJECT_ROOT}/CLAUDE.memory.md" << MEMORY_EOF
# CLAUDE.memory.md — Project Memory: $(basename "${PROJECT_ROOT}")

> Project-specific learnings, patterns, gotchas, and decisions.
> Claude Code reads this automatically. Entries are append-only.
>
> **Initialized**: ${DATE}

---

## PATTERNS — What works in this project

_No entries yet._

---

## GOTCHAS — What has bitten us

_No entries yet._

---

## DECISIONS — Why we chose X over Y

_No entries yet._

---

## DEBT — Known shortcuts and their remediation plan

_No entries yet._

---

## PERFORMANCE — Benchmarks and capacity observations

_No entries yet._

---

## DEPENDENCIES — External dependency notes

_No entries yet._

---

## ENVIRONMENT — Infrastructure and deployment notes

_No entries yet._

---

## ROLLBACK LOG — What we rolled back and why

_No entries yet._
MEMORY_EOF
fi

# --- 7. Sync script ---
if create_if_missing "${PROJECT_ROOT}/scripts/sync-standards.sh" "Standards sync script"; then
  cat > "${PROJECT_ROOT}/scripts/sync-standards.sh" << 'SYNC_EOF'
#!/usr/bin/env bash
# Syncs CLAUDE.md and LEARNINGS.md from the central standards repo.
# Usage: ./scripts/sync-standards.sh [branch]
#
# Set STANDARDS_REPO_URL to the raw base URL of your standards repo.
# For local repos, set STANDARDS_REDACTED_PATH instead.

set -euo pipefail

BRANCH="${1:-main}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sync_file() {
  local filename="$1"
  local target="${PROJECT_ROOT}/${filename}"

  if [[ -n "${STANDARDS_REDACTED_PATH:-}" ]]; then
    # Local copy mode
    local source="${STANDARDS_REDACTED_PATH}/${filename}"
    if [[ -f "${source}" ]]; then
      cp "${source}" "${target}.new"
    else
      echo "[SKIP] ${filename} not found in ${STANDARDS_REDACTED_PATH}"
      return
    fi
  elif [[ -n "${STANDARDS_REPO_URL:-}" ]]; then
    # Remote fetch mode
    curl -fsSL "${STANDARDS_REPO_URL}/${BRANCH}/${filename}" -o "${target}.new" 2>/dev/null || {
      echo "[SKIP] ${filename} not available from remote"
      return
    }
  else
    echo "[ERROR] Set STANDARDS_REPO_URL or STANDARDS_REDACTED_PATH"
    exit 1
  fi

  if [[ -f "${target}" ]] && diff -q "${target}" "${target}.new" > /dev/null 2>&1; then
    rm "${target}.new"
    echo "[OK] ${filename} is up to date"
  else
    mv "${target}.new" "${target}"
    echo "[UPDATED] ${filename}"
  fi
}

echo "=== Syncing Engineering Standards ==="
sync_file "CLAUDE.md"
sync_file "LEARNINGS.md"
sync_file "CLAUDE.agent.md"
echo "=== Done ==="
SYNC_EOF
  chmod +x "${PROJECT_ROOT}/scripts/sync-standards.sh"
fi

# --- 8. ADR template ---
if create_if_missing "${PROJECT_ROOT}/docs/adr/000-template.md" "ADR template"; then
  cat > "${PROJECT_ROOT}/docs/adr/000-template.md" << 'ADR_EOF'
# ADR-NNN: Title

## Status
Proposed | Accepted | Superseded by ADR-NNN

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?

## References
- Related MEM entries: MEM-NNNN
- Related PRs: #NN
ADR_EOF
fi

# --- Summary ---
echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Files in project root (all auto-read by Claude Code):"
echo "  CLAUDE.md          — Universal standards"
echo "  CLAUDE.agent.md    — Agent enforcement prompt"
echo "  CLAUDE.memory.md   — Project memory (append-only)"
echo "  CLAUDE.local.md    — Project overrides (create when needed)"
echo "  LEARNINGS.md       — Cross-project learnings"
echo ""
echo "Next steps:"
echo "  1. Review CLAUDE.md and CLAUDE.agent.md"
echo "  2. Set STANDARDS_REPO_URL or STANDARDS_REDACTED_PATH in your env"
echo "  3. Add './scripts/sync-standards.sh' to your CI install step"
echo "  4. Start working — the agent captures learnings automatically"
echo ""
