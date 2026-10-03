# Build-job image: Node toolchain, git, and the coding-agent CLIs under test.
# Build:  docker build -f infra/sandbox/worker-node.Dockerfile -t agents-office/worker-node:latest infra/sandbox
# Pin CLAUDE_CODE_VERSION and MINI_SWE_VERSION to the versions the bake-off used.
FROM node:22-bookworm-slim

ARG CLAUDE_CODE_VERSION=latest
ARG MINI_SWE_VERSION=

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates bash python3 python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && python3 -m pip install --no-cache-dir --break-system-packages "mini-swe-agent${MINI_SWE_VERSION:+==$MINI_SWE_VERSION}"

COPY run-job.sh /opt/run-job.sh
RUN chmod 0755 /opt/run-job.sh \
 && useradd --uid 1000 --create-home --home-dir /home/agent --shell /bin/bash agent || true

USER 1000:1000
WORKDIR /workspace
ENTRYPOINT []
