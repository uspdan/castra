#!/usr/bin/env bash
#
# Siege Range CTF - Backup Script
# Creates a timestamped backup of PostgreSQL and Redis data.
#
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="siege-backup-${TIMESTAMP}"
WORK_DIR="${BACKUP_DIR}/${BACKUP_NAME}"
TARBALL="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
RETENTION_DAYS=30

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-siege-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-siege-redis}"
POSTGRES_USER="${POSTGRES_USER:-siege}"
POSTGRES_DB="${POSTGRES_DB:-siege_range}"

# ── Main ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}=== Siege Range CTF - Backup ===${RESET}\n"

# Create backup directories
mkdir -p "${WORK_DIR}"
info "Backup directory: ${BOLD}${WORK_DIR}${RESET}"

# ── PostgreSQL Dump ──────────────────────────────────────────────────────────
info "Dumping PostgreSQL database '${POSTGRES_DB}' ..."

if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running"
    exit 1
fi

if docker exec "${POSTGRES_CONTAINER}" \
    pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        --no-owner --no-acl --clean --if-exists \
    > "${WORK_DIR}/postgres.sql" 2>/dev/null; then
    DUMP_SIZE=$(du -h "${WORK_DIR}/postgres.sql" | cut -f1)
    ok "PostgreSQL dump complete (${DUMP_SIZE})"
else
    error "PostgreSQL dump failed"
    rm -rf "${WORK_DIR}"
    exit 1
fi

# ── Redis Export ─────────────────────────────────────────────────────────────
info "Exporting Redis data ..."

if ! docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    warn "Redis container '${REDIS_CONTAINER}' is not running -- skipping Redis backup"
else
    # Trigger a background save and wait for it to finish
    docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE > /dev/null 2>&1 || true
    sleep 2

    # Copy the RDB dump file from the container
    if docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${WORK_DIR}/redis-dump.rdb" 2>/dev/null; then
        RDB_SIZE=$(du -h "${WORK_DIR}/redis-dump.rdb" | cut -f1)
        ok "Redis dump complete (${RDB_SIZE})"
    else
        warn "Could not copy Redis dump file -- the container may use a different data path"
    fi
fi

# ── Create metadata ─────────────────────────────────────────────────────────
cat > "${WORK_DIR}/backup-meta.json" <<METAEOF
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$(hostname)",
  "postgres_db": "${POSTGRES_DB}",
  "postgres_container": "${POSTGRES_CONTAINER}",
  "redis_container": "${REDIS_CONTAINER}"
}
METAEOF

# ── Create tarball ───────────────────────────────────────────────────────────
info "Creating tarball ..."

tar -czf "${TARBALL}" -C "${BACKUP_DIR}" "${BACKUP_NAME}"
TARBALL_SIZE=$(du -h "${TARBALL}" | cut -f1)
ok "Tarball created: ${BOLD}${TARBALL}${RESET} (${TARBALL_SIZE})"

# Clean up working directory
rm -rf "${WORK_DIR}"

# ── Prune old backups ────────────────────────────────────────────────────────
info "Pruning backups older than ${RETENTION_DAYS} days ..."

PRUNED=0
while IFS= read -r old_backup; do
    rm -f "${old_backup}"
    info "  Removed $(basename "${old_backup}")"
    PRUNED=$((PRUNED + 1))
done < <(find "${BACKUP_DIR}" -name "siege-backup-*.tar.gz" -mtime "+${RETENTION_DAYS}" -type f 2>/dev/null)

if [ "${PRUNED}" -eq 0 ]; then
    info "No old backups to prune"
else
    ok "Pruned ${PRUNED} old backup(s)"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${GREEN}=== Backup Complete ===${RESET}"
echo -e "  File: ${TARBALL}"
echo -e "  Size: ${TARBALL_SIZE}"
echo ""
