# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl build-essential nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# The Zotero/pdf.js overlay probe may be run against a bind-mounted Windows
# zotero-pdfjs checkout. Its node_modules contains Windows native packages, so
# keep the Linux canvas binding inside the image and point @napi-rs/canvas at it.
RUN --mount=type=cache,target=/root/.npm \
    mkdir -p /opt/z2m-node \
    && cd /opt/z2m-node \
    && npm init -y \
    && npm install --omit=dev @napi-rs/canvas-linux-x64-gnu@0.1.100

ENV NAPI_RS_NATIVE_LIBRARY_PATH=/opt/z2m-node/node_modules/@napi-rs/canvas-linux-x64-gnu/skia.linux-x64-gnu.node

COPY pyproject.toml README.md ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install \
        marker-pdf==1.10.2 \
        "requests>=2.31" \
        "psutil>=5.9" \
        "mini-racer>=0.12" \
        "pymupdf>=1.24" \
        "pypdf>=4"

COPY src ./src
COPY tools ./tools
COPY experiments/lmstudio_instruct_translation ./experiments/lmstudio_instruct_translation
COPY docs ./docs

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps -e .

CMD ["pdf-html-convert", "--help"]
