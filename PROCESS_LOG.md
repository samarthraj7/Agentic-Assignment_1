# Process log

## AI tools used

- Cursor (Grok 4.6) — wrote the FastAPI/LangGraph app, Dockerfile, deploy script, README diagrams
- OpenAI Codex CLI 0.155.1 — installed because the course mentioned it; I started a git skeleton there, then switched this work to Cursor
- NVIDIA NIM (`nvidia/nemotron-3-ultra-550b-a55b`) — the deployed agent LLM; I started on `nvidia/nemotron-3.5-lightning-30b-a3b` and switched (see below)
- Cursor (Claude) — final requirements cross-check, failure-mode tests, model comparison, reading Cloud Run logs
- Homebrew / gcloud — machine setup, not code generation

## Development narrative

I first went through the assignment PDF line by line: Papa’s two rules (no fake MCP, no one-query deploy), the 25/25/20/20/10 rubric, and the process-log section. I picked LangGraph because the PDF calls it the tested path with FastAPI and `langchain-mcp-adapters`.

The prompt that actually produced the app was roughly: “LangGraph + FastAPI, three real MCP servers, MemorySaver keyed by session_id, do not hard-code tools, NVIDIA NIM + Tavily keys stay in .env.” Cursor drafted `main.py` from the langchain-mcp-adapters README (`MultiServerMCPClient` + `get_tools`) and the assignment Dockerfile.

What broke: Tavily’s remote MCP URL puts the key in the query string, and httpx logged it. I switched to `Authorization: Bearer` on `https://mcp.tavily.com/mcp/` so Cloud Run logs would not leak it. Filesystem MCP also needed the real `PATH` (nvm’s `npx`) merged into the stdio env; passing only `TAVILY_API_KEY` would have wiped PATH and `npx` would not start.

After that, `tools/list` returned 14 filesystem tools, 5 Tavily tools, and 8 Open-Meteo tools. Live calls: notes.txt → Trojan, LA weather from Open-Meteo, Tavily search for the current US president, and “what did I ask last?” on the same session_id.

Lightning kept skipping the weather tool, so I had added a regex retry that forced it. When I cross-checked against the rubric, that was exactly the "keyword matching" it penalizes, and the retry ran on a separate thread so memory lost the answer. I deleted it. Without the crutch, Lightning replied with a made-up `[ERROR: Tool ... failed]` on follow-ups like "and what about Los Angeles?" (4/4 times; logs showed no `CallToolRequest`). Prompt tweaks got it to 2/4. Nemotron 3 Ultra got 4/4, so I switched.

## Debugging log — what went wrong and how I fixed it

Each entry is: what I saw, the evidence (terminal or Cloud Run logs), and the fix. No keys are shown; anything secret is replaced with `<XXX_KEY_HERE>`.

### 1. Tavily key showing up in logs

Tavily's docs give a URL like `https://mcp.tavily.com/mcp/?tavilyApiKey=<XXX_KEY_HERE>`. httpx logs every request URL at INFO, so the key would land in Cloud Run logs. I moved it into a header in `mcp_config.json`:

```json
"tavily": {
  "transport": "http",
  "url": "https://mcp.tavily.com/mcp/",
  "headers": { "Authorization": "Bearer ${TAVILY_API_KEY}" }
}
```

Now the log line is just `HTTP Request: POST https://mcp.tavily.com/mcp/ "HTTP/1.1 200 OK"`.

### 2. Filesystem MCP would not start (`npx` not found)

Passing an `env` to a stdio server replaces the whole environment, so `npx` (installed under nvm on my Mac) disappeared from `PATH`. Fix in `load_mcp_connections()`:

```python
env = get_default_environment()
env.update(expanded.get("env") or {})
env["PATH"] = os.environ.get("PATH", env.get("PATH", ""))
```

### 3. Keyword-forced weather retry (removed)

My old `/chat` had this, which I deleted after the rubric check:

```python
needs_weather = bool(WEATHER_RE.search(body.query))
if (needs_weather and not used_mcp_tool(messages)) or is_garbled(text):
    messages, text = await _run_turn(agent, nudge, f"{body.session_id}-wx")
```

Two problems: it is keyword matching (rubric 7.2 "no credit"), and the `-wx` thread meant the retried answer never landed in the user's session memory.

### 4. Nemotron 3.5 Lightning inventing tool errors

