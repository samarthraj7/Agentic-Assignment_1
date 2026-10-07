#!/usr/bin/env bash
# Build and deploy csci599-a1 to Cloud Run. Keys come from the local .env
# file via --set-env-vars. Never put literal secrets in this script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and fill in keys first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

export OPENAI_API_KEY="${OPENAI_API_KEY:-${NVIDIA_API_KEY:-}}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://integrate.api.nvidia.com/v1}"
export OPENAI_MODEL="${OPENAI_MODEL:-nvidia/nemotron-3-ultra-550b-a55b}"
PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID missing in .env}"

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud builds submit --tag "gcr.io/${PROJECT}/csci599-a1"

gcloud run deploy csci599-a1 \
  --image "gcr.io/${PROJECT}/csci599-a1" \
  --platform managed \
  --region us-west1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 1 \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY},OPENAI_BASE_URL=${OPENAI_BASE_URL},OPENAI_MODEL=${OPENAI_MODEL},NVIDIA_API_KEY=${NVIDIA_API_KEY:-},TAVILY_API_KEY=${TAVILY_API_KEY},FILESYSTEM_ROOT=/app/workspace,MCP_SERVERS_CONFIG=/app/mcp_config.json,PYTHON=python"
