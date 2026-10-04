# AdPilot web image: builds the Vite bundle, then serves it from nginx which
# also reverse-proxies /api to the API service.
FROM node:20-alpine AS build

WORKDIR /build
# Install with the lockfile so the image is reproducible, and because npm
# workspaces place apps/web inside this root project.
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
RUN npm ci --workspace @adpilot/web --include-workspace-root

COPY apps/web ./apps/web
RUN npm run build --workspace @adpilot/web


FROM nginx:1.27-alpine AS runtime

# nginx serves the built assets and reverse-proxies /api to the FastAPI service,
# so the whole stack runs from one compose command with no extra local tooling.
COPY --from=build /build/apps/web/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY apps/api/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    AUTH_DB_PATH="/data/adpilot.db" \
    STORAGE_DIR="/data/storage"

RUN groupadd --system adpilot && useradd --system --gid adpilot --create-home adpilot

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY apps/api/app ./app

# Uploads and the local database live on a volume so they survive redeploys.
RUN mkdir -p /data/storage && chown -R adpilot:adpilot /data /app
VOLUME ["/data"]

USER adpilot
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]