Two-turn probe (Bangalore weather, then "And what about in Los Angeles?"), run 4 times per variant. The local server log showed only one `CallToolRequest` per conversation, so the second "error" was made up by the model, not returned by Open-Meteo:

```
0 AIMessage  '[ERROR: Tool open-meteo_get_current_weather not found in agent OSS-Assistant]'
1 AIMessage  '[ERROR: Tool open-meteo_get_current_weather failed]'
```

| Variant | Follow-up answered correctly |
|---|---|
| Lightning, original prompt | 0/4 |
| Lightning, strip text from tool-call messages | 0/4 |
| Lightning, plain-text tool results | 1/4 |
| Lightning, extra prompt rule | 2/4 |
| Lightning, plain text + prompt rule | 2/4 |
| **Nemotron 3 Ultra, original prompt** | **4/4** |

Fix: `DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"` in `main.py`, `deploy.sh`, and `.env.example`.

### 5. "What did I ask you last?" quoted the current question

Live answer before the fix: `You asked: "What did I ask you last? And what's my favorite color?"`. I added one line to the system prompt:

```
- "What did I ask last?" means the user's previous message in this conversation, not the current one. Quote that earlier message. If there is none, say so.
```

After: `Your last message was: "My favorite city is Tokyo. What is 12 times 12?"`.

### 6. Slow cold starts / first request returned a Google 500 page

The first live request after idle returned Cloud Run's HTML `500 Server Error`, and `/health` took 25 s. `npx -y` was downloading `@modelcontextprotocol/server-filesystem` from npm on every new instance. I install it into the image instead, so `npx` resolves it from `/app/node_modules`:

```dockerfile
RUN npm install --no-save --no-package-lock --no-audit --no-fund \
        @modelcontextprotocol/server-filesystem
```

and set `"cwd": "${APP_ROOT}"` on the filesystem server in `mcp_config.json`. After this the filesystem server is ready 3.4 s into startup (see latency table).

### 7. `./deploy.sh` → `permission denied`

```
$ ls -l deploy.sh
-rw-r--r--  1 samarth_raj  staff  1342  deploy.sh
$ git ls-files -s deploy.sh
100644 4e53238...  deploy.sh
```

The script was never executable, locally or in git. Fix: `chmod +x deploy.sh` and `git update-index --chmod=+x deploy.sh` (now `100755`).

### 8. `gcloud services enable` → `AUTH_PERMISSION_DENIED`

```
reason: AUTH_PERMISSION_DENIED
permission: serviceusage.services.enable
```

`gcloud auth list` showed the active account had switched to my USC account, which has no role on `csci-599-agenticai` (even `gcloud projects describe` was denied). My Gmail account is `roles/owner`, and all three APIs were already enabled. Fix: `gcloud config set account <my gmail>`, then `./deploy.sh` worked (revision `csci599-a1-00004-mxk`).

### 9. "Live URL doesn't show anything"

Opening the bare URL in a browser gave `{"detail":"Not Found"} [HTTP 404]` because only `POST /chat` and `GET /health` existed, and `curl -s` prints nothing until the agent finishes, which looked like a hang. I added a `GET /` usage page and a latency note in the README:

```python
@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "CSCI 599 Assignment 1 agent", "chat": 'POST /chat {"query": string, "session_id": string}', ...}
```

### 10. Memory lost on the second turn right after a cold start

On Oct 12, after the service had been idle, my two-turn memory test failed: turn 2 said "this is the first turn in our conversation." Run on a warm instance a minute later, the same test passed. The Cloud Run request logs (times UTC, instance ID shortened) showed why:

```
19:58:26.104 e86216 GET / 200 18.235722406s
19:58:26.137 e86216 Starting new instance. Reason: AUTOSCALING
19:58:44.554 e86216 INFO:     Application startup complete.
19:58:45.137 e86216 POST /chat 200 12.787417596s      <- turn 1
19:58:55.626 61b801 Starting new instance. Reason: AUTOSCALING
19:58:58.024 e86216 INFO:     Shutting down
19:59:17.032 61b801 INFO:     Application startup complete.   <- turn 2 served here
```

Cloud Run replaced the first instance about 30 s after it started, and turn 2 went to a fresh instance with an empty `MemorySaver`. I checked for `severity>=WARNING` and for `Memory limit` messages in that window: none, so it was not an out-of-memory crash or an app error. The live config is `maxScale=1`, `memory=512Mi`, `startup-cpu-boost=true`. The assignment says in-memory state "may be lost when Cloud Run stops or replaces the instance", so I left the code alone and did not use `--min-instances 1` (not allowed here). Once the instance has settled, memory holds across turns.

