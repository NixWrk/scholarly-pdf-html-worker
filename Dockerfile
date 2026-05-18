# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl build-essential nodejs \
    && rm -rf /var/lib/apt/lists/*

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
