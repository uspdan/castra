#!/usr/bin/env bash
#
# Siege Range CTF - Certificate Generator
# Creates a self-signed CA and server certificate for local HTTPS.
#
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[91m'
GREEN='\033[92m'
CYAN='\033[96m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CERT_DIR="${PROJECT_ROOT}/nginx/certs"
VALIDITY_DAYS=365

# Certificate subject fields
CA_SUBJECT="/C=US/ST=Cyber/L=Range/O=Siege Range CTF/OU=CA/CN=Siege Range Root CA"
SERVER_CN="${SERVER_CN:-siege.local}"
SERVER_SUBJECT="/C=US/ST=Cyber/L=Range/O=Siege Range CTF/OU=Server/CN=${SERVER_CN}"

# Subject Alternative Names
SERVER_SAN="DNS:${SERVER_CN},DNS:*.${SERVER_CN},DNS:localhost,IP:127.0.0.1"

# File paths
CA_KEY="${CERT_DIR}/ca.key"
CA_CERT="${CERT_DIR}/ca.crt"
SERVER_KEY="${CERT_DIR}/server.key"
SERVER_CSR="${CERT_DIR}/server.csr"
SERVER_CERT="${CERT_DIR}/server.crt"
SERVER_BUNDLE="${CERT_DIR}/server-bundle.crt"
EXT_FILE="${CERT_DIR}/server-ext.cnf"

# ── Main ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}=== Siege Range CTF - Certificate Generator ===${RESET}\n"

# Check for openssl
if ! command -v openssl &>/dev/null; then
    error "openssl is not installed or not in PATH"
    exit 1
fi

# Create output directory
mkdir -p "${CERT_DIR}"
info "Certificate directory: ${BOLD}${CERT_DIR}${RESET}"

# ── Generate CA Private Key ─────────────────────────────────────────────────
info "Generating CA private key ..."
openssl genrsa -out "${CA_KEY}" 4096 2>/dev/null
ok "CA private key: ${CA_KEY}"

# ── Generate CA Certificate ─────────────────────────────────────────────────
info "Generating CA certificate (${VALIDITY_DAYS} days) ..."
openssl req -x509 -new -nodes \
    -key "${CA_KEY}" \
    -sha256 \
    -days "${VALIDITY_DAYS}" \
    -subj "${CA_SUBJECT}" \
    -out "${CA_CERT}" \
    2>/dev/null
ok "CA certificate: ${CA_CERT}"

# ── Generate Server Private Key ──────────────────────────────────────────────
info "Generating server private key ..."
openssl genrsa -out "${SERVER_KEY}" 2048 2>/dev/null
ok "Server private key: ${SERVER_KEY}"

# ── Generate Server CSR ─────────────────────────────────────────────────────
info "Generating server certificate signing request ..."
openssl req -new \
    -key "${SERVER_KEY}" \
    -subj "${SERVER_SUBJECT}" \
    -out "${SERVER_CSR}" \
    2>/dev/null
ok "Server CSR: ${SERVER_CSR}"

# ── Create extensions file for SAN ───────────────────────────────────────────
cat > "${EXT_FILE}" <<EXTEOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage=serverAuth
subjectAltName=${SERVER_SAN}
EXTEOF

# ── Sign Server Certificate with CA ─────────────────────────────────────────
info "Signing server certificate with CA (${VALIDITY_DAYS} days) ..."
openssl x509 -req \
    -in "${SERVER_CSR}" \
    -CA "${CA_CERT}" \
    -CAkey "${CA_KEY}" \
    -CAcreateserial \
    -out "${SERVER_CERT}" \
    -days "${VALIDITY_DAYS}" \
    -sha256 \
    -extfile "${EXT_FILE}" \
    2>/dev/null
ok "Server certificate: ${SERVER_CERT}"

# ── Create full-chain bundle ─────────────────────────────────────────────────
info "Creating certificate bundle (server + CA) ..."
cat "${SERVER_CERT}" "${CA_CERT}" > "${SERVER_BUNDLE}"
ok "Certificate bundle: ${SERVER_BUNDLE}"

# ── Set permissions ──────────────────────────────────────────────────────────
chmod 600 "${CA_KEY}" "${SERVER_KEY}"
chmod 644 "${CA_CERT}" "${SERVER_CERT}" "${SERVER_BUNDLE}"

# ── Clean up temporary files ─────────────────────────────────────────────────
rm -f "${SERVER_CSR}" "${EXT_FILE}" "${CERT_DIR}/ca.srl"
info "Cleaned up temporary files"

# ── Verify ───────────────────────────────────────────────────────────────────
info "Verifying certificate chain ..."
if openssl verify -CAfile "${CA_CERT}" "${SERVER_CERT}" &>/dev/null; then
    ok "Certificate chain is valid"
else
    error "Certificate chain verification failed"
    exit 1
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${GREEN}=== Certificates Generated ===${RESET}"
echo -e ""
echo -e "  CA Key:         ${CA_KEY}"
echo -e "  CA Certificate: ${CA_CERT}"
echo -e "  Server Key:     ${SERVER_KEY}"
echo -e "  Server Cert:    ${SERVER_CERT}"
echo -e "  Bundle:         ${SERVER_BUNDLE}"
echo -e ""
echo -e "  Common Name:    ${SERVER_CN}"
echo -e "  SANs:           ${SERVER_SAN}"
echo -e "  Validity:       ${VALIDITY_DAYS} days"
echo -e ""
echo -e "  ${CYAN}Nginx config example:${RESET}"
echo -e "    ssl_certificate     /etc/nginx/certs/server-bundle.crt;"
echo -e "    ssl_certificate_key /etc/nginx/certs/server.key;"
echo -e ""
