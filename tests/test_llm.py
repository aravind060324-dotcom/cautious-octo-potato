"""Ranking parser and the Groq-compatible chat client. No live network calls."""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.config import GROQ_MODEL, Settings
from app.recommender.llm import LlmError, OpenAiCompatibleClient, parse_ranking

SECRET_WISH = "family-friendly rooftop wish"
FAKE_KEY = "test-key-do-not-log"


def _settings(**overrides: object) -> Settings:
    fields: dict[str, object] = {
        "llm_base_url": "https://api.groq.com/openai/v1",
        "llm_api_key": FAKE_KEY,
        "llm_model": GROQ_MODEL,
    }
    fields.update(overrides)
    return Settings(_env_file=None, **fields)  # type: ignore[arg-type]


def _client(handler: httpx.MockTransport | object, **setting_overrides: object) -> OpenAiCompatibleClient:
    transport = handler if isinstance(handler, httpx.MockTransport) else httpx.MockTransport(handler)  # type: ignore[arg-type]
    http = httpx.Client(transport=transport)
    return OpenAiCompatibleClient(_settings(**setting_overrides), http_client=http)


def test_parse_raw_json_object():
    ranking = parse_ranking(
        json.dumps(
            {
                "summary": " Two places. ",
                "recommendations": [
                    {"id": "abc", "rank": 1, "explanation": " Fits. "},
                ],
            }
        )
    )

    assert ranking.summary == "Two places."
    assert ranking.items[0].id == "abc"
    assert ranking.items[0].rank == 1
    assert ranking.items[0].explanation == "Fits."


def test_parse_json_fence_with_leading_prose():
    text = """Here is the ranking:
```json
{"summary": "Short list.", "recommendations": [{"id": "abc", "rank": "2", "explanation": "Because"}]}
```
"""
    ranking = parse_ranking(text)

    assert ranking.summary == "Short list."
    assert ranking.items[0].id == "abc"
    assert ranking.items[0].rank == 2


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "I would recommend Onesta.",
        '{"summary": "Cut off"',
        '{"summary": "Only one field"}',
        '{"recommendations": []}',
        '{"summary": 4, "recommendations": []}',
        '{"summary": "Ok", "recommendations": {"id": "abc"}}',
    ],
)
def test_unparseable_output_raises(text: str):
    with pytest.raises(LlmError):
        parse_ranking(text)


def test_numeric_id_is_dropped_and_whitespace_explanation_is_empty():
    ranking = parse_ranking(
        json.dumps(
            {
                "summary": "Ok",
                "recommendations": [
                    {"id": 12345, "rank": 1, "explanation": "No"},
                    {"id": "abc", "rank": 2, "explanation": "  \n  "},
                ],
            }
        )
    )

    assert [item.id for item in ranking.items] == ["abc"]
    assert ranking.items[0].explanation == ""


def test_client_posts_groq_chat_completion_for_a_json_object():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content.decode())
        content = json.dumps({"summary": "Ok", "recommendations": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = _client(handler)
    text = client.complete(
        [
            {"role": "system", "content": "Reply with JSON."},
            {"role": "user", "content": SECRET_WISH},
        ]
    )

    assert text == json.dumps({"summary": "Ok", "recommendations": []})
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == f"Bearer {FAKE_KEY}"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == GROQ_MODEL
    assert body["temperature"] == 0.2
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][1]["content"] == SECRET_WISH


def test_client_logs_status_and_latency_without_the_prompt_or_key(caplog: pytest.LogCaptureFixture):
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"summary": "Ok", "recommendations": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = _client(handler)
    with caplog.at_level(logging.INFO, logger="app.recommender.llm"):
        client.complete([{"role": "user", "content": SECRET_WISH}])

    assert "status=200" in caplog.text
    assert "latency_ms=" in caplog.text
    assert SECRET_WISH not in caplog.text
    assert FAKE_KEY not in caplog.text


@pytest.mark.parametrize("status_code", [401, 429, 500])
def test_http_failure_raises(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "no"})

    client = _client(handler)
    with pytest.raises(LlmError, match=str(status_code)):
        client.complete([{"role": "user", "content": "hello"}])


def test_timeout_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = _client(handler)
    with pytest.raises(LlmError, match="timed out"):
        client.complete([{"role": "user", "content": "hello"}])


def test_missing_key_raises_without_a_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the client should not call the network")

    client = _client(handler, llm_api_key="")
    with pytest.raises(LlmError, match="API key"):
        client.complete([{"role": "user", "content": SECRET_WISH}])
