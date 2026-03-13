"""Heuristic-only summarizer for Snip MCP.

No AI API calls -- the calling agent (Claude) handles deeper summarization
itself.  These functions produce fast, deterministic one-liners used during
indexing and tool responses.
"""

from __future__ import annotations

from snip_mcp.parser.symbols import FileSymbols, Symbol

_MAX_LEN = 120


def _first_sentence(text: str) -> str:
    """Extract the first sentence from *text*, capped at ``_MAX_LEN`` chars.

    A "sentence" ends at the first occurrence of ". " (period + space) or the
    first newline, whichever comes first.  If neither is found the whole string
    is used (truncated).
    """
    # Normalise leading/trailing whitespace.
    text = text.strip()

    # Find earliest sentence boundary.
    end = len(text)
    for delimiter in (". ", "\n"):
        pos = text.find(delimiter)
        if pos != -1:
            # Include the period itself but not the space / newline.
            boundary = pos + 1 if delimiter == ". " else pos
            end = min(end, boundary)

    sentence = text[:end].strip()
    if len(sentence) > _MAX_LEN:
        return sentence[: _MAX_LEN - 3] + "..."
    return sentence


def summarize_symbol(symbol: Symbol) -> str:
    """Generate a one-line heuristic summary for *symbol*.

    If the symbol carries a docstring the first sentence is extracted.
    Otherwise the raw signature is used, truncated to 120 characters.

    The result is prefixed with the symbol kind, e.g.::

        function: Does something useful.
        class: MyClass(Base)

    Parameters
    ----------
    symbol:
        A :class:`Symbol` instance to summarise.

    Returns
    -------
    str
        A single-line summary string.
    """
    kind_label: str = symbol.kind.value

    if symbol.docstring:
        description = _first_sentence(symbol.docstring)
    else:
        sig = symbol.signature.strip()
        if len(sig) > _MAX_LEN:
            description = sig[: _MAX_LEN - 3] + "..."
        else:
            description = sig

    return f"{kind_label}: {description}"


def summarize_file(file_symbols: FileSymbols) -> str:
    """Generate a brief file-level summary.

    Format::

        python file, 3 symbols: my_func, MyClass, CONSTANT
        sql file, 7 symbols: users, orders, payments, cte_totals, get_user ... and 2 more

    Parameters
    ----------
    file_symbols:
        A :class:`FileSymbols` container for a single file.

    Returns
    -------
    str
        A single-line summary string.
    """
    top_level: list[str] = [s.name for s in file_symbols.symbols if not s.parent_id]
    total: int = len(file_symbols.symbols)
    lang: str = file_symbols.language or "unknown"

    if not top_level:
        return f"{lang} file, {total} symbols"

    max_shown = 5
    if len(top_level) <= max_shown:
        names_part = ", ".join(top_level)
    else:
        names_part = ", ".join(top_level[:max_shown])
        remaining = len(top_level) - max_shown
        names_part += f" ... and {remaining} more"

    return f"{lang} file, {total} symbols: {names_part}"


def summarize_repo(
    total_files: int,
    total_symbols: int,
    language_stats: dict[str, int],
) -> str:
    """Generate a one-line repository-level summary.

    Lists the top 5 languages (by file count) alongside aggregate totals.

    Format::

        42 files, 318 symbols across python (20), sql (12), javascript (5), rust (3), go (2)

    Parameters
    ----------
    total_files:
        Total number of indexed files.
    total_symbols:
        Total number of extracted symbols.
    language_stats:
        Mapping of language name to file count.

    Returns
    -------
    str
        A single-line summary string.
    """
    sorted_langs: list[tuple[str, int]] = sorted(
        language_stats.items(), key=lambda item: item[1], reverse=True
    )
    top_langs: list[str] = [f"{lang} ({count})" for lang, count in sorted_langs[:5]]
    langs_part: str = ", ".join(top_langs) if top_langs else "no languages detected"

    return f"{total_files} files, {total_symbols} symbols across {langs_part}"
