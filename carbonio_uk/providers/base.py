"""Translation-provider interface. Providers receive English only as source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranslationRequest:
    component: str
    key: str
    english: str
    glossary: dict[str, str]
    context: str = "UI"


class TranslationProvider(Protocol):
    name: str

    def translate(self, request: TranslationRequest) -> str: ...
