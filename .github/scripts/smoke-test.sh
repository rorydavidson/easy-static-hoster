#!/bin/sh
# Starts the full stack in Basic Auth mode from already-built images and
# checks the behaviour that only shows up end to end: headers, blocked
# files, upload through nginx, rate limiting and the regenerated index.
#
# Usage: .github/scripts/smoke-test.sh   (after `docker compose build`)
set -eu

PROJECT="eh-smoke-$$"
PORT="${SMOKE_PORT:-18080}"
BASE="http://127.0.0.1:$PORT"
CONTENT_DIR=$(mktemp -d)
# mktemp makes it 0700; nginx runs as a different uid and must traverse it
chmod 755 "$CONTENT_DIR"
# Throwaway credentials, generated per run
CREDS="smoke:$(openssl rand -hex 12)"

export CONTENT_DIR PORT BASIC_AUTH="$CREDS" SITE_TITLE="Smoke Test"

cleanup() {
    docker compose -p "$PROJECT" down -v >/dev/null 2>&1 || true
    # The generator chowns the content dir to uid 1000, so remove it from a container
    docker run --rm -v "$CONTENT_DIR:/c" alpine:3 sh -c 'rm -rf /c/* /c/.[!.]*' >/dev/null 2>&1 || true
    rmdir "$CONTENT_DIR" 2>/dev/null || true
}
trap cleanup EXIT

failures=0
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1"; failures=$((failures + 1)); }
expect_status() {  # <label> <expected> <curl args...>
    label="$1"; expected="$2"; shift 2
    actual=$(curl -s -o /dev/null -w '%{http_code}' "$@")
    if [ "$actual" = "$expected" ]; then pass "$label"; else fail "$label (got $actual, want $expected)"; fi
}
expect_match() {  # <label> <grep -i pattern> <curl args...>
    label="$1"; pattern="$2"; shift 2
    if curl -s "$@" | grep -qi "$pattern"; then pass "$label"; else fail "$label"; fi
}

mkdir -p "$CONTENT_DIR/reports"
printf '<html><head><title>Smoke Report</title></head><body>hi</body></html>\n' \
    >"$CONTENT_DIR/reports/smoke-report.html"

docker compose -p "$PROJECT" up -d --no-build --pull never --wait >/dev/null

# nginx has no healthcheck; wait for it to answer
for _ in $(seq 30); do
    curl -sf -o /dev/null "$BASE/" && break
    sleep 1
done

expect_status "index served" 200 "$BASE/"
expect_match "index lists page"      "Smoke Report" "$BASE/"
expect_match "index CSP"             "content-security-policy: default-src 'none'" -I "$BASE/"
expect_match "hosted page sandboxed" "content-security-policy: sandbox" -I "$BASE/reports/smoke-report.html"
expect_match "security headers"      "x-content-type-options: nosniff" -I "$BASE/"

expect_status "shortlinks.json blocked" 404 "$BASE/shortlinks.json"
expect_status "meta.json blocked"       404 "$BASE/reports/meta.json"
expect_status "dot-files blocked"       404 "$BASE/.index.html.tmp"

# 2 MB is over nginx's default body limit, so this proves the override
head -c 2000000 /dev/zero | tr '\0' 'a' >"$CONTENT_DIR.upload"
expect_status "upload over 1 MB" 200 -u "$CREDS" \
    -H 'X-Folder: reports' -H 'X-Filename: big-upload.html' \
    --data-binary "@$CONTENT_DIR.upload" "$BASE/api/upload"
rm -f "$CONTENT_DIR.upload"

expect_status "short link create" 200 -u "$CREDS" -H 'Content-Type: application/json' \
    -d '{"path":"reports/smoke-report.html","code":"smoke"}' "$BASE/api/shortlinks"
expect_status "short link redirect" 302 "$BASE/s/smoke"

# The index rebuilds about a second after changes settle
found=no
for _ in $(seq 15); do
    curl -s "$BASE/" | grep -q "reports/big-upload.html" && { found=yes; break; }
    sleep 1
done
if [ "$found" = yes ]; then pass "index picks up upload"; else fail "index picks up upload"; fi

# Once content stops changing, the generator must stop rebuilding
rebuilds() { docker compose -p "$PROJECT" logs generator 2>/dev/null | grep -c "Index rebuilt"; }
sleep 3
before=$(rebuilds)
sleep 6
after=$(rebuilds)
if [ "$before" = "$after" ]; then pass "generator settles"; else fail "generator settles ($before -> $after rebuilds while idle)"; fi

# Last, as it exhausts this client's API allowance
expect_status "bad credentials rejected" 401 -u smoke:wrong \
    -H 'Content-Type: application/json' -d '{}' "$BASE/api/shortlinks"
limited=no
for _ in $(seq 15); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -u smoke:wrong \
        -H 'Content-Type: application/json' -d '{}' "$BASE/api/shortlinks")
    [ "$code" = 429 ] && { limited=yes; break; }
done
if [ "$limited" = yes ]; then pass "API rate limited"; else fail "API rate limited"; fi

if [ "$failures" -ne 0 ]; then
    echo "$failures check(s) failed; container logs:"
    docker compose -p "$PROJECT" logs --no-color --tail 50
    exit 1
fi
