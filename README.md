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

Snip scans your code folder and builds an index — like a table of contents. It uses [tree-sitter](https://tree-sitter.github.io/) (a code parser) to understand the structure: where every function, class, and method starts and ends, down to the exact byte position. It also parses documents (Markdown, Excel, Word, PowerPoint, PDF, CSV) and builds a call graph across your codebase.

### Step 2 — Retrieve (every time the assistant needs code)

Instead of reading full files, the assistant calls Snip tools like `get_symbol` which does a precision lookup — jumps directly to byte position 1,847, reads exactly 312 bytes, done. Like flipping to page 47 instead of reading the whole book.

### Step 3 — Track Savings

Every time Snip serves code, it records: "The full file was ~500 tokens, but I only returned ~20 tokens." These savings accumulate and are visible in the status bar and via the `get_stats` tool.

## Features

- **Tree-sitter AST parsing** for 23 languages (Python, JS, TS, TSX, Go, Rust, Java, C#, C, C++, SQL, Ruby, Kotlin, Swift, PHP, Scala, Lua, Bash, HTML, CSS, YAML, JSON, TOML)
- **29 MCP tools** for indexing, searching, retrieving, code intelligence, document parsing, and exporting
- **Dead code & circular import detection** — find unused symbols and import cycles across the codebase
- **Call graph analysis** — see what calls what, find callers, assess change impact
- **Type information extraction** — parameters and return types for Python, TS, Go, Rust, Java, C#
- **Document indexing** — parse Markdown, Excel, Word, PowerPoint, PDF, CSV into searchable sections
- **Fuzzy search** — rapidfuzz-powered symbol search with camelCase/snake_case normalization
- **Mermaid diagram export** — class hierarchy, call graph, and import diagrams
- **Test coverage mapping** — find tests for any symbol via naming conventions, imports, and call graph
- **Watch mode** — auto-reindex on file changes (optional `watchfiles` dependency)
- **Fast serialization** — orjson for ~10x faster index read/write, optional gzip compression
- **Accurate token counting** — optional tiktoken integration (falls back to chars/4 heuristic)
- **Zero external network calls** — fully local, no telemetry
- **Incremental indexing** — only re-parses changed files
- **Byte-offset retrieval** — O(1) symbol source lookup
- **Security filtering** — blocks secrets, binaries, path traversal

## Install

```bash
uv sync
```

### Optional extras

```bash
uv sync --extra tokens   # tiktoken for accurate token counting
uv sync --extra docs     # openpyxl, python-docx, python-pptx, pymupdf for document parsing
uv sync --extra watch    # watchfiles for auto-reindex on file changes
uv sync --extra all      # everything
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

### Setup & Browse (5 tools)

| Tool | Purpose |
|------|---------|
| `index_folder` | Scan a folder and build the code index |
| `list_repos` | List all indexed folders |
| `get_file_tree` | Directory tree with language annotations |
| `get_repo_outline` | High-level repo overview (languages, stats) |
| `get_file_outline` | Symbol hierarchy for a file |

### Read (3 tools)

| Tool | Purpose |
|------|---------|
| `get_file_content` | File content with optional line range |
| `get_symbol` | Single symbol by ID (O(1) byte-offset lookup) |
| `get_symbols` | Batch retrieve multiple symbols |

### Search (7 tools)

| Tool | Purpose |
|------|---------|
| `search_symbols` | Weighted + fuzzy search across symbols |
| `search_text` | Full-text search with context lines |
| `search_columns` | Column metadata search (e.g., dbt schema.yml) |
| `search_annotations` | Find symbols by decorator/annotation pattern |
| `find_importers` | Reverse import graph — who imports this? |
| `find_references` | Find all usages of a symbol name |
| `get_changes` | Symbols added/modified/removed since last index |

### Code Intelligence (4 tools)

| Tool | Purpose |
|------|---------|
| `get_call_graph` | What does a symbol call? (with depth traversal) |
| `get_callers` | Who calls this symbol? |
| `get_change_impact` | Changed symbols + their dependents via call graph |
| `get_test_coverage` | Find tests for a symbol (naming, imports, call graph) |
| `get_dead_code` | Detect unused symbols and circular import chains |

### Documents (3 tools)

| Tool | Purpose |
|------|---------|
| `get_document_outline` | Section hierarchy of a document |
| `get_document_section` | Retrieve specific section content |
| `search_documents` | Search document sections by title/content |

### Export & Manage (6 tools)

| Tool | Purpose |
|------|---------|
| `export_diagram` | Mermaid diagrams (class hierarchy, call graph, imports) |
| `export_docs` | Generate markdown documentation from index |
| `resolve_cross_repo` | Resolve imports across indexed repos |
| `watch_repo` | Start/stop auto-reindex on file changes |
| `invalidate_cache` | Delete cached index, force re-index |
| `get_stats` | Session + cumulative token savings |

## Auto-Index on Session Start

Add a Claude Code hook to automatically index your project when a conversation starts. Add this to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "uv --directory /path/to/snip-mcp run snip-mcp-index $PWD"
          }
        ]
      }
    ]
  }
}
```

Or simply tell Claude to run `index_folder` at the start of your conversation — it only re-parses changed files so subsequent runs are fast.

## Teaching Claude to Use Snip

Copy `docs/CLAUDE.md.example` into your project as `CLAUDE.md` to teach Claude when to use Snip tools:

```bash
cp /path/to/snip-mcp/docs/CLAUDE.md.example ./CLAUDE.md
```

This makes Claude prefer `get_symbol` over reading full files, use `get_change_impact` before refactors, and leverage the call graph for navigation.

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
