FROM node:22-alpine
RUN apk add --no-cache python3 py3-pip git ripgrep uv ca-certificates \
    && mkdir -p /workspace /workspace/.venv /workspace/node_modules \
    && chown -R node:node /workspace
RUN chmod 1777 /workspace/.venv /workspace/node_modules
ENV GIT_TERMINAL_PROMPT=0 UV_PROJECT_ENVIRONMENT=/workspace/.venv UV_CACHE_DIR=/tmp/uv-cache NPM_CONFIG_CACHE=/tmp/npm-cache
USER node
WORKDIR /workspace
