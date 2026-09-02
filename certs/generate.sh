#!/usr/bin/env bash
# Generate the five defective TLS certificates for the range's cert-defect
# hosts. All keys/certs are throwaway and live only inside the isolated range.
#
#   expired      - notAfter in the past
#   self-signed  - not chained to the range CA
#   mismatch     - CN/SAN does not match the served hostname
#   oldtls       - normal cert; the terminator is configured for TLS 1.0/1.1
#   expiring     - valid but notAfter < 14 days away
#
# Usage: BASE_DOMAIN=range.example.net ./generate.sh [out_dir]
set -euo pipefail

BASE_DOMAIN="${BASE_DOMAIN:-range.invalid}"
OUT="${1:-$(cd "$(dirname "$0")" && pwd)/out}"
mkdir -p "$OUT"

KEYOPTS="-newkey rsa:2048 -nodes"
SUBJ_O="/O=AIS-Y Test Range/OU=deliberately vulnerable"

echo "base domain: $BASE_DOMAIN"
echo "output:      $OUT"

# --- range CA (chains the self-signed counter-example against it) -----------
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -keyout "$OUT/range-ca.key" -out "$OUT/range-ca.crt" \
    -subj "${SUBJ_O}/CN=AIS-Y Range Root CA" 2>/dev/null

sign_with_ca() { # host days_offset  (negative => already expired)
    local host="$1" days="$2" cn="$3"
    openssl req $KEYOPTS -keyout "$OUT/${host}.key" -out "$OUT/${host}.csr" \
        -subj "${SUBJ_O}/CN=${cn}" 2>/dev/null
    # -days cannot go negative; use explicit start/end for the expired case.
    if [ "$days" -lt 0 ]; then
        local end; end="$(date -u -v"${days}d" +%Y%m%d%H%M%SZ 2>/dev/null \
            || date -u -d "${days} days" +%Y%m%d%H%M%SZ)"
        openssl x509 -req -in "$OUT/${host}.csr" \
            -CA "$OUT/range-ca.crt" -CAkey "$OUT/range-ca.key" -CAcreateserial \
            -not_before 20200101000000Z -not_after "$end" \
            -out "$OUT/${host}.crt" 2>/dev/null
    else
        openssl x509 -req -in "$OUT/${host}.csr" -days "$days" \
            -CA "$OUT/range-ca.crt" -CAkey "$OUT/range-ca.key" -CAcreateserial \
            -out "$OUT/${host}.crt" 2>/dev/null
    fi
    rm -f "$OUT/${host}.csr"
}

# 1. expired: cert whose validity ended in the past.
sign_with_ca "expired" -30 "expired.${BASE_DOMAIN}"

# 2. self-signed: NOT signed by the range CA.
openssl req -x509 $KEYOPTS -days 365 \
    -keyout "$OUT/self-signed.key" -out "$OUT/self-signed.crt" \
    -subj "${SUBJ_O}/CN=self-signed.${BASE_DOMAIN}" 2>/dev/null

# 3. mismatch: valid cert, wrong name (CN belongs to another host).
sign_with_ca "mismatch" 365 "not-the-right-host.${BASE_DOMAIN}"

# 4. oldtls: a normal, valid cert. Weakness is in the terminator config below.
sign_with_ca "oldtls" 365 "oldtls.${BASE_DOMAIN}"

# 5. expiring: valid today but notAfter is < 14 days away.
sign_with_ca "expiring" 7 "expiring.${BASE_DOMAIN}"

# --- weak-TLS terminator snippet for the oldtls host ------------------------
# nginx TLS terminator forced to legacy protocols/ciphers. Wired into the
# oldtls container in scenarios/range-web-2/docker-compose.yml.
cat > "$OUT/oldtls.nginx.conf" <<'NGINX'
# oldtls host: intentionally weak TLS for the range's weak-TLS detector.
server {
    listen 443 ssl;
    server_name oldtls;
    ssl_certificate     /certs/oldtls.crt;
    ssl_certificate_key /certs/oldtls.key;
    ssl_protocols TLSv1 TLSv1.1;                 # deliberately obsolete
    ssl_ciphers DEFAULT@SECLEVEL=0:ECDHE-RSA-DES-CBC3-SHA;  # weak
    location / { return 200 "range oldtls terminator\n"; }
}
NGINX

echo "generated 5 defective certs + oldtls.nginx.conf in $OUT"
