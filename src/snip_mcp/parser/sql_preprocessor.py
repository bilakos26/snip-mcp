"""SQL preprocessor — strips Jinja/dbt templates before tree-sitter parsing."""

from __future__ import annotations

import re

# Patterns for Jinja2/dbt template syntax
_JINJA_BLOCK = re.compile(r"\{%[-~]?.*?[-~]?%\}", re.DOTALL)
_JINJA_EXPR = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)

# dbt-specific macros that expand to SQL fragments
_DBT_REF = re.compile(r"\{\{\s*ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_DBT_SOURCE = re.compile(
    r"\{\{\s*source\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)
_DBT_CONFIG = re.compile(r"\{\{\s*config\s*\(.*?\)\s*\}\}", re.DOTALL)


def strip_jinja(sql: str) -> str:
    """Remove Jinja/dbt template syntax from SQL, replacing with valid SQL placeholders.

    - `{{ ref('model') }}` -> `model`
    - `{{ source('schema', 'table') }}` -> `schema.table`
    - `{{ config(...) }}` -> empty string
    - `{% ... %}` blocks -> empty string
    - `{{ expr }}` -> `__JINJA_EXPR__`
    - `{# comment #}` -> empty string
    """
    result = sql

    # Replace dbt ref() with table name
    result = _DBT_REF.sub(r"\1", result)

    # Replace dbt source() with schema.table
    result = _DBT_SOURCE.sub(r"\1.\2", result)

    # Remove dbt config()
    result = _DBT_CONFIG.sub("", result)

    # Remove Jinja comments
    result = _JINJA_COMMENT.sub("", result)

    # Remove Jinja blocks ({% if %}, {% for %}, etc.)
    result = _JINJA_BLOCK.sub("", result)

    # Replace remaining Jinja expressions with placeholder identifier
    result = _JINJA_EXPR.sub("__JINJA_EXPR__", result)

    return result


def is_dbt_model(sql: str) -> bool:
    """Check if SQL content contains dbt template syntax."""
    return bool(
        _DBT_REF.search(sql)
        or _DBT_SOURCE.search(sql)
        or _DBT_CONFIG.search(sql)
        or _JINJA_BLOCK.search(sql)
    )
