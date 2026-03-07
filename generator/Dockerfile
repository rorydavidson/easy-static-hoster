FROM python:3.12-alpine AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Test stage ──────────────────────────────────────────────
# Runs the full test suite. The production stage depends on
# this via COPY --from, so a test failure breaks the build.
FROM base AS test

COPY generate.py shortlinks_server.py ./
COPY templates/ templates/
COPY tests/ tests/
ENV PYTHONPATH=/app
RUN python -m pytest tests/ -v && touch /tmp/.tests-passed

# ── Production stage ────────────────────────────────────────
FROM base AS production

# su-exec: lightweight tool to drop from root to appuser after fixing volume ownership
RUN apk add --no-cache su-exec

# Create a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Force the test stage to run before this image can be built
COPY --from=test /tmp/.tests-passed /tmp/.test-sentinel

COPY generate.py .
COPY shortlinks_server.py .
COPY templates/ templates/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Clean up test sentinel
RUN rm -rf /tmp/.test-sentinel

# Entrypoint runs as root to fix /content ownership, then drops to appuser
ENTRYPOINT ["./entrypoint.sh"]
