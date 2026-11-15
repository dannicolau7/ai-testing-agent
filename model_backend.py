"""
model_backend.py — which model, if any, the tool talks to.

Three ways to run, in the order they are tried:

1. A local model          ATA_MODEL_URL=http://localhost:11434/v1   (free; nothing leaves the machine)
2. The Anthropic API      ANTHROPIC_API_KEY=...                     (paid per use; best results)
3. No model               everything that reads source still works: audit, trace, validate

A "local model" is any server that speaks the OpenAI chat-completions protocol: Ollama,
llama.cpp's server, LM Studio, vLLM. Set ATA_MODEL_NAME to the model's name on that server
(for example llama3.2) and, if the server wants one, ATA_MODEL_KEY.

The URL does not have to be on this machine. If it is not, the code and requirements in a
prompt go to whoever runs that server; `describe()` says where prompts are sent so a report
can state it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse


class ModelError(RuntimeError):
    """The model could not be reached or gave no usable answer."""


class LocalBackend:
    """An OpenAI-compatible chat-completions server."""

    kind = "local"

    def __init__(self, base_url: str, model: str = "", key: str = "", timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        self.model = model or "local"
        self.key = key
        self.timeout = timeout

    @property
    def on_this_machine(self) -> bool:
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local")

    def describe(self) -> str:
        where = "on this machine" if self.on_this_machine else f"at {urlparse(self.base_url).hostname}"
        return f"model `{self.model}` {where}"

    def complete(self, prompt: str, max_tokens: int = 4000, json_only: bool = False) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        if json_only:
            body["response_format"] = {"type": "json_object"}
        try:
            return self._post(body)
        except ModelError as exc:
            # Some servers do not know response_format; ask again without it.
            if json_only and "400" in str(exc):
                body.pop("response_format")
                return self._post(body)
            raise

    def _post(self, body: dict) -> str:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - URL set by the user
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ModelError(f"The model server answered {exc.code} at {self.base_url}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ModelError(f"Could not reach a model at {self.base_url}: {exc}") from exc
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("The model server's answer was not in the expected form") from exc
        if not isinstance(text, str) or not text.strip():
            raise ModelError("The model returned an empty answer")
        return text


class AnthropicBackend:
    kind = "anthropic"

    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or os.getenv("ATA_ANTHROPIC_MODEL") or "claude-haiku-4-5-20251001"

    def describe(self) -> str:
        return f"model `{self.model}` through the Anthropic API"

    def complete(self, prompt: str, max_tokens: int = 4000, json_only: bool = False) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise ModelError("The anthropic package is not installed: pip install anthropic") from exc
        try:
            message = anthropic.Anthropic(api_key=self.api_key).messages.create(
                model=self.model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        except Exception as exc:  # noqa: BLE001 - every SDK failure becomes one error type
            raise ModelError(f"The Anthropic API call failed: {str(exc)[:200]}") from exc
        return "".join(
            block.text for block in message.content
            if getattr(block, "type", "text") == "text" and isinstance(getattr(block, "text", None), str))


def resolve(api_key: Optional[str] = None, env: Optional[dict] = None):
    """The backend the settings ask for, or None to run without a model.

    A local model wins when both are set: it is the choice that costs nothing and sends
    nothing out, so nobody is billed by surprise.
    """
    env = os.environ if env is None else env
    url = (env.get("ATA_MODEL_URL") or "").strip()
    if url:
        return LocalBackend(url, env.get("ATA_MODEL_NAME", ""), env.get("ATA_MODEL_KEY", ""))
    key = api_key or env.get("ANTHROPIC_API_KEY")
    if key:
        return AnthropicBackend(key)
    return None
