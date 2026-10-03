# Build-job image for the OpenHands CLI (bake-off candidate). Package name and install
# method are UNVERIFIED: confirm against the OpenHands docs before the first build.
# Build:  docker build -f infra/sandbox/worker-openhands.Dockerfile -t agents-office/worker-openhands:latest infra/sandbox
FROM python:3.12-slim-bookworm

ARG OPENHANDS_VERSION=

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates bash nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "openhands-ai${OPENHANDS_VERSION:+==$OPENHANDS_VERSION}"

COPY run-job.sh /opt/run-job.sh
RUN chmod 0755 /opt/run-job.sh && useradd --uid 1000 --create-home --home-dir /home/agent --shell /bin/bash agent || true

USER 1000:1000
WORKDIR /workspace
ENTRYPOINT []
