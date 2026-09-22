# How to build this assignment in Codex

Work **one branch / one PR at a time**. After Codex finishes a phase,
you review, commit, then start the next branch.

```bash
cd ~/Agentic
source .venv/bin/activate
```

Start Codex from this folder:

```bash
codex
```

If sign-in fails, use Chrome, log into chatgpt.com with your **USC**
account, then:

```bash
codex login
```

---

## PR 1 — HTTP shell

```bash
git checkout main
git checkout -b feat/http-chat
codex
```

Paste:

> Read AGENTS.md and Assignment_1_Description.pdf. Create main.py as a
> FastAPI app with POST /chat matching the assignment JSON contract.
> Read PORT from the environment, bind 0.0.0.0, load .env with
> python-dotenv. For now the agent can return a placeholder string.
> Add Dockerfile (python:3.13-slim multi-stage, non-root, Node for npx)
> and deploy.sh using project csci-599-agenticai, region us-west1,
> gcr.io image csci599-a1. Do not put secrets in the files. Do not
> deploy yet.

Then:

```bash
git add -A && git commit -m "Add FastAPI /chat shell, Dockerfile, and deploy script"
git push -u origin HEAD
gh pr create --title "PR 1: HTTP /chat shell" --body "FastAPI endpoint, Docker, deploy.sh. No MCP yet."
```

---

## PR 2 — MCP tools

```bash
git checkout main && git pull
git checkout -b feat/mcp-servers
codex
```

Paste:

> Wire LangGraph to at least three real MCP servers via
> langchain-mcp-adapters: filesystem, Tavily search, and Open-Meteo
> weather. Use tools/list and tools/call. No hard-coded tool results.
> Add mcp_config.json. Handle connection failures, tool errors, and
> bad responses without crashing. Keep POST /chat the same.

```bash
git add -A && git commit -m "Integrate filesystem, Tavily, and weather MCP servers"
git push -u origin HEAD
gh pr create --title "PR 2: MCP servers" --body "Real MCP tool discovery and invocation."
```

---

## PR 3 — Memory

```bash
git checkout main && git pull
git checkout -b feat/memory
codex
```

Paste:

> Add LangGraph checkpointer memory keyed by request session_id.
> Same session_id must remember prior turns. Different session_id
> must stay isolated. Do not use a custom dict.

```bash
git add -A && git commit -m "Add LangGraph session memory"
git push -u origin HEAD
gh pr create --title "PR 3: Conversational memory" --body "Checkpointer keyed by session_id."
```

---

## PR 4 — Docs, log, deploy

```bash
git checkout main && git pull
git checkout -b feat/docs-deploy
codex
```

Paste:

> Update README.md with setup, run, deploy, cost note, and three
> diagrams that match THIS repo (system, tool-call loop with
> loop-back, Cloud Run topology). Help me fill PROCESS_LOG.md with
> prompts I actually used, but keep it in first person so I can
> rewrite it. Then walk me through deploy.sh against
> csci-599-agenticai in us-west1. Do not print secret values.

```bash
git add -A && git commit -m "Add diagrams, process log notes, and Cloud Run deploy"
git push -u origin HEAD
gh pr create --title "PR 4: Docs and Cloud Run deploy" --body "README diagrams, process log, live URL."
```

---

## Rules while Codex is working

- Watch the files it changes. If it fakes MCP tools, stop it.
- After each phase, try the code yourself before the next PR.
- Write PROCESS_LOG.md in your own words before submit.
