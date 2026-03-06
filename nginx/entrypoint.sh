#!/bin/sh
set -e

# Set up optional HTTP Basic Auth from BASIC_AUTH env var (user:password)
if [ -n "$BASIC_AUTH" ]; then
    USER=$(echo "$BASIC_AUTH" | cut -d: -f1)
    PASS=$(echo "$BASIC_AUTH" | cut -d: -f2-)

    if [ -z "$USER" ] || [ -z "$PASS" ]; then
        echo "BASIC_AUTH must be in 'user:password' format" >&2
        exit 1
    fi

    # Generate htpasswd entry using openssl (available in alpine)
    HASH=$(openssl passwd -apr1 "$PASS")
    echo "$USER:$HASH" > /etc/nginx/.htpasswd

    printf 'auth_basic "Restricted";\nauth_basic_user_file /etc/nginx/.htpasswd;\n' \
        > /etc/nginx/auth.conf

    echo "Basic auth enabled for user: $USER"
else
    # Empty include — auth disabled
    echo "" > /etc/nginx/auth.conf
fi

exec nginx -g "daemon off;"
