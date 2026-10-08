"""Explicitly gated OpenAI Responses API provider for reviewed pilot rows."""

from __future__ import annotations

import json

from .base import TranslationRequest


class OpenAITranslationProvider:
    name = "openai"

    def __init__(self, model: str):
        if not model:
            raise ValueError("an explicit OpenAI model is required")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("install the optional `ai` dependency to execute the OpenAI pilot") from error
        self.model = model
        self.client = OpenAI()

    def translate(self, request: TranslationRequest) -> str:
        glossary = "\n".join(f"- {source}: {target}" for source, target in request.glossary.items()) or "(no matching terms)"
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Translate Carbonio UI text from English to Ukrainian. Preserve every placeholder name, "
                        "interpolation delimiter, HTML tag, API identifier, and protocol exactly. Return only the "
                        "structured result. Never translate from Russian."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Component: {request.component}\nKey: {request.key}\nEnglish: {request.english}\n"
                        f"Approved glossary context:\n{glossary}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "uk_translation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"translation": {"type": "string"}},
                        "required": ["translation"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        payload = json.loads(response.output_text)
        return str(payload["translation"])
