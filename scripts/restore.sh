#!/usr/bin/env bash
#
# Siege Range CTF - Restore Script
# Restores a backup tarball created by backup.sh.
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

# ── Validate arguments ──────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo -e "${BOLD}Usage:${RESET} $0 <backup-tarball.tar.gz>"
    echo ""
    echo "  Restores a Siege Range backup created by backup.sh."
    echo ""
    echo "  Examples:"
    echo "    $0 ./backups/siege-backup-20260310-120000.tar.gz"
    echo ""
    exit 1
fi

TARBALL="$1"

if [ ! -f "${TARBALL}" ]; then
    error "Backup file not found: ${TARBALL}"
    exit 1
fi

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORK_DIR="$(mktemp -d)"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-siege-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-siege-redis}"
POSTGRES_USER="${POSTGRES_USER:-siege}"
POSTGRES_DB="${POSTGRES_DB:-siege_range}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"

# Cleanup on exit
cleanup() {
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

# ── Main ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}=== Siege Range CTF - Restore ===${RESET}\n"

info "Tarball: ${BOLD}${TARBALL}${RESET}"

# ── Confirmation ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}${BOLD}WARNING: This will overwrite the current database and Redis data.${RESET}"
read -rp "Continue? [y/N] " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    info "Restore cancelled"
    exit 0
fi

# ── Extract tarball ──────────────────────────────────────────────────────────
info "Extracting backup ..."
tar -xzf "${TARBALL}" -C "${WORK_DIR}"

# Find the extracted directory (the first directory inside WORK_DIR)
EXTRACTED_DIR="$(find "${WORK_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n1)"

if [ -z "${EXTRACTED_DIR}" ]; then
    error "No directory found in tarball"
    exit 1
fi

ok "Extracted to ${EXTRACTED_DIR}"

# Show backup metadata if available
if [ -f "${EXTRACTED_DIR}/backup-meta.json" ]; then
    info "Backup metadata:"
    cat "${EXTRACTED_DIR}/backup-meta.json" | while IFS= read -r line; do
        echo -e "    ${line}"
    done
fi

# ── Restore PostgreSQL ───────────────────────────────────────────────────────
PGDUMP="${EXTRACTED_DIR}/postgres.sql"

if [ -f "${PGDUMP}" ]; then
    info "Restoring PostgreSQL database '${POSTGRES_DB}' ..."

    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running"
        exit 1
    fi

    if docker exec -i "${POSTGRES_CONTAINER}" \
        psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
            --single-transaction --quiet \
        < "${PGDUMP}" 2>/dev/null; then
        ok "PostgreSQL restore complete"
    else
        error "PostgreSQL restore failed"
        exit 1
    fi
else
    warn "No postgres.sql found in backup -- skipping PostgreSQL restore"
fi

# ── Restore Redis ────────────────────────────────────────────────────────────
RDUMP="${EXTRACTED_DIR}/redis-dump.rdb"

if [ -f "${RDUMP}" ]; then
    info "Restoring Redis data ..."

    if ! docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        warn "Redis container '${REDIS_CONTAINER}' is not running -- skipping Redis restore"
    else
        # Stop Redis, copy the dump, restart
        info "Stopping Redis to replace dump file ..."
        docker exec "${REDIS_CONTAINER}" redis-cli SHUTDOWN NOSAVE 2>/dev/null || true
        sleep 2

        docker cp "${RDUMP}" "${REDIS_CONTAINER}:/data/dump.rdb" 2>/dev/null || true
        ok "Redis dump file copied"
    fi
else
    warn "No redis-dump.rdb found in backup -- skipping Redis restore"
fi

# ── Restart services ─────────────────────────────────────────────────────────
info "Restarting services ..."

if [ -n "${COMPOSE_PROJECT}" ]; then
    COMPOSE_ARGS="-p ${COMPOSE_PROJECT}"
else
    COMPOSE_ARGS=""
fi

# Try docker compose (v2) first, fall back to docker-compose (v1)
if command -v docker compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD=""
fi

if [ -n "${COMPOSE_CMD}" ]; then
    COMPOSE_FILE=""
    for candidate in "${PROJECT_ROOT}/docker-compose.yml" \
                     "${PROJECT_ROOT}/docker-compose.yaml" \
                     "${PROJECT_ROOT}/compose.yml" \
                     "${PROJECT_ROOT}/compose.yaml"; do
        if [ -f "${candidate}" ]; then
            COMPOSE_FILE="${candidate}"
            break
        fi
    done

    if [ -n "${COMPOSE_FILE}" ]; then
        ${COMPOSE_CMD} ${COMPOSE_ARGS} -f "${COMPOSE_FILE}" restart 2>/dev/null && \
            ok "Services restarted via docker compose" || \
            warn "docker compose restart returned non-zero"
    else
        warn "No compose file found -- restarting containers individually"
        docker restart "${POSTGRES_CONTAINER}" 2>/dev/null || true
        docker restart "${REDIS_CONTAINER}" 2>/dev/null || true
        ok "Containers restarted"
    fi
else
    warn "docker compose not found -- restarting containers individually"
    docker restart "${POSTGRES_CONTAINER}" 2>/dev/null || true
    docker restart "${REDIS_CONTAINER}" 2>/dev/null || true
    ok "Containers restarted"
fi

# Wait for services to be ready
info "Waiting for services to become healthy ..."
sleep 5

# Verify PostgreSQL is accepting connections
RETRIES=10
for i in $(seq 1 $RETRIES); do
    if docker exec "${POSTGRES_CONTAINER}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" &>/dev/null; then
        ok "PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        warn "PostgreSQL did not become ready after ${RETRIES} attempts"
    fi
    sleep 2
done

# Verify Redis is accepting connections
if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    for i in $(seq 1 $RETRIES); do
        if docker exec "${REDIS_CONTAINER}" redis-cli PING 2>/dev/null | grep -q PONG; then
            ok "Redis is ready"
            break
        fi
        if [ "$i" -eq "$RETRIES" ]; then
            warn "Redis did not become ready after ${RETRIES} attempts"
        fi
        sleep 2
    done
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${GREEN}=== Restore Complete ===${RESET}"
echo -e "  Source: ${TARBALL}"
echo ""
