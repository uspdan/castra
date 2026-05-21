#!/usr/bin/env bash
#
# Sprint 13 — challenge image builder for the dev stack.
#
# Each ``challenges/<slug>/Dockerfile`` is built inside the DinD
# (orchestrator) container and tagged as ``siege/<slug>:latest``,
# matching the ``docker_image`` field the seed script writes into
# each challenge row. Idempotent — re-running rebuilds with cache.
#
# Prerequisites:
#   * dev stack up (``make dev``) and ``orchestrator`` container
#     attached to a non-internal network so DinD can pull base
#     images. ``docker-compose.dev.yml`` arranges that.
#
# Production path is different — images are expected to arrive via
# a registry mirror with pinned digests. This script is dev-only.

set -euo pipefail

ORCH="seige-range-orchestrator-1"
CHALLENGES_DIR_IN_DIND="/challenges"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Stage sealed answers + reveal flags into each challenge dir before
# the docker build sees them. Idempotent — safe to re-run.
"${REPO_ROOT}/scripts/stage-answers.sh"

cyan()  { printf '\033[96m%s\033[0m' "$*"; }
green() { printf '\033[92m%s\033[0m' "$*"; }
red()   { printf '\033[91m%s\033[0m' "$*"; }

if ! docker ps --format '{{.Names}}' | grep -qx "${ORCH}"; then
    red  "[ERR] orchestrator container '${ORCH}' is not running"
    echo "      bring the stack up with 'make dev' first" >&2
    exit 1
fi

mapfile -t SLUGS < <(docker exec "${ORCH}" sh -c \
    "ls -1 ${CHALLENGES_DIR_IN_DIND}" | tr -d '\r')

ok=0; fail=0; failures=()
for slug in "${SLUGS[@]}"; do
    [ -n "$slug" ] || continue
    if ! docker exec "${ORCH}" test -f "${CHALLENGES_DIR_IN_DIND}/${slug}/Dockerfile"; then
        continue
    fi
    cyan "[build]"; echo " ${slug}"
    if docker exec "${ORCH}" sh -c \
        "cd ${CHALLENGES_DIR_IN_DIND}/${slug} && docker build -t siege/${slug}:latest ." \
        > /tmp/build-${slug}.log 2>&1; then
        green "  [ok]"; echo " ${slug}"
        ok=$((ok+1))
    else
        red "  [fail]"; echo " ${slug} — see /tmp/build-${slug}.log"
        tail -5 /tmp/build-${slug}.log | sed 's/^/      /'
        fail=$((fail+1))
        failures+=("$slug")
    fi
done

echo
echo "== Build summary =="
printf "  built : "; green "${ok}"; echo
printf "  failed: "; red   "${fail}"; echo
for s in "${failures[@]}"; do
    echo "    - $s"
done

[ "$fail" -eq 0 ]
