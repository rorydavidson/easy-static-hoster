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

    AUTH_DIRECTIVES='auth_basic "Restricted";\nauth_basic_user_file /etc/nginx/.htpasswd;\n'

    if [ -n "$AUTH_GLOBAL" ]; then
        # Lock the entire site via nginx
        printf "$AUTH_DIRECTIVES" > /etc/nginx/global_auth.conf
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

exec nginx -g "daemon off;"
