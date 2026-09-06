from __future__ import annotations

from typing import Protocol, runtime_checkable

from .schemas import SearchContext, SearchHit


@runtime_checkable
class SearchProvider(Protocol):
    provider_code: str

    def search(self, context: SearchContext) -> list[SearchHit]: ...
