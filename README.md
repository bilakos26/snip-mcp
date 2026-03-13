# Snip MCP

Local-only MCP server for token-efficient code retrieval via tree-sitter AST parsing.

## The Problem

When AI coding assistants read your code, they read **entire files**. If you have a 500-line Python file but the assistant only needs one 20-line function, it still reads all 500 lines. That wastes the **context window** — the assistant's working memory for your conversation. The more of it gets filled with unnecessary code, the sooner it forgets earlier parts of your conversation.

## How Snip Solves It

Think of it like a **book index** vs reading the whole book.

**Without Snip:**
> "I need to understand the `calculate_premium` function"
> *Reads the entire 500-line file* — 500 lines consumed from context window

**With Snip:**
> "I need to understand the `calculate_premium` function"
> *Looks up the exact location in its index and returns just those 20 lines* — 20 lines consumed

**That's 96% savings.**

## How It Works

### Step 1 — Index (one-time per project)

Snip scans your code folder and builds an index — like a table of contents. It uses [tree-sitter](https://tree-sitter.github.io/) (a code parser) to understand the structure: where every function, class, and method starts and ends, down to the exact byte position.

### Step 2 — Retrieve (every time the assistant needs code)

Instead of reading full files, the assistant calls Snip tools like `get_symbol` which does a precision lookup — jumps directly to byte position 1,847, reads exactly 312 bytes, done. Like flipping to page 47 instead of reading the whole book.

### Step 3 — Track Savings

Every time Snip serves code, it records: "The full file was ~500 tokens, but I only returned ~20 tokens." These savings accumulate and are visible in the status bar and via the `get_stats` tool.

## Features

- **Tree-sitter AST parsing** for 11 languages (Python, JS, TS, TSX, Go, Rust, Java, C#, C, C++, SQL)
- **15 MCP tools** for indexing, searching, retrieving code symbols, and tracking savings
- **Zero external network calls** — fully local, no telemetry
- **Incremental indexing** — only re-parses changed files
- **Byte-offset retrieval** — O(1) symbol source lookup
- **Security filtering** — blocks secrets, binaries, path traversal

## Install

```bash
uv sync
```

## Usage

### As MCP server (stdio)

```bash
uv run snip-mcp
```

### Claude Code integration

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "snip": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/path/to/snip-mcp", "run", "snip-mcp"]
    }
  }
}
```

Or via CLI:

```bash
claude mcp add snip uv --directory /path/to/snip-mcp run snip-mcp
```

## Tools

| Category | Tool | Purpose |
|----------|------|---------|
| **Setup** | `index_folder` | Scan a folder and build the code index |
| **Browse** | `list_repos` | List all indexed folders |
| | `get_file_tree` | Directory tree with language annotations |
| | `get_repo_outline` | High-level repo overview (languages, stats) |
| **Read** | `get_file_outline` | Symbol hierarchy for a file |
| | `get_file_content` | File content with optional line range |
| | `get_symbol` | Single symbol by ID (O(1) byte-offset lookup) |
| | `get_symbols` | Batch retrieve multiple symbols |
| **Search** | `search_symbols` | Weighted scoring search across symbols |
| | `search_text` | Full-text search with context lines |
| | `search_columns` | Column metadata search (e.g., dbt schema.yml) |
| | `find_importers` | Reverse import graph — who imports this? |
| | `find_references` | Find all usages of a symbol name |
| **Manage** | `invalidate_cache` | Delete cached index, force re-index |
| | `get_stats` | Session + cumulative token savings |

## Status Line

Show Snip token savings in your Claude Code terminal status bar:

```bash
# One command — copies script + updates settings.json automatically
uv run snip-mcp --setup-statusline

# Quick stats check from the terminal
uv run snip-mcp --stats
```

The statusline displays two lines at the bottom of your terminal:
```
Opus  ▐████████░░░░░░░░░░▌ 42% ctx  84.0K/200.0K  $0.15
  ⚡ Snip  ▐████████████████░░▌ 5 calls  12.3K saved (87%)
```

## Where Everything Lives

```
~/.snip/
  ├── stats.json      ← lifetime savings counter
  ├── session.json    ← current session savings (resets on server start)
  └── indexes/        ← code indexes (one per project)
```

Everything is **local only** — no data leaves your machine, no API calls, no telemetry.

## Corporate Network (SSL/Proxy)

If you're behind a corporate proxy that intercepts HTTPS, `pyproject.toml` includes:

```toml
[tool.uv]
native-tls = true                    # use OS certificate store
allow-insecure-host = ["pypi.org"]   # trust corporate-intercepted hosts
link-mode = "copy"                   # avoid hardlink errors on OneDrive
```

## License

MIT
