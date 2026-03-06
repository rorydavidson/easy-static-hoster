FROM python:3.12-alpine

WORKDIR /app

# su-exec: lightweight tool to drop from root to appuser after fixing volume ownership
RUN apk add --no-cache su-exec

# Create a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate.py .
COPY shortlinks_server.py .
COPY templates/ templates/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Entrypoint runs as root to fix /content ownership, then drops to appuser
ENTRYPOINT ["./entrypoint.sh"]
