# CSCI 599 Assignment 1 — Codex instructions

Individual assignment. Do the work in this repo. Prefer small commits
and one pull request per phase.

## Goal

Build a LangGraph agent (FastAPI) that:

- Exposes `POST /chat` with `{ "query": string, "session_id": string }`
  and returns `{ "response": string }`
- Reads `PORT` from the environment (default 8080) and binds `0.0.0.0`
- Integrates **at least 3 MCP servers** with real `tools/list` and
  `tools/call` (not fake/hard-coded tool results)
  1. Filesystem MCP (`@modelcontextprotocol/server-filesystem`)
  2. Tavily Search MCP
  3. One extra (Open-Meteo weather, fetch, sqlite, or GitHub)
- Uses LangGraph checkpointer memory keyed by `session_id`
- Handles MCP connection failures, tool errors, and bad responses
  without crashing
- Deploys to Google Cloud Run (`us-west1`, project `csci-599-agenticai`)

Full spec: `Assignment_1_Description.pdf`.

## Stack (already chosen)

- Python 3.13/3.14, FastAPI, Uvicorn
- LangGraph + `langchain-mcp-adapters` + `langchain-openai`
- Local venv: `.venv` (activate before running)
- GCP project: `csci-599-agenticai`
- Region: `us-west1`

## Do

- Keep API keys in `.env` only. Never commit `.env`.
- Commit `.env.example` with placeholders.
- Attribute copied/adapted code: `# Adapted from <url> — <why>`
- Name MCP servers by real name in README diagrams (not "Server 1")
- Leave the Cloud Run service running after deploy (`--min-instances 0`,
  `--max-instances 1`, `--memory 512Mi`, `--allow-unauthenticated`)

## Do not

- Hard-code tool responses
- Deploy Ollama to Cloud Run (local testing only)
- Put keys in source, Dockerfiles, or `deploy.sh`
- Prefix files with `A1_`
- Use a custom dict for memory (must be LangGraph checkpointer)

## Deliverables

- `main.py`, `README.md`, `PROCESS_LOG.md`, `deploy.sh`, Dockerfile
- Live Cloud Run URL
- Three architecture diagrams in README (system, tool loop, deploy)
