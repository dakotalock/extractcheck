FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/extractcheck
ENV PYTHONPATH=/app
ENV EXTRACTCHECK_RECEIPTS=/app/extractcheck/data/receipts.jsonl
EXPOSE 8787

CMD ["sh", "-c", "uvicorn extractcheck.api:app --host 0.0.0.0 --port ${PORT:-8787}"]
