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
# Current project only:
claude mcp add snip uv --directory /path/to/snip-mcp run snip-mcp

# Global — available in all projects:
claude mcp add --global snip uv --directory /path/to/snip-mcp run snip-mcp
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

**Choosing the right search tool:**

| Goal | Tool |
|------|------|
| Find a function/class by name (fuzzy ok) | `search_symbols` |
| Find code containing a specific string or pattern | `search_text` |
| Find every place a specific symbol is used | `find_references` |
| Find which files import a specific module | `find_importers` |
| Find symbols with a specific decorator (e.g. `@pytest.fixture`) | `search_annotations` |

### Code Intelligence (5 tools)

| Tool | Purpose |
|------|---------|
| `get_call_graph` | What does a symbol call? (with depth traversal) |
| `get_callers` | Who calls this symbol? |
| `get_change_impact` | Changed symbols + their dependents via call graph |
| `get_test_coverage` | Find tests for a symbol (naming, imports, call graph) |
| `get_dead_code` | Detect unused symbols and circular import chains |

**Notable details:**

- **`get_call_graph`** — traverses outward from a symbol up to a configurable `depth` (default 1 = direct callees only). Increase depth to trace multi-level call chains.
- **`get_change_impact`** — given a list of changed symbol IDs, walks the call graph to find all downstream dependents. Run this before refactoring to know what else might break.
- **`get_dead_code`** — finds symbols that are never referenced anywhere in the codebase and detects circular import chains. Useful for cleanup before a major refactor.

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

**`export_diagram` — diagram types**

All three types output [Mermaid](https://mermaid.js.org/) markdown. Paste into any Mermaid renderer (e.g. [mermaid.live](https://mermaid.live), VS Code Mermaid Preview, or GitHub markdown blocks).

| Type | Shows | Best for |
|------|-------|----------|
| `class_hierarchy` | Classes, their methods, and nested class relationships | Understanding the object model |
| `call_graph` | Which functions/methods call which others | Understanding execution flow |
| `imports` | Which files import which other files/modules | Understanding project architecture |

Use `file_pattern` to scope the diagram to a specific subfolder — essential for large repos where the full graph would hit the 100-edge display limit:

```
# All tools files only:
export_diagram(repo_path, type="call_graph", file_pattern="tools/")
```

**Other notable tools:**

- **`export_docs`** — generates a markdown summary of every file in the index: symbol list, signatures, docstrings. Useful for producing onboarding docs or API references.
- **`resolve_cross_repo`** — given an import path (e.g. `from shared_lib.utils import helper`), resolves which symbol in another indexed repo it refers to. Useful in multi-repo monorepos.
- **`get_stats`** — returns session token savings (since last server start) and lifetime cumulative totals. Same data shown in the status bar.

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

There are two ways to teach Claude when and how to use Snip tools. Pick the one that fits your needs.

### Option A — Claude Rules file (recommended)

Copy the comprehensive rules file into your project's `.claude/rules/` directory. This is a [Claude Code rules file](https://docs.anthropic.com/en/docs/claude-code/settings#rules) that activates automatically in every conversation — no manual prompting needed.

```bash
# Create the rules directory if it doesn't exist
mkdir -p .claude/rules

# Copy the rules file
cp /path/to/snip-mcp/docs/snip-rules.md .claude/rules/snip.md
```

The rules file includes:
- Complete tool reference (all 29 tools with "use instead of" mappings)
- Decision guide: when to use Snip vs built-in tools
- Step-by-step workflows for code exploration, pre-refactor analysis, and document search
- An indexed repositories table you can customize for your team

Edit the `Indexed Repositories` table at the bottom of the file to list your team's repos and paths.

### Option B — CLAUDE.md (lightweight)

Copy the shorter `CLAUDE.md` into your project root for a lighter-touch guide:

```bash
cp /path/to/snip-mcp/docs/CLAUDE.md.example ./CLAUDE.md
```

This covers the essentials — prefer `get_symbol` over reading full files, use `get_change_impact` before refactors, leverage the call graph for navigation — but without the full tool reference or workflows.

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

## Releases

Versions follow `MAJOR.MINOR.PATCH` and are tracked in [`CHANGELOG.md`](CHANGELOG.md) and `pyproject.toml`.

To cut a release after merging changes:

```bash
# 1. Update version in pyproject.toml and add entry to CHANGELOG.md
# 2. Commit
git add pyproject.toml CHANGELOG.md
git commit -m "docs: add X.Y.Z changelog entry and bump version"

# 3. Tag and push
git tag vX.Y.Z
git push && git push origin vX.Y.Z
```

## License

MIT
