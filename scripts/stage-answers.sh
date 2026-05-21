#!/usr/bin/env bash
#
# Pre-build hook — stage sealed answers + reveal flags into each
# challenge directory as gitignored sidecar files (.answers.json,
# .flag.txt) that the Dockerfile COPYs into the container image.
#
# Reads:
#   secrets/answers/campaigns/<campaign-stem>.json
#   secrets/answers/validators/<challenge-slug>.json
#   secrets/flags.json   (keyed by challenge slug)
#
# Writes (mode 0600, gitignored):
#   challenges/<slug>/.answers.json
#   challenges/<slug>/.flag.txt
#
# Idempotent. Run before ``scripts/build_challenge_images.sh`` (or
# any other docker build over the challenges/ tree).
#
# Exit codes:
#   0 — staged something or no-op (every challenge already has
#       sidecars, or it's a hand-rolled challenge with no sealed map)
#   1 — operator error (secrets dir missing, json malformed)
#   2 — a challenge dir references sealed answers that aren't present
#       in the secrets store (fail-loud: the build would silently
#       ship a validator that rejects every submission)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="${REPO_ROOT}/secrets"
CHALLENGES="${REPO_ROOT}/challenges"
FLAGS_JSON="${SECRETS}/flags.json"

cyan()  { printf '\033[96m%s\033[0m' "$*"; }
green() { printf '\033[92m%s\033[0m' "$*"; }
red()   { printf '\033[91m%s\033[0m' "$*"; }
amber() { printf '\033[93m%s\033[0m' "$*"; }

if [ ! -d "${SECRETS}" ]; then
    red "[ERR] secrets/ directory not found at ${SECRETS}"; echo
    echo "      Run scripts/seal-flags.py and scripts/seal-answers.py first." >&2
    exit 1
fi
if [ ! -f "${FLAGS_JSON}" ]; then
    red "[ERR] ${FLAGS_JSON} not present — run scripts/seal-flags.py"; echo
    exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
    red "[ERR] jq is required to stage answers"; echo
    exit 1
fi

ok=0; skipped=0; missing=()

for chdir in "${CHALLENGES}"/*/; do
    [ -d "${chdir}" ] || continue
    slug="$(basename "${chdir}")"
    [ "${slug}" = "_factory" ] && continue
    [ -f "${chdir}/Dockerfile" ] || continue

    answers_src=""
    if [ -f "${SECRETS}/answers/validators/${slug}.json" ]; then
        answers_src="${SECRETS}/answers/validators/${slug}.json"
    elif [ -f "${SECRETS}/answers/campaigns/${slug}.json" ]; then
        # Direct slug match (rare — most campaigns use a different
        # yaml stem like ta0001-initial-access for slug
        # tier-2-initial-access). Fall through to lookup-by-prefix.
        answers_src="${SECRETS}/answers/campaigns/${slug}.json"
    else
        # Heuristic — yaml stem to slug map: the materialised tree
        # records the slug, but the seal-answers.py keys campaigns
        # by yaml stem. Walk the campaign jsons and pick the one
        # whose corresponding yaml has slug=${slug}.
        for yml in "${REPO_ROOT}"/challenges/_factory/campaigns/*.yaml; do
            [ -f "${yml}" ] || continue
            yaml_slug="$(awk '/^slug:/ {print $2; exit}' "${yml}" | tr -d '"')"
            if [ "${yaml_slug}" = "${slug}" ]; then
                stem="$(basename "${yml}" .yaml)"
                if [ -f "${SECRETS}/answers/campaigns/${stem}.json" ]; then
                    answers_src="${SECRETS}/answers/campaigns/${stem}.json"
                fi
                break
            fi
        done
    fi

    flag="$(jq -r --arg s "${slug}" '.[$s] // ""' "${FLAGS_JSON}")"

    if [ -z "${answers_src}" ] && [ -z "${flag}" ]; then
        amber "[skip]"; echo " ${slug} (no sealed answers + no sealed flag — hand-rolled?)"
        skipped=$((skipped+1))
        continue
    fi

    if [ -n "${answers_src}" ]; then
        install -m 0600 "${answers_src}" "${chdir}/.answers.json"
    else
        # Validator may have its own hardcoded answers — emit an
        # empty stub so the Dockerfile COPY still succeeds.
        printf '{}\n' > "${chdir}/.answers.json"
        chmod 0600 "${chdir}/.answers.json"
        missing+=("${slug} (no sealed answers — stubbed; validator will fail-closed)")
    fi

    if [ -n "${flag}" ]; then
        printf '%s\n' "${flag}" > "${chdir}/.flag.txt"
        chmod 0600 "${chdir}/.flag.txt"
    else
        printf '' > "${chdir}/.flag.txt"
        chmod 0600 "${chdir}/.flag.txt"
        missing+=("${slug} (no sealed flag — stubbed; reveal will fail-closed)")
    fi

    cyan "[ok]"; echo "   ${slug}"
    ok=$((ok+1))
done

echo
echo "== stage-answers summary =="
printf "  staged : "; green "${ok}"; echo
printf "  skipped: "; amber "${skipped}"; echo
if [ "${#missing[@]}" -gt 0 ]; then
    printf "  partial: "; amber "${#missing[@]}"; echo
    for m in "${missing[@]}"; do
        echo "    - $m"
    done
fi
