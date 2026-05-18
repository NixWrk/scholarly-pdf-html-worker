FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl build-essential nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tools ./tools
COPY experiments/lmstudio_instruct_translation ./experiments/lmstudio_instruct_translation
COPY docs ./docs

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir marker-pdf==1.10.2 \
    && pip install --no-cache-dir -e ".[math,pdf-text-detect]"

CMD ["pdf-html-convert", "--help"]
