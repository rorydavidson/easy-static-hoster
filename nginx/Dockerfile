FROM nginx:alpine

# openssl is needed by entrypoint.sh to hash the BASIC_AUTH password
RUN apk add --no-cache openssl

# Remove default vhost
RUN rm /etc/nginx/conf.d/default.conf

# Copy our config
COPY nginx.conf /etc/nginx/nginx.conf

# Placeholder auth file (overwritten at runtime by entrypoint.sh)
RUN touch /etc/nginx/global_auth.conf && chown nginx:nginx /etc/nginx/global_auth.conf

# Temp dirs must be writable (nginx runs workers as nginx user)
RUN mkdir -p /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chown -R nginx:nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /var/run

# Favicon (served from a fixed path, not the content volume)
COPY favicon.ico /usr/share/nginx/favicon.ico

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Move PID file to a writable location (already in nginx.conf as /tmp/nginx.pid)
# Ensure the entrypoint can write the auth file
RUN chown nginx:nginx /etc/nginx

USER nginx

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