## Latency measurements

Cold start, from the Cloud Run logs above (one instance, Oct 12):

| Step | Time |
|---|---|
| Instance start → Python imports + uvicorn up | 11.0 s |
| Filesystem MCP `tools/list` (14 tools) | 3.4 s |
| Tavily MCP `tools/list` (5 tools, remote HTTP) | 0.8 s |
| Open-Meteo MCP `tools/list` (8 tools) | 2.7 s |
| Build agent → "Application startup complete" | 0.5 s |
| **Total, first request after idle** | **18.2 s** |

Warm requests against the live URL (`curl -w '%{time_total}'`):

| Request | Tools used | Time |
|---|---|---|
| `GET /` | — | 0.12 s |
| `GET /health` | — | 0.07 s |
| "What is 12 times 12?" | none | 1.3 s |
| "What did I ask you last…?" | none (memory) | 1.0 s |
| "Weather in my favorite city?" | Open-Meteo | 6.6 s |
| "Best trek in California?" (long answer) | none | 13.1 s |
| Turn 2 that landed on the replacement instance | none | 20.8 s |

Local (my Mac, same NIM backend): Nemotron 3 Ultra averaged about 10 s per turn over 8 weather turns (77 s total, including MCP startup). The 7-turn final check, which included a Tavily → filesystem chain, took 55 s.

Deploy: `./deploy.sh` took 228 s end to end. Cloud Build plus the new revision was about 3 minutes (build at 00:13 UTC, revision `00004-mxk` at 00:16 UTC).

## Verification narrative

I did not stop at one curl. I ran `discover_tools()` and printed the inventory, then five agent turns: no-tool greeting, memory follow-up, filesystem read, weather, search. I hit `POST /chat` with a missing field to confirm we still return `{response}` instead of a stack trace:

```
{"response":"Invalid request: [{'type': 'missing', 'loc': ('body', 'session_id'), 'msg': 'Field required', ...}]"}
```

I also watched MCP logs for `ListToolsRequest` / `CallToolRequest` so I knew we were on the wire, not a stub.

To test failures, I started the server with `TAVILY_API_KEY=bad-key` and `PYTHON=/nonexistent/python`, which took down Tavily and Open-Meteo:

```
ERROR csci599: MCP tools/list failed for tavily: unhandled errors in a TaskGroup (1 sub-exception)
ERROR csci599: MCP tools/list failed for open-meteo: [Errno 2] No such file or directory: '/nonexistent/python'
{"ok":true,"mcp_servers":{"filesystem":["filesystem_read_file", ...],"tavily":[],"open-meteo":[]}}
```

`/chat` then said the search/weather tool wasn't available instead of crashing, and reading a missing file came back as a normal answer. `tests/test_chat.py` (pytest, 6 tests) covers the API contract and root page, a dead stdio and HTTP server, a tool that raises, and a non-string tool result.

Final local run: Paris (no tool), notes.txt (`filesystem_read_text_file`), Bangalore then LA weather (two `open-meteo_get_current_weather` calls), `tavily_tavily_search` → `filesystem_write_file` chain, "what did I ask last?" quoting the previous turn, and a second session_id that did not know my name. On the live URL I repeated the memory test on a warm instance and checked the Cloud Run logs when the cold one failed (debugging entry 10).

## Attribution

- `main.py` — adapted from https://github.com/langchain-ai/langchain-mcp-adapters (`MultiServerMCPClient`, `get_tools`) and https://docs.langchain.com/oss/python/langgraph/overview (`create_react_agent` + `MemorySaver`).
- `Dockerfile` — adapted from the multi-stage Dockerfile in `Assignment_1_Description.pdf` §4.3.
- `deploy.sh` — adapted from the deploy commands in `Assignment_1_Description.pdf` §4.4.
- MCP servers used as external projects: `@modelcontextprotocol/server-filesystem`, Tavily remote MCP, `mcp_weather_server` (cited in README).

## What I learned

The adapter does `tools/list` and `tools/call` for you, but it will not save you from a bad stdio environment or from logging a key in a URL. Memory only works if you pass `thread_id=session_id` into the checkpointer — a dict on the FastAPI app would have been easier and would have lost the 20% memory points. Debugging was also on me: the AI happily patched around Lightning's bad tool turns with retries until I compared models side by side, and the Cloud Run logs, not the code, explained the one time memory was lost.
