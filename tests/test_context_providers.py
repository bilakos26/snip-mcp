"""Tests for context providers (dbt)."""

from __future__ import annotations

from pathlib import Path

import pytest

from snip_mcp.parser.context.dbt import DbtContextProvider


class TestDbtProvider:
    @pytest.fixture
    def dbt_repo(self, tmp_path: Path) -> Path:
        """Create a minimal dbt project structure."""
        # dbt_project.yml (marker file)
        (tmp_path / "dbt_project.yml").write_text("name: test_project\nversion: '1.0.0'\n")

        # models directory
        models = tmp_path / "models"
        models.mkdir()

        # schema.yml with model definitions
        schema = models / "schema.yml"
        schema.write_text(
            """
version: 2

models:
  - name: orders
    description: Order data
    columns:
      - name: order_id
        description: Primary key
        data_type: integer
      - name: customer_id
        description: Foreign key to customers
        data_type: integer
      - name: amount
        description: Order total amount
        data_type: decimal
        tags:
          - financial

sources:
  - name: raw
    tables:
      - name: raw_orders
        columns:
          - name: id
            description: Raw order ID
          - name: status
            description: Order status
"""
        )
        return tmp_path

    def test_detect_dbt_project(self, dbt_repo: Path) -> None:
        provider = DbtContextProvider()
        assert provider.detect(dbt_repo) is True

    def test_detect_non_dbt(self, tmp_path: Path) -> None:
        provider = DbtContextProvider()
        assert provider.detect(tmp_path) is False

    def test_load_columns(self, dbt_repo: Path) -> None:
        provider = DbtContextProvider()
        provider.load(dbt_repo)
        columns = provider.get_columns("orders")
        assert len(columns) == 3
        names = {c.name for c in columns}
        assert "order_id" in names
        assert "customer_id" in names
        assert "amount" in names

    def test_search_columns(self, dbt_repo: Path) -> None:
        provider = DbtContextProvider()
        provider.load(dbt_repo)
        results = provider.search_columns("order")
        assert len(results) >= 1
        assert any("order" in c.name.lower() for c in results)

    def test_source_columns(self, dbt_repo: Path) -> None:
        provider = DbtContextProvider()
        provider.load(dbt_repo)
        columns = provider.get_columns("raw_orders")
        assert len(columns) == 2

    def test_column_metadata_fields(self, dbt_repo: Path) -> None:
        provider = DbtContextProvider()
        provider.load(dbt_repo)
        columns = provider.get_columns("orders")
        amount = next((c for c in columns if c.name == "amount"), None)
        assert amount is not None
        assert amount.data_type == "decimal"
        assert "financial" in amount.tags
