# Adapted from Assignment_1_Description.pdf §4.3 — multi-stage Cloud Run image
# with Node for the filesystem MCP server. Python packages are copied into the
# non-root user's home so the process can actually import them.

FROM python:3.13-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m appuser

COPY --from=build /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FILESYSTEM_ROOT=/app/workspace \
    MCP_SERVERS_CONFIG=/app/mcp_config.json \
    NPM_CONFIG_CACHE=/tmp/npm-cache \
    HOME=/home/appuser

COPY . .
# Install the filesystem MCP server into /app/node_modules so `npx` resolves it
# locally at startup instead of downloading it on every cold start.
RUN npm install --no-save --no-package-lock --no-audit --no-fund \
        @modelcontextprotocol/server-filesystem \
    && mkdir -p /app/workspace /tmp/npm-cache \
    && chown -R appuser:appuser /app /home/appuser /tmp/npm-cache

USER appuser
EXPOSE 8080
CMD ["python", "main.py"]
