"""dbt context provider — extracts column metadata from schema.yml and doc blocks."""

from __future__ import annotations

import re
from pathlib import Path

from snip_mcp.parser.context.base import ColumnMetadata, ContextProvider, registry

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class DbtContextProvider(ContextProvider):
    """Extracts column metadata from dbt schema.yml files and doc blocks."""

    def __init__(self) -> None:
        self._columns: dict[str, list[ColumnMetadata]] = {}  # table -> columns
        self._all_columns: list[ColumnMetadata] = []

    def name(self) -> str:
        return "dbt"

    def detect(self, repo_path: Path) -> bool:
        """Detect dbt project by presence of dbt_project.yml."""
        return (repo_path / "dbt_project.yml").exists()

    def load(self, repo_path: Path) -> None:
        """Load schema.yml files from the dbt project."""
        if not HAS_YAML:
            return

        self._columns.clear()
        self._all_columns.clear()

        # Find all schema.yml / *.yml files in models/ directory
        models_dir = repo_path / "models"
        if not models_dir.exists():
            # Try looking for yml files anywhere
            yml_files = list(repo_path.rglob("schema.yml")) + list(repo_path.rglob("*.yml"))
        else:
            yml_files = list(models_dir.rglob("*.yml"))

        for yml_path in yml_files:
            self._parse_schema_yml(yml_path, repo_path)

    def _parse_schema_yml(self, yml_path: Path, repo_path: Path) -> None:
        """Parse a dbt schema.yml file for model/column definitions."""
        try:
            content = yml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        # Parse models
        for model in data.get("models", []):
            if not isinstance(model, dict):
                continue
            model_name = model.get("name", "")
            if not model_name:
                continue

            columns: list[ColumnMetadata] = []
            for col in model.get("columns", []):
                if not isinstance(col, dict):
                    continue
                col_name = col.get("name", "")
                if not col_name:
                    continue

                description = col.get("description", "")
                # Strip dbt doc blocks: {{ doc("...") }}
                doc_pattern = r'\{\{\s*doc\s*\(\s*["\'].*?["\']\s*\)\s*\}\}'
                description = re.sub(doc_pattern, "", description)
                description = description.strip()

                data_type = col.get("data_type", col.get("type", ""))
                tags = tuple(col.get("tags", []))

                col_meta = ColumnMetadata(
                    name=col_name,
                    description=description,
                    data_type=str(data_type) if data_type else "",
                    table=model_name,
                    source_file=str(yml_path.relative_to(repo_path)),
                    tags=tags,
                )
                columns.append(col_meta)
                self._all_columns.append(col_meta)

            if columns:
                self._columns[model_name] = columns

        # Parse sources
        for source in data.get("sources", []):
            if not isinstance(source, dict):
                continue
            source_name = source.get("name", "")
            for table in source.get("tables", []):
                if not isinstance(table, dict):
                    continue
                table_name = table.get("name", "")
                full_name = f"{source_name}.{table_name}" if source_name else table_name
                if not table_name:
                    continue

                columns: list[ColumnMetadata] = []
                for col in table.get("columns", []):
                    if not isinstance(col, dict):
                        continue
                    col_name = col.get("name", "")
                    if not col_name:
                        continue

                    col_meta = ColumnMetadata(
                        name=col_name,
                        description=col.get("description", "").strip(),
                        data_type=str(col.get("data_type", "")) if col.get("data_type") else "",
                        table=full_name,
                        source_file=str(yml_path.relative_to(repo_path)),
                        tags=tuple(col.get("tags", [])),
                    )
                    columns.append(col_meta)
                    self._all_columns.append(col_meta)

                if columns:
                    self._columns[full_name] = columns
                    self._columns[table_name] = columns  # Also index by short name

    def get_columns(self, table_name: str) -> list[ColumnMetadata]:
        """Return column metadata for a given table/model name."""
        return self._columns.get(table_name, [])

    def search_columns(self, query: str) -> list[ColumnMetadata]:
        """Search columns by name or description (case-insensitive substring match)."""
        query_lower = query.lower()
        results: list[ColumnMetadata] = []
        for col in self._all_columns:
            if query_lower in col.name.lower() or query_lower in col.description.lower():
                results.append(col)
        return results


# Auto-register
registry.register(DbtContextProvider)
