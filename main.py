"""CSCI 599 Assignment 1 — LangGraph agent with real MCP tools.

Adapted from https://github.com/langchain-ai/langchain-mcp-adapters — MultiServerMCPClient
loads tools via MCP tools/list and invokes them via tools/call.

Adapted from https://docs.langchain.com/oss/python/langgraph/overview — create_react_agent
plus MemorySaver checkpointer keyed by session_id.

Adapted from Assignment_1_Description.pdf §4.3 — Cloud Run PORT binding and Docker layout.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from mcp.client.stdio import get_default_environment
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("csci599")

ENV_REF = re.compile(r"\$\{([^}]+)\}")
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
SYSTEM_PROMPT = """You are a helpful CSCI 599 agent with three real MCP servers:

- filesystem: read and write files under the workspace root only.
- tavily: live web search for current facts, news, and research.
- open-meteo: live weather via Open-Meteo. No API key. This tool works.

Rules:
- Weather / forecast / temperature questions → open-meteo. Each new city or follow-up needs its own fresh tool call.
- File questions → filesystem. Research / current events → tavily.
- Chain two or more tools when the question needs it (example: search, then write a short file).
- If no tool is needed (greetings, general knowledge, "what did I ask last?"), answer from conversation memory. Do not force a tool call.
- "What did I ask last?" means the user's previous message in this conversation, not the current one. Quote that earlier message. If there is none, say so.
- If a tool fails, say so briefly and still answer with what you have. Never invent a fake tool result.
- Keep answers concise. Do not repeat the same word or fragment.
"""

# Open-Meteo geocodes "Bangalore" to a town in Pakistan; "Bengaluru" is India.
CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "bengalooru": "Bengaluru",
    "bangaluru": "Bengaluru",
}

class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class ChatResponse(BaseModel):
    response: str


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_REF.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def load_mcp_connections() -> dict[str, dict[str, Any]]:
    """Build MultiServerMCPClient connections from mcp_config.json."""
    os.environ.setdefault("FILESYSTEM_ROOT", str(ROOT / "workspace"))
    os.environ.setdefault("PYTHON", sys.executable)
    os.environ.setdefault("APP_ROOT", str(ROOT))

    config_path = Path(os.getenv("MCP_SERVERS_CONFIG", str(ROOT / "mcp_config.json")))
    if not config_path.is_file():
        config_path = ROOT / "mcp_config.json"
    raw = json.loads(config_path.read_text())
    servers = raw.get("mcpServers", raw)

    connections: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        expanded = _expand(spec)
        if expanded.get("transport") == "stdio":
            env = get_default_environment()
            extra = expanded.get("env") or {}
            env.update(extra)
            # npx on this Mac lives under nvm; PATH must include it.
            env["PATH"] = os.environ.get("PATH", env.get("PATH", ""))
            expanded["env"] = env
        connections[name] = expanded
        log.info("configured MCP server %s transport=%s", name, expanded.get("transport"))
    return connections


def _normalize_city(kwargs: dict[str, Any]) -> dict[str, Any]:
    city = kwargs.get("city")
    if isinstance(city, str):
        mapped = CITY_ALIASES.get(city.strip().lower())
        if mapped:
            kwargs = {**kwargs, "city": mapped}
    return kwargs


def wrap_tool(tool: BaseTool) -> BaseTool:
    """Turn transport / parse failures into a string the agent can recover from."""

    async def _run(**kwargs: Any) -> str:
        kwargs = _normalize_city(kwargs)
        try:
            result = await tool.ainvoke(kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, default=str)
        except Exception as exc:  # noqa: BLE001 — must not crash the agent loop
            log.exception("MCP tools/call failed for %s", tool.name)
            return (
                f"Tool '{tool.name}' failed ({type(exc).__name__}): {exc}. "
                "Continue without this result."
            )

    return StructuredTool.from_function(
        coroutine=_run,
        name=tool.name,
        description=tool.description or tool.name,
        args_schema=tool.args_schema,
    )


def message_text(message: BaseMessage | Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def is_garbled(text: str) -> bool:
    words = re.findall(r"\S+", text)
    if len(words) < 8:
        return False
    _token, count = Counter(words).most_common(1)[0]
    return count >= 12 and count / len(words) > 0.35


def build_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY or NVIDIA_API_KEY in .env")
    # NVIDIA NIM is OpenAI-compatible. Nemotron 3.5 Lightning invented fake
    # "[ERROR: Tool ... failed]" replies on follow-up tool turns; Ultra does not.
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        temperature=0.2,
        max_tokens=2048,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


async def discover_tools(connections: dict[str, dict[str, Any]]) -> tuple[list[BaseTool], dict[str, list[str]]]:
    """Call MCP tools/list per server. One dead server must not kill the rest."""
    inventory: dict[str, list[str]] = {}
    tools: list[BaseTool] = []
    client = MultiServerMCPClient(
        connections,
        handle_tool_errors=True,
        tool_name_prefix=True,
    )
    for name in connections:
        try:
            loaded = await client.get_tools(server_name=name)
            inventory[name] = [item.name for item in loaded]
            tools.extend(wrap_tool(item) for item in loaded)
            log.info("MCP tools/list %s -> %s", name, inventory[name])
        except Exception as exc:  # noqa: BLE001
            inventory[name] = []
            log.exception("MCP tools/list failed for %s: %s", name, exc)
    return tools, inventory


async def build_agent():
    connections = load_mcp_connections()
    tools, inventory = await discover_tools(connections)
    llm = build_llm()
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
        name="csci599-a1",
    )
    return agent, inventory


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent, inventory = await build_agent()
    app.state.agent = agent
    app.state.mcp_inventory = inventory
    yield


app = FastAPI(title="CSCI 599 Assignment 1", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse({"response": f"Invalid request: {exc.errors()}"}, status_code=400)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "CSCI 599 Assignment 1 agent",
        "chat": 'POST /chat {"query": string, "session_id": string}',
        "health": "GET /health",
        "docs": "GET /docs",
        "latency": "First request after idle can take ~30s (cold start); tool queries usually 5-15s.",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    inventory = getattr(app.state, "mcp_inventory", {})
    return {"ok": True, "mcp_servers": inventory}


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse | JSONResponse:
    agent = getattr(app.state, "agent", None)
    if agent is None:
        return JSONResponse({"response": "Agent is still starting. Try again."}, status_code=503)
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=body.query)]},
            config={
                "configurable": {"thread_id": body.session_id},
                "recursion_limit": 12,
            },
        )
        messages = result.get("messages") or []
        finals = [m for m in messages if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)]
        text = message_text(finals[-1]) if finals else ""
        if not text or is_garbled(text):
            text = "I could not produce a clean response. Please try that question again."
        return ChatResponse(response=text)
    except Exception as exc:  # noqa: BLE001 — assignment: never crash the HTTP server
        log.exception("chat failed")
        return JSONResponse(
            {"response": f"The agent hit an error and recovered: {type(exc).__name__}: {exc}"}
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
