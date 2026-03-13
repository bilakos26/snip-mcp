"""ContextProvider ABC and registry for discovering and loading context providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColumnMetadata:
    """Metadata about a column in a SQL table/view/model."""

    name: str
    description: str = ""
    data_type: str = ""
    table: str = ""
    source_file: str = ""
    tags: tuple[str, ...] = ()


class ContextProvider(ABC):
    """Base class for context providers that enrich symbols with external metadata."""

    @abstractmethod
    def name(self) -> str:
        """Unique name for this provider."""
        ...

    @abstractmethod
    def detect(self, repo_path: Path) -> bool:
        """Return True if this provider is applicable to the given repo."""
        ...

    @abstractmethod
    def load(self, repo_path: Path) -> None:
        """Load/parse external metadata from the repo."""
        ...

    @abstractmethod
    def get_columns(self, table_name: str) -> list[ColumnMetadata]:
        """Return column metadata for a given table/model name."""
        ...

    @abstractmethod
    def search_columns(self, query: str) -> list[ColumnMetadata]:
        """Search column metadata by name or description."""
        ...


@dataclass
class ProviderRegistry:
    """Registry of available context providers."""

    _providers: list[type[ContextProvider]] = field(default_factory=list)
    _active: dict[str, ContextProvider] = field(default_factory=dict)

    def register(self, provider_cls: type[ContextProvider]) -> None:
        """Register a context provider class."""
        self._providers.append(provider_cls)

    def discover(self, repo_path: Path) -> list[ContextProvider]:
        """Detect and load applicable providers for a repo."""
        active: list[ContextProvider] = []
        for cls in self._providers:
            provider = cls()
            if provider.detect(repo_path):
                provider.load(repo_path)
                self._active[provider.name()] = provider
                active.append(provider)
        return active

    def get_active(self) -> list[ContextProvider]:
        """Return currently active providers."""
        return list(self._active.values())

    def search_all_columns(self, query: str) -> list[ColumnMetadata]:
        """Search columns across all active providers."""
        results: list[ColumnMetadata] = []
        for provider in self._active.values():
            results.extend(provider.search_columns(query))
        return results

    def get_all_columns(self, table_name: str) -> list[ColumnMetadata]:
        """Get columns for a table across all active providers."""
        results: list[ColumnMetadata] = []
        for provider in self._active.values():
            results.extend(provider.get_columns(table_name))
        return results


# Global registry
registry = ProviderRegistry()
