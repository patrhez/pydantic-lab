FROM pydantic-lab-sandbox:local AS api
USER root
ENV UV_PROJECT_ENVIRONMENT=/app/.venv UV_CACHE_DIR=/root/.cache/uv PATH=/app/.venv/bin:$PATH PYDANTIC_AI_NO_BANNER=1 LAB_STATE_DIR=/data
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
CMD ["lab-api"]

FROM api AS agent
RUN apk add --no-cache docker-cli
CMD ["lab-agent"]
