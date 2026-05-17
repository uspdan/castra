#!/usr/bin/env bash
# build-offline-bundle.sh
#
# Pre-builds every runnable seige-range challenge image, saves
# them as a portable tarball, and bundles the `seige` CLI plus the
# operator runbook into a single tar.zst that can be carried on a
# USB stick / dropped on a laptop at a customer site / loaded on an
# air-gapped network.
#
# Usage:
#     scripts/build-offline-bundle.sh [--out PATH]
#
# Output (by default):
#     dist/seige-offline-<YYYYMMDD>.tar.zst
#
# Reload on the target host:
#     tar --use-compress-program=unzstd -xvf seige-offline-*.tar.zst
#     cd seige-offline
#     ./load-images.sh                # docker load < images/*.tar
#     ./scripts/seige list

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/dist"
DATE_TAG="$(date +%Y%m%d)"
BUNDLE_NAME="seige-offline-${DATE_TAG}"
BUNDLE_DIR="${OUT_DIR}/${BUNDLE_NAME}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out) OUT_DIR="$2"; BUNDLE_DIR="${OUT_DIR}/${BUNDLE_NAME}"; shift 2 ;;
        --help|-h) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
done

command -v docker >/dev/null || { echo "docker not on PATH" >&2; exit 1; }
command -v zstd   >/dev/null || { echo "zstd not on PATH" >&2;   exit 1; }

mkdir -p "${BUNDLE_DIR}/images" "${BUNDLE_DIR}/scripts"

echo "[bundle] building all runnable challenge images..."
"${ROOT}/scripts/seige" pull

# Snapshot every siege/<slug>:latest image to a single tar to keep
# layer dedup. `docker save` accepts multiple images at once.
IMAGES=$("${ROOT}/scripts/seige" list 2>/dev/null | awk 'NR>2 {print "siege/"$4":latest"}' | sort -u)
if [[ -z "${IMAGES}" ]]; then
    echo "[bundle] no images to save — aborting" >&2
    exit 1
fi
COUNT=$(echo "${IMAGES}" | wc -l)
echo "[bundle] saving ${COUNT} images to images/all.tar..."
# shellcheck disable=SC2086  # we want $IMAGES word-split
docker save -o "${BUNDLE_DIR}/images/all.tar" ${IMAGES}

cp "${ROOT}/scripts/seige" "${BUNDLE_DIR}/scripts/seige"

# A tiny loader script so the player on the target host doesn't
# need to remember the `docker load` invocation.
cat > "${BUNDLE_DIR}/load-images.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
for tar in images/*.tar; do
    echo "[load] $tar"
    docker load -i "$tar"
done
echo "[load] done. try: ./scripts/seige list"
EOF
chmod +x "${BUNDLE_DIR}/load-images.sh" "${BUNDLE_DIR}/scripts/seige"

# Copy the runbook + the challenge manifests (so the offline CLI can
# discover challenges without the full repo present).
mkdir -p "${BUNDLE_DIR}/challenges"
for dir in "${ROOT}/challenges"/*/; do
    slug="$(basename "${dir}")"
    if [[ -f "${dir}/challenge.json" && -f "${dir}/Dockerfile" ]]; then
        mkdir -p "${BUNDLE_DIR}/challenges/${slug}"
        cp "${dir}/challenge.json" "${BUNDLE_DIR}/challenges/${slug}/challenge.json"
        # Dockerfile-presence stub so _is_runnable() passes.
        cp "${dir}/Dockerfile" "${BUNDLE_DIR}/challenges/${slug}/Dockerfile"
    fi
done

cp "${ROOT}/docs/runbooks/offline-workstation.md" "${BUNDLE_DIR}/README.md" 2>/dev/null \
    || echo "[bundle] (runbook not found — README.md will be skipped)"

echo "[bundle] packing tar.zst..."
( cd "${OUT_DIR}" && tar -cf - "${BUNDLE_NAME}" | zstd -19 -o "${BUNDLE_NAME}.tar.zst" )

SIZE=$(du -sh "${OUT_DIR}/${BUNDLE_NAME}.tar.zst" | awk '{print $1}')
echo "[bundle] done: ${OUT_DIR}/${BUNDLE_NAME}.tar.zst (${SIZE})"
echo "[bundle] reload on target: tar --use-compress-program=unzstd -xvf ${BUNDLE_NAME}.tar.zst && cd ${BUNDLE_NAME} && ./load-images.sh"
