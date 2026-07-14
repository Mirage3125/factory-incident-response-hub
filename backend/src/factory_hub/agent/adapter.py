from __future__ import annotations

import json
from typing import Any

import httpx

from factory_hub.config import Settings


class OpenAICompatibleAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise RuntimeError("missing_llm_api_key")
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        body = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        return json.loads(content)
