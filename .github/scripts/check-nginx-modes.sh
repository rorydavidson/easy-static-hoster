#!/bin/sh
# Runs the nginx entrypoint under each auth mode and checks the generated
# config: `nginx -t` must pass and the hosted-page sandbox must be on only
# when the site is public.
#
# Usage: .github/scripts/check-nginx-modes.sh <nginx-image>
set -eu

IMAGE="$1"
NETWORK="eh-nginx-check-$$"

# nginx resolves proxy_pass hosts at startup, so "generator" must exist
docker network create "$NETWORK" >/dev/null
docker run -d --rm --name "generator-$$" --network-alias generator \
    --network "$NETWORK" alpine:3 sleep 300 >/dev/null
trap 'docker rm -f "generator-$$" >/dev/null 2>&1; docker network rm "$NETWORK" >/dev/null 2>&1' EXIT

failures=0

# check <label> <expect sandbox: yes|no> [docker run -e flags...]
check() {
    label="$1"; expect="$2"; shift 2
    output=$(docker run --rm --network "$NETWORK" "$@" --entrypoint sh "$IMAGE" -c '
        /entrypoint.sh >/tmp/out 2>&1 &
        sleep 1
        nginx -t 2>&1 | tail -1
        cat /etc/nginx/content_csp.conf
    ')
    result=ok
    echo "$output" | grep -q "test is successful" || result="nginx -t failed"
    if [ "$expect" = yes ]; then
        echo "$output" | grep -q 'default "sandbox' || result="expected sandbox"
    else
        echo "$output" | grep -q 'default "";' || result="expected no sandbox"
    fi
    echo "$label: $result"
    [ "$result" = ok ] || { echo "$output"; failures=$((failures + 1)); }
}

check "no auth"                yes
check "basic auth"             yes -e BASIC_AUTH=user:pw
check "basic + AUTH_GLOBAL"    no  -e BASIC_AUTH=user:pw -e AUTH_GLOBAL=true
check "AUTH_GLOBAL=false"      yes -e BASIC_AUTH=user:pw -e AUTH_GLOBAL=false
check "CONTENT_SANDBOX=false"  no  -e CONTENT_SANDBOX=false
check "OIDC"                   no  -e OIDC_ISSUER_URL=https://idp.example \
                                   -e TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
check "TRUSTED_PROXIES=auto"   yes -e TRUSTED_PROXIES=auto

# Conflicting modes must refuse to start
if docker run --rm --network "$NETWORK" -e BASIC_AUTH=user:pw \
        -e OIDC_ISSUER_URL=https://idp.example "$IMAGE" >/dev/null 2>&1; then
    echo "BASIC_AUTH + OIDC: expected startup failure"; failures=$((failures + 1))
else
    echo "BASIC_AUTH + OIDC: ok (refused)"
fi

[ "$failures" -eq 0 ]
