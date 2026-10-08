#!/bin/sh
set -e

# AUTH modes (controlled by env vars):
#
#   BASIC_AUTH=user:pass               → upload endpoint requires credentials;
#                                        rest of site is public.
#
#   BASIC_AUTH=user:pass AUTH_GLOBAL=true → entire site requires credentials
#                                           (upload is also protected).
#
#   (unset)                            → site fully public, no upload button.

# TRUSTED_PROXIES: comma- or space-separated CIDRs of reverse proxies allowed
# to set X-Forwarded-For. Leave empty when clients connect to nginx directly.
: > /etc/nginx/real_ip.conf
if [ -n "$TRUSTED_PROXIES" ]; then
    for cidr in $(echo "$TRUSTED_PROXIES" | tr ',' ' '); do
        case "$cidr" in
            *[!0-9A-Fa-f.:/]*)
                echo "ERROR: invalid TRUSTED_PROXIES entry: $cidr" >&2
                exit 1
                ;;
        esac
        echo "set_real_ip_from $cidr;" >> /etc/nginx/real_ip.conf
    done
    printf 'real_ip_header X-Forwarded-For;\nreal_ip_recursive on;\n' >> /etc/nginx/real_ip.conf
fi

# Identity headers sent to the generator's /api/ endpoints. Outside OIDC mode
# they are always blanked so a client can never supply its own.
cat > /etc/nginx/api_auth.conf <<'EOF'
proxy_set_header X-Forwarded-User  "";
proxy_set_header X-Forwarded-Email "";
EOF
echo "" > /etc/nginx/oidc_auth_location.conf

# Whether anonymous visitors can load hosted pages; decides the content sandbox below.
SITE_PUBLIC=true

# OIDC mode: oauth2-proxy handles auth; skip Basic Auth setup entirely.
if [ -n "$OIDC_ISSUER_URL" ]; then
    if [ -n "$BASIC_AUTH" ]; then
        echo "ERROR: BASIC_AUTH and OIDC_ISSUER_URL are mutually exclusive" >&2
        exit 1
    fi
    echo "" > /etc/nginx/global_auth.conf
    SITE_PUBLIC=false

    # Every /api/ request is checked against oauth2-proxy, and the user
    # identity comes from its answer. This fails closed: if oauth2-proxy is
    # missing (e.g. the OIDC overlay was not used) the API returns an error
    # instead of trusting whatever headers the client sent.
    cat > /etc/nginx/api_auth.conf <<'EOF'
auth_request /_oauth2_auth;
auth_request_set $auth_user  $upstream_http_x_auth_request_user;
auth_request_set $auth_email $upstream_http_x_auth_request_email;
proxy_set_header X-Forwarded-User  $auth_user;
proxy_set_header X-Forwarded-Email $auth_email;
EOF

    # The upstream is resolved per request (Docker's DNS) rather than at
    # startup, because oauth2-proxy starts after nginx.
    cat > /etc/nginx/oidc_auth_location.conf <<'EOF'
location = /_oauth2_auth {
    internal;
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $oauth2_proxy oauth2-proxy:4180;
    proxy_pass http://$oauth2_proxy/oauth2/auth;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_read_timeout 5s;
}
EOF
    echo "OIDC mode: authentication handled by oauth2-proxy"

elif [ -n "$BASIC_AUTH" ]; then
    USER=$(echo "$BASIC_AUTH" | cut -d: -f1)
    PASS=$(echo "$BASIC_AUTH" | cut -d: -f2-)

    if [ -z "$USER" ] || [ -z "$PASS" ]; then
        echo "BASIC_AUTH must be in 'user:password' format" >&2
        exit 1
    fi

    # Generate htpasswd entry using openssl (available in alpine)
    HASH=$(openssl passwd -apr1 "$PASS")
    echo "$USER:$HASH" > /etc/nginx/.htpasswd

    AUTH_DIRECTIVES='auth_basic "Restricted";\nauth_basic_user_file /etc/nginx/.htpasswd;\n'

    if [ -n "$AUTH_GLOBAL" ]; then
        # Lock the entire site via nginx
        printf "$AUTH_DIRECTIVES" > /etc/nginx/global_auth.conf
        SITE_PUBLIC=false
        echo "Global auth enabled for user: $USER"
    else
        # Site is public; upload credentials are validated per-request in the generator
        echo "" > /etc/nginx/global_auth.conf
        echo "Upload auth enabled for user: $USER (site is public)"
    fi
else
    # No credentials — global auth include is empty, upload endpoint disabled
    echo "" > /etc/nginx/global_auth.conf
fi

# Hosted pages are arbitrary HTML served from the same origin as the index
# and the API. A CSP sandbox gives each one an opaque origin, so its scripts
# cannot read the index (where Basic Auth credentials are typed) or call the
# API. The catch: browsers send no cookies with a sandboxed page's own image,
# CSS and script requests, and do not reliably send cached Basic Auth either,
# so behind OIDC or AUTH_GLOBAL every asset would fail. The sandbox is
# therefore only applied when the site is public.
CONTENT_CSP="sandbox allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-pointer-lock allow-presentation"
if [ "$SITE_PUBLIC" = true ] && [ "$CONTENT_SANDBOX" != "false" ]; then
    echo "default \"$CONTENT_CSP\";" > /etc/nginx/content_csp.conf
    echo "Hosted pages are sandboxed (set CONTENT_SANDBOX=false to disable)"
else
    echo 'default "";' > /etc/nginx/content_csp.conf
fi

exec nginx -g "daemon off;"
