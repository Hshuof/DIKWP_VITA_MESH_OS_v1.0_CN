FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VITA_LEDGER=/data/vitality.db \
    VITA_ARTIFACT=DIKWP-VITA-MESH \
    VITA_NODE_ID=docker-reference-node

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 vita \
    && mkdir -p /data \
    && chown -R vita:vita /data /app

USER vita
VOLUME ["/data"]
EXPOSE 8787

CMD ["dikwp-vita", "serve", "--host", "0.0.0.0", "--port", "8787", "--ledger", "/data/vitality.db", "--node-id", "docker-reference-node"]
