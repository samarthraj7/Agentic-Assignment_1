# CSCI 599 Assignment 1 — Tool-using agent with MCP

LangGraph + FastAPI agent on Google Cloud Run. Talks to at least three
MCP servers, keeps conversation memory by `session_id`, and answers
`POST /chat`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put real keys in .env
```

## Run locally

```bash
source .venv/bin/activate
set -a && source .env && set +a
python main.py
```

```bash
curl -X POST http://localhost:8080/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"hello","session_id":"demo"}'
```

## Deploy

See `deploy.sh` (added in a later PR). Cloud Run region: `us-west1`.
GCP project: `csci-599-agenticai`.

## Architecture diagrams

_To be added: system architecture, tool invocation loop, deployment topology._
