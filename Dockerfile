# syntax=docker/dockerfile:1.7
#
# localscribe: React UI + FastAPI server + on-device transcription pipeline.
#   docker compose up --build        -> http://localhost:8000
# See README "Run with Docker" for HF_TOKEN and volumes.

########## 1. Frontend build ##########
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

########## 2. Python runtime ##########
FROM python:3.12-slim-bookworm AS runtime

# cpu (default): CPU-only torch wheel, ~3 GB smaller (the pipeline runs on
# CPU: faster-whisper int8 + pyannote). Anything else: torch exactly as
# locked in uv.lock (pulls CUDA libraries on linux/amd64).
ARG TORCH_VARIANT=cpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.9.2

WORKDIR /app

# Dependencies first (cached unless pyproject/uv.lock change).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv "$VIRTUAL_ENV" --python "$(command -v python3)" \
    && uv export --frozen --no-dev --extra server --no-hashes --no-emit-project -o /tmp/requirements.txt \
    && if [ "$TORCH_VARIANT" = "cpu" ]; then \
         TORCH_VERSION=$(grep -E '^torch==' /tmp/requirements.txt | sed -E 's/^torch==([^ ;]+).*/\1/') \
         && uv pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}" \
         && grep -vE '^(torch==|nvidia-|triton==|cuda-)' /tmp/requirements.txt > /tmp/requirements.cpu.txt \
         && uv pip install --no-deps -r /tmp/requirements.cpu.txt ; \
       else \
         uv pip install --no-deps -r /tmp/requirements.txt ; \
       fi

COPY src/ src/
COPY templates/ templates/
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps .
COPY --from=frontend /frontend/dist /app/frontend/dist

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/tmp /models \
    && chown -R app:app /data /models
USER app

ENV LOCALSCRIBE_DATA_DIR=/data \
    LOCALSCRIBE_TEMPLATE=/app/templates/coding_transcription_template.docx \
    LOCALSCRIBE_STATIC_DIR=/app/frontend/dist \
    LOCALSCRIBE_HOST=0.0.0.0 \
    LOCALSCRIBE_PORT=8000 \
    TMPDIR=/data/tmp \
    MALLOC_ARENA_MAX=2 \
    HF_HOME=/models/huggingface \
    XDG_CACHE_HOME=/models/cache

VOLUME ["/data", "/models"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["localscribe-server"]
