# The office app (optional container; the default is to run it natively, see docker-compose.yml).
# Stage 1: build the single-file frontend.
FROM node:22-slim AS frontend
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY build.mjs graph-build.mjs config.mjs office.config.json ./
COPY src ./src
COPY brain ./brain
RUN node build.mjs

# Stage 2: Python runtime — FastAPI + LangGraph.
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl git \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 1001 --create-home --shell /usr/sbin/nologin office

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY office.agents.json office.config.json ./
COPY skills ./skills
COPY --from=frontend /src/dist ./dist
RUN mkdir -p /app/data /brain && chown -R office:office /app/data /brain

ENV PYTHONUNBUFFERED=1
EXPOSE 4520
USER office

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS -H "Host: localhost" http://127.0.0.1:4520/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "4520"]
