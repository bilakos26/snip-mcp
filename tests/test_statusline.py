"""Tests for the statusline script."""

from __future__ import annotations

from snip_mcp.statusline import (
    _format_claude_line,
    _format_snip_line,
    _format_tokens,
    _progress_bar,
)


class TestFormatTokens:
    def test_small_number(self) -> None:
        assert _format_tokens(500) == "500"

    def test_thousands(self) -> None:
        assert _format_tokens(12345) == "12.3K"

    def test_millions(self) -> None:
        assert _format_tokens(1_500_000) == "1.5M"

    def test_exact_thousand(self) -> None:
        assert _format_tokens(1000) == "1.0K"

    def test_exact_million(self) -> None:
        assert _format_tokens(1_000_000) == "1.0M"

    def test_zero(self) -> None:
        assert _format_tokens(0) == "0"

    def test_float_input(self) -> None:
        assert _format_tokens(84000.0) == "84.0K"


class TestProgressBar:
    def test_zero_percent(self) -> None:
        bar = _progress_bar(0)
        assert bar == "\u2590" + "\u2591" * 18 + "\u258c"

    def test_hundred_percent(self) -> None:
        bar = _progress_bar(100)
        assert bar == "\u2590" + "\u2588" * 18 + "\u258c"

    def test_fifty_percent(self) -> None:
        bar = _progress_bar(50)
        filled = bar.count("\u2588")
        empty = bar.count("\u2591")
        assert filled == 9
        assert empty == 9

    def test_custom_width(self) -> None:
        bar = _progress_bar(50, width=10)
        assert bar.count("\u2588") == 5
        assert bar.count("\u2591") == 5

    def test_clamps_over_100(self) -> None:
        bar = _progress_bar(150)
        assert bar == _progress_bar(100)

    def test_clamps_negative(self) -> None:
        bar = _progress_bar(-10)
        assert bar == _progress_bar(0)


class TestFormatClaudeLine:
    def test_full_context(self) -> None:
        ctx = {
            "model": {"display_name": "Opus"},
            "context_window": {
                "used_percentage": 42,
                "total_input_tokens": 84000,
                "context_window_size": 200000,
            },
            "cost": {"total_cost_usd": 0.15},
        }
        line = _format_claude_line(ctx)
        assert "Opus" in line
        assert "42%" in line
        assert "84.0K" in line
        assert "200.0K" in line
        assert "$0.15" in line
        assert "\u2588" in line  # has filled bar chars
        assert "\u2591" in line  # has empty bar chars

    def test_empty_context(self) -> None:
        line = _format_claude_line({})
        assert "Claude" in line  # default model name
        assert "\u2590" in line  # has bar


class TestFormatSnipLine:
    def test_with_savings(self) -> None:
        session = {
            "retrievals": 5,
            "full_tokens": 10000,
            "returned_tokens": 1000,
        }
        line = _format_snip_line(session)
        assert "5 calls" in line
        assert "9.0K saved" in line
        assert "90.0%" in line
        assert "\u26a1" in line  # lightning bolt
        assert "\u2588" in line  # filled bar

    def test_zero_calls(self) -> None:
        session = {"retrievals": 0, "full_tokens": 0, "returned_tokens": 0}
        line = _format_snip_line(session)
        assert "0 calls" in line
        assert "0.0%" in line
