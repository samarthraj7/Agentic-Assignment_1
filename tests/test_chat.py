import asyncio

from fastapi.testclient import TestClient
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from main import ChatRequest, ChatResponse, app, discover_tools, message_text, wrap_tool


class CityArgs(BaseModel):
    city: str


def test_dead_server_does_not_block_others() -> None:
    connections = {
        "dead": {"transport": "stdio", "command": "definitely-not-a-real-binary", "args": []},
        "dead-http": {"transport": "http", "url": "http://127.0.0.1:9/mcp/"},
    }
    tools, inventory = asyncio.run(discover_tools(connections))
    assert tools == []
    assert inventory == {"dead": [], "dead-http": []}


def test_tool_error_becomes_message() -> None:
    async def boom(city: str) -> str:
        raise RuntimeError("upstream 500")

    tool = StructuredTool.from_function(coroutine=boom, name="wx", description="x", args_schema=CityArgs)
    out = asyncio.run(wrap_tool(tool).ainvoke({"city": "Bangalore"}))
    assert "failed (RuntimeError)" in out


def test_non_string_result_is_serialized() -> None:
    async def echo(city: str) -> dict:
        return {"city": city}

    tool = StructuredTool.from_function(coroutine=echo, name="wx", description="x", args_schema=CityArgs)
    out = asyncio.run(wrap_tool(tool).ainvoke({"city": "Bangalore"}))
    assert out == '{"city": "Bengaluru"}'


def test_message_text_plain() -> None:
    class Dummy:
        content = "hello"

    assert message_text(Dummy()) == "hello"


def test_request_models() -> None:
    req = ChatRequest(query="hi", session_id="s1")
    assert req.query == "hi"
    assert ChatResponse(response="ok").response == "ok"


def test_health_and_chat_contract() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["ok"] is True
        for name in ("filesystem", "tavily", "open-meteo"):
            assert name in body["mcp_servers"]

        assert "chat" in client.get("/").json()

        bad = client.post("/chat", json={"query": ""})
        assert bad.status_code == 400
        assert "response" in bad.json()
