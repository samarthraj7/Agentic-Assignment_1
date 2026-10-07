# Process log

## AI tools used

- Cursor (Grok 4.6) — wrote the FastAPI/LangGraph app, Dockerfile, deploy script, README diagrams
- OpenAI Codex CLI 0.155.1 — installed because the course mentioned it; I started a git skeleton there, then switched this work to Cursor
- NVIDIA NIM (`nvidia/nemotron-3-ultra-550b-a55b`) — the deployed agent LLM; I started on `nvidia/nemotron-3.5-lightning-30b-a3b` and switched (see below)
- Cursor (Claude) — final requirements cross-check, failure-mode tests, model comparison
- Homebrew / gcloud — machine setup, not code generation

## Development narrative

I first went through the assignment PDF line by line: Papa’s two rules (no fake MCP, no one-query deploy), the 25/25/20/20/10 rubric, and the process-log section. I picked LangGraph because the PDF calls it the tested path with FastAPI and `langchain-mcp-adapters`.

The prompt that actually produced the app was roughly: “LangGraph + FastAPI, three real MCP servers, MemorySaver keyed by session_id, do not hard-code tools, NVIDIA NIM + Tavily keys stay in .env.” Cursor drafted `main.py` from the langchain-mcp-adapters README (`MultiServerMCPClient` + `get_tools`) and the assignment Dockerfile.

What broke: Tavily’s remote MCP URL puts the key in the query string, and httpx logged it. I switched to `Authorization: Bearer` on `https://mcp.tavily.com/mcp/` so Cloud Run logs would not leak it. Filesystem MCP also needed the real `PATH` (nvm’s `npx`) merged into the stdio env; passing only `TAVILY_API_KEY` would have wiped PATH and `npx` would not start.

After that, `tools/list` returned 14 filesystem tools, 5 Tavily tools, and 8 Open-Meteo tools. Live calls: notes.txt → Trojan, LA weather from Open-Meteo, Tavily search for the current US president, and “what did I ask last?” on the same session_id.

Lightning kept skipping the weather tool, so I had added a regex retry that forced it. When I cross-checked against the rubric, that was exactly the "keyword matching" it penalizes, and the retry ran on a separate thread so memory lost the answer. I deleted it. Without the crutch, Lightning replied with a made-up `[ERROR: Tool ... failed]` on follow-ups like "and what about Los Angeles?" (4/4 times; logs showed no `CallToolRequest`). Prompt tweaks got it to 2/4. Nemotron 3 Ultra got 4/4, so I switched.

## Verification narrative

I did not stop at one curl. I ran `discover_tools()` and printed the inventory, then five agent turns: no-tool greeting, memory follow-up, filesystem read, weather, search. I hit `POST /chat` with a missing field to confirm we still return `{response}` instead of a stack trace. I also watched MCP logs for `ListToolsRequest` / `CallToolRequest` so I knew we were on the wire, not a stub.

To test failures, I started the server with `TAVILY_API_KEY=bad-key` and `PYTHON=/nonexistent/python`, which took down Tavily and Open-Meteo. `/health` still came up with filesystem's 14 tools and empty lists for the other two, and `/chat` said the tool wasn't available instead of crashing. Reading a missing file came back as a normal answer. `tests/test_chat.py` (pytest) covers the API contract, a dead stdio and HTTP server, a tool that raises, and a non-string tool result.

Final local run: Paris (no tool), notes.txt (filesystem), Bangalore then LA weather (two Open-Meteo calls), Tavily search → `filesystem_write_file` chain, "what did I ask last?" quoting the previous turn, and a second session_id that did not know my name.

## Attribution

- `main.py` — adapted from https://github.com/langchain-ai/langchain-mcp-adapters (`MultiServerMCPClient`, `get_tools`) and https://docs.langchain.com/oss/python/langgraph/overview (`create_react_agent` + `MemorySaver`).
- `Dockerfile` — adapted from the multi-stage Dockerfile in `Assignment_1_Description.pdf` §4.3.
- `deploy.sh` — adapted from the deploy commands in `Assignment_1_Description.pdf` §4.4.
- MCP servers used as external projects: `@modelcontextprotocol/server-filesystem`, Tavily remote MCP, `mcp_weather_server` (cited in README).

## What I learned

The adapter does `tools/list` and `tools/call` for you, but it will not save you from a bad stdio environment or from logging a key in a URL. Memory only works if you pass `thread_id=session_id` into the checkpointer — a dict on the FastAPI app would have been easier and would have lost the 20% memory points. Picking the model was also on me: the AI happily patched around Lightning's bad tool turns with retries, and only comparing models side by side showed the real fix.
