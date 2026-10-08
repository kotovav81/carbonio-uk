"""Deterministic offline provider used only by tests and workflow rehearsals."""

from __future__ import annotations

from .base import TranslationRequest


class MockTranslationProvider:
    name = "mock"

    def translate(self, request: TranslationRequest) -> str:
        return f"[MOCK UK:{request.component}:{request.key}] {request.english}"
