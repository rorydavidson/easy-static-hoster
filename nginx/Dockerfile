FROM nginx:alpine

# openssl is needed by entrypoint.sh to hash the BASIC_AUTH password
RUN apk add --no-cache openssl

# Remove default vhost
RUN rm /etc/nginx/conf.d/default.conf

# Copy our config
COPY nginx.conf /etc/nginx/nginx.conf

# Placeholder auth file (overwritten at runtime by entrypoint.sh)
RUN touch /etc/nginx/global_auth.conf

# Temp dirs must be writable (nginx runs workers as nginx user)
RUN mkdir -p /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi \
    && chown -R nginx:nginx /tmp/client_body /tmp/proxy /tmp/fastcgi /tmp/uwsgi /tmp/scgi

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
