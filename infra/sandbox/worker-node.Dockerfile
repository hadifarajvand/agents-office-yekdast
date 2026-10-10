# Build-job image: Node toolchain, git, and the coding-agent CLIs under test.
# Build:  npm run image   (scripts/build-worker-image.sh: --pull=false, template as a named context,
#         reports how many layers were reused). Editing run-job.sh or run-checks.mjs rebuilds in
#         about a second; only a template package.json / package-lock.json change re-runs npm.
# Pin CLAUDE_CODE_VERSION and MINI_SWE_VERSION to the versions the bake-off used.
FROM node:22-bookworm-slim

ARG CLAUDE_CODE_VERSION=latest
ARG MINI_SWE_VERSION=

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates bash python3 python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && python3 -m pip install --no-cache-dir --break-system-packages "mini-swe-agent${MINI_SWE_VERSION:+==$MINI_SWE_VERSION}"

# Chromium for the template's Playwright tests. Keep PLAYWRIGHT_VERSION equal to the version
# pinned in templates/webapp/package.json, or the browser and the library will not match.
ARG PLAYWRIGHT_VERSION=1.63.0
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN npx -y "playwright@${PLAYWRIGHT_VERSION}" install --with-deps chromium \
 && chmod -R a+rx /ms-playwright

# The platform's own template dependencies are baked in: its lockfile is installed once here
# and the npm cache stays in the image, so a job's `npm ci` resolves offline from this copy
# instead of fetching from the registry every time. Only a dependency the builder adds is
# fetched (through the egress proxy). The template comes in as a named build context:
#   docker build --pull=false --build-context template=templates/webapp -f infra/sandbox/worker-node.Dockerfile -t agents-office/worker-node:latest infra/sandbox
ENV npm_config_cache=/opt/npm-cache
COPY --from=template package.json package-lock.json /opt/template/
RUN cd /opt/template && npm ci --no-audit --no-fund --ignore-scripts \
 && rm -rf /opt/template/node_modules \
 && chmod -R a+rwX /opt/npm-cache

COPY run-job.sh /opt/run-job.sh
COPY run-checks.mjs /opt/run-checks.mjs
RUN chmod 0755 /opt/run-job.sh /opt/run-checks.mjs \
 && useradd --uid 1000 --create-home --home-dir /home/agent --shell /bin/bash agent || true

USER 1000:1000
WORKDIR /workspace
ENTRYPOINT []
