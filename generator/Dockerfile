FROM python:3.12-alpine

WORKDIR /app

# Create a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate.py .
COPY shortlinks_server.py .
COPY templates/ templates/

# Ensure the appuser can write to any necessary directories if needed, 
# although content is usually a volume. The app itself doesn't need root.
USER appuser

CMD ["python", "generate.py"]
