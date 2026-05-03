#!/usr/bin/env bash
#
# Siege Range CTF - Health Check
# Verifies that all platform services are running and healthy.
#
set -uo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
BOLD='\033[1m'
RESET='\033[0m'

PASS="${GREEN}PASS${RESET}"
FAIL="${RED}FAIL${RESET}"
WARN="${YELLOW}WARN${RESET}"

# ── Configuration ────────────────────────────────────────────────────────────
API_URL="${API_URL:-http://localhost:3000}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/health}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-siege-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-siege-redis}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-siege-backend}"
FRONTEND_CONTAINER="${FRONTEND_CONTAINER:-siege-frontend}"
NGINX_CONTAINER="${NGINX_CONTAINER:-siege-nginx}"
POSTGRES_USER="${POSTGRES_USER:-siege}"
POSTGRES_DB="${POSTGRES_DB:-siege_range}"

CHECKS_TOTAL=0
CHECKS_PASSED=0
CHECKS_FAILED=0

check_pass() {
    echo -e "  [${PASS}] $*"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

check_fail() {
    echo -e "  [${FAIL}] $*"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

check_warn() {
    echo -e "  [${WARN}] $*"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
}

# ── Main ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}=== Siege Range CTF - Health Check ===${RESET}\n"

# ── 1. Container Status ─────────────────────────────────────────────────────
echo -e "${BOLD}Container Status${RESET}"

for CONTAINER in "${POSTGRES_CONTAINER}" "${REDIS_CONTAINER}" "${BACKEND_CONTAINER}" "${FRONTEND_CONTAINER}" "${NGINX_CONTAINER}"; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "${CONTAINER}" 2>/dev/null || echo "not_found")
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${CONTAINER}" 2>/dev/null || echo "unknown")

    if [ "${STATUS}" = "running" ]; then
        if [ "${HEALTH}" = "healthy" ] || [ "${HEALTH}" = "no-healthcheck" ]; then
            check_pass "${CONTAINER}: running (health: ${HEALTH})"
        else
            check_warn "${CONTAINER}: running but health=${HEALTH}"
        fi
    elif [ "${STATUS}" = "not_found" ]; then
        check_fail "${CONTAINER}: container not found"
    else
        check_fail "${CONTAINER}: ${STATUS}"
    fi
done

echo ""

# ── 2. HTTP Health Endpoint ──────────────────────────────────────────────────
echo -e "${BOLD}HTTP Health Endpoint${RESET}"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 \
    "${API_URL}${HEALTH_ENDPOINT}" 2>/dev/null || echo "000")

if [ "${HTTP_CODE}" = "200" ]; then
    check_pass "GET ${HEALTH_ENDPOINT} returned HTTP 200"

    # Try to parse response body for details
    BODY=$(curl -s --connect-timeout 5 --max-time 10 "${API_URL}${HEALTH_ENDPOINT}" 2>/dev/null || echo "")
    if [ -n "${BODY}" ]; then
        echo -e "         Response: ${BODY}" | head -c 500
        echo ""
    fi
elif [ "${HTTP_CODE}" = "000" ]; then
    check_fail "GET ${HEALTH_ENDPOINT} -- connection refused or timed out"
else
    check_fail "GET ${HEALTH_ENDPOINT} returned HTTP ${HTTP_CODE}"
fi

echo ""

# ── 3. PostgreSQL Connectivity ───────────────────────────────────────────────
echo -e "${BOLD}PostgreSQL${RESET}"

if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    # pg_isready check
    if docker exec "${POSTGRES_CONTAINER}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" &>/dev/null; then
        check_pass "pg_isready: accepting connections"
    else
        check_fail "pg_isready: not accepting connections"
    fi

    # Basic query test
    RESULT=$(docker exec "${POSTGRES_CONTAINER}" \
        psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT 1;" 2>/dev/null | tr -d '[:space:]')
    if [ "${RESULT}" = "1" ]; then
        check_pass "Query test: SELECT 1 returned successfully"
    else
        check_fail "Query test: unable to execute SELECT 1"
    fi

    # Check table count
    TABLE_COUNT=$(docker exec "${POSTGRES_CONTAINER}" \
        psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
        2>/dev/null | tr -d '[:space:]')
    if [ -n "${TABLE_COUNT}" ] && [ "${TABLE_COUNT}" -gt 0 ] 2>/dev/null; then
        check_pass "Schema: ${TABLE_COUNT} public table(s) found"
    else
        check_warn "Schema: no public tables found (database may need migration)"
    fi
else
    check_fail "PostgreSQL container '${POSTGRES_CONTAINER}' is not running"
fi

echo ""

# ── 4. Redis Connectivity ───────────────────────────────────────────────────
echo -e "${BOLD}Redis${RESET}"

if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    # PING test
    PONG=$(docker exec "${REDIS_CONTAINER}" redis-cli PING 2>/dev/null || echo "")
    if [ "${PONG}" = "PONG" ]; then
        check_pass "PING: Redis responded with PONG"
    else
        check_fail "PING: Redis did not respond"
    fi

    # Info check
    REDIS_VERSION=$(docker exec "${REDIS_CONTAINER}" redis-cli INFO server 2>/dev/null | grep "redis_version:" | cut -d: -f2 | tr -d '[:space:]')
    if [ -n "${REDIS_VERSION}" ]; then
        check_pass "Version: Redis ${REDIS_VERSION}"
    fi

    # Memory usage
    REDIS_MEM=$(docker exec "${REDIS_CONTAINER}" redis-cli INFO memory 2>/dev/null | grep "used_memory_human:" | cut -d: -f2 | tr -d '[:space:]')
    if [ -n "${REDIS_MEM}" ]; then
        echo -e "         Memory usage: ${REDIS_MEM}"
    fi

    # Key count
    KEY_COUNT=$(docker exec "${REDIS_CONTAINER}" redis-cli DBSIZE 2>/dev/null | grep -oP '\d+' || echo "0")
    check_pass "Keys: ${KEY_COUNT} key(s) in database"
else
    check_fail "Redis container '${REDIS_CONTAINER}' is not running"
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}=== Summary ===${RESET}"
echo -e "  Total checks:  ${CHECKS_TOTAL}"
echo -e "  ${GREEN}Passed:${RESET}        ${CHECKS_PASSED}"
if [ "${CHECKS_FAILED}" -gt 0 ]; then
    echo -e "  ${RED}Failed:${RESET}        ${CHECKS_FAILED}"
fi
echo ""

if [ "${CHECKS_FAILED}" -gt 0 ]; then
    echo -e "${RED}${BOLD}Health check FAILED${RESET} -- ${CHECKS_FAILED} check(s) did not pass\n"
    exit 1
else
    echo -e "${GREEN}${BOLD}All checks passed${RESET}\n"
    exit 0
fi
