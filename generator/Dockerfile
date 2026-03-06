FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate.py .
COPY shortlinks_server.py .
COPY templates/ templates/

CMD ["python", "generate.py"]
