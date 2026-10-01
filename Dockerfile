# Stage 1: build the existing frontend, untouched.
FROM node:20-slim AS frontend
WORKDIR /src
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN node build.mjs

# Stage 2: Python runtime — FastAPI + LangGraph engine.
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY office.agents.json office.config.json ./
COPY skills ./skills
COPY --from=frontend /src/dist ./dist

ENV PYTHONUNBUFFERED=1
EXPOSE 4520

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "4520"]
