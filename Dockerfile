# syntax=docker/dockerfile:1.7

FROM node:22-bookworm AS zotero-pdfjs-build

ARG ZOTERO_PDFJS_REF=f57fc80d1c07e4cdc50a767ae0b500b5272123b4

WORKDIR /zotero-pdfjs-src

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git init . \
    && git remote add origin https://github.com/zotero/pdf.js.git \
    && git fetch --depth 1 origin "${ZOTERO_PDFJS_REF}" \
    && git checkout --detach FETCH_HEAD

RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    && npx gulp generic-legacy

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
    mkdir -p /opt/pdf-html-polish-node \
    && cd /opt/pdf-html-polish-node \
    && npm init -y \
    && npm install --omit=dev @napi-rs/canvas-linux-x64-gnu@0.1.100

ENV NAPI_RS_NATIVE_LIBRARY_PATH=/opt/pdf-html-polish-node/node_modules/@napi-rs/canvas-linux-x64-gnu/skia.linux-x64-gnu.node
ENV PDF_HTML_POLISH_ZOTERO_PDFJS_DIR=/opt/zotero-pdfjs \
    Z2M_ZOTERO_PDFJS_DIR=/opt/zotero-pdfjs

COPY pyproject.toml README.md ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install \
        marker-pdf==1.10.2 \
        "requests>=2.31" \
        "psutil>=5.9" \
        "pytest>=8" \
        "mini-racer>=0.12" \
        "pymupdf>=1.24" \
        "pypdf>=4"

# Marker downloads this font lazily at runtime if it is missing. Runtime
# containers must stay offline-safe, so warm the exact cache path in the image.
RUN --mount=type=cache,target=/root/.cache/marker \
    python -c "from marker.util import download_font; download_font()"

COPY src ./src
COPY tools ./tools
COPY docs ./docs
COPY --from=zotero-pdfjs-build /zotero-pdfjs-src/build/generic-legacy /opt/zotero-pdfjs/build/generic-legacy
COPY --from=zotero-pdfjs-build /zotero-pdfjs-src/node_modules/@napi-rs /opt/zotero-pdfjs/node_modules/@napi-rs

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps -e .

CMD ["pdf-html-polish", "--help"]
