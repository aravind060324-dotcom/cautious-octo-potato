"""Groq chat client and the ranking parser.

Groq speaks the OpenAI chat-completions API. ``Settings`` supplies
``https://api.groq.com/openai/v1`` and the model. This module posts to
``{llm_base_url}/chat/completions`` and does not log preference text.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class LlmError(RuntimeError):
    """The model call timed out, failed, or returned unusable output."""


class LlmClient(Protocol):
    """One chat completion. Tests substitute a fake that returns canned text."""

    def complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        """Return the assistant text from one completion."""


@dataclass(frozen=True)
class RankedItem:
    """One id the model asked to show, before catalog checks."""

    id: str
    rank: int | None
    explanation: str


@dataclass(frozen=True)
class Ranking:
    """Parsed model payload. Ids are not yet checked against the catalog."""

    summary: str
    items: list[RankedItem]


class OpenAiCompatibleClient:
    """POST one JSON chat completion to an OpenAI-compatible host such as Groq."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._http = http_client

    def complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        settings = self._settings
        if not settings.llm_base_url.strip():
            raise LlmError("A model base URL is required for a live call")
        if not settings.llm_api_key.strip():
            raise LlmError("A model API key is required for a live call")
        if not settings.llm_model.strip():
            raise LlmError("A model name is required for a live call")

        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [dict(message) for message in messages],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        started = time.perf_counter()
        status: object = "error"
        try:
            try:
                response = self._post(url, payload, headers)
            except httpx.TimeoutException as exc:
                status = "timeout"
                raise LlmError("Model request timed out") from exc
            except httpx.HTTPError as exc:
                status = "error"
                raise LlmError("Model request failed") from exc
            status = response.status_code
            if response.status_code >= 400:
                raise LlmError(f"Model request failed with status {response.status_code}")
            return _message_text(response)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info("llm completion status=%s latency_ms=%.0f", status, elapsed_ms)

    def _post(self, url: str, payload: dict[str, object], headers: dict[str, str]) -> httpx.Response:
        timeout = httpx.Timeout(self._settings.llm_timeout_seconds)
        if self._http is not None:
            return self._http.post(url, json=payload, headers=headers, timeout=timeout)
        with httpx.Client(timeout=timeout) as http:
            return http.post(url, json=payload, headers=headers)


def parse_ranking(text: str) -> Ranking:
    """Parse a raw JSON object or a string wrapped in a ```json fence."""
    if not isinstance(text, str) or not text.strip():
        raise LlmError("Model output was empty")
    raw = text.strip()
    if "```" in raw:
        match = _FENCE.search(raw)
        if match is None or not match.group(1).strip():
            raise LlmError("Model output was not valid JSON")
        raw = match.group(1).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmError("Model output was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise LlmError("Model output was not a JSON object")
    if "summary" not in payload or "recommendations" not in payload:
        raise LlmError("Model output is missing summary or recommendations")
    summary = payload["summary"]
    recommendations = payload["recommendations"]
    if not isinstance(summary, str) or not isinstance(recommendations, list):
        raise LlmError("Model output has the wrong shape")
    items: list[RankedItem] = []
    for entry in recommendations:
        item = _ranked_item(entry)
        if item is not None:
            items.append(item)
    return Ranking(summary=summary.strip(), items=items)


def _ranked_item(entry: object) -> RankedItem | None:
    if not isinstance(entry, dict) or "id" not in entry:
        return None
    identity = _identity(entry.get("id"))
    if identity is None:
        return None
    explanation = entry.get("explanation", "")
    if not isinstance(explanation, str):
        explanation = ""
    return RankedItem(id=identity, rank=_rank(entry.get("rank")), explanation=explanation.strip())


def _identity(value: object) -> str | None:
    """Keep a string id. A JSON number is dropped so it cannot match a catalog id."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _rank(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _message_text(response: httpx.Response) -> str:
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LlmError("Model response did not include a completion") from exc
    if not isinstance(content, str):
        raise LlmError("Model response did not include a completion")
    return content
