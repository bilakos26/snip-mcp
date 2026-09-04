# Changelog

All notable changes to snip-mcp are documented here.

## [0.4.0] — 2026-09-04

### Changed
- **Version is now sourced solely from `snip_mcp.__version__`.** `pyproject.toml`
  previously said 0.3.3 while the package said 0.1.0; the two can no longer drift.

### Added
- **`.gitattributes`** normalizing text to LF, so `core.autocrlf` stops reporting ~50
  unchanged files as modified.

## [0.3.3] — 2026-05-07

### Added
- **`output_path` parameter** on `export_diagram` and `export_docs` — both tools now optionally
  write their output to a file on disk and return a `saved_to` field in the response.
- **Node color groups** on all three diagram types — nodes are colored by top-level directory
  (e.g. `core/`, `schemas/`, `src/`) so the architecture layers are immediately visible.

### Fixed
- **`imports` diagram showed external packages** — `logging`, `os`, `requests`, `pydantic` etc.
  were drawn as nodes, producing a huge noisy graph. Only project-internal file imports are now
  shown. Node labels show `folder/file.py` to disambiguate files with the same name.
- **`class_hierarchy` showed duplicate classes** — same class name in different files (e.g.
  `schemas/applications.py` and `core/ifw_api/applications.py` both named `Applications`)
  collided on the same sanitized ID, producing self-referencing arrows. Fixed by using
  `directory_ClassName` as the unique ID.
- **`class_hierarchy` rendered 126+ classes in one horizontal line** — now filters to classes
  with at least one public method, caps at 30, and groups into `namespace` blocks by directory
  so each folder's classes appear in their own labeled box.
- **`class_hierarchy` found no methods** — tree-sitter stores Python class methods as
  `FUNCTION` kind, not `METHOD`. Both kinds are now accepted when collecting class members.
- **`classDef`/`class` color syntax invalid in `classDiagram`** — flowchart-style `classDef`
  is not valid in `classDiagram` context. Switched to `style ClassName fill:...` directives.
- **Graph layout unreadable** — `graph LR` (left-right) created wide horizontal chains.
  Switched to `graph TD` (top-down) for `imports` and `call_graph`. `classDiagram` now uses
  `namespace` blocks to group classes vertically by directory.

---

## [0.3.2] — 2026-05-07

### Fixed
- **Call graph produced unreadable diagrams** — `build_call_graph` matched every identifier in
  function bodies (including comments, string literals, and local variable names) against all
  known symbol names, creating thousands of false edges. Added `_EXCLUDED_NAMES` (Python
  keywords, built-ins, and ~30 ubiquitous local variable names) to filter candidate names before
  matching. Re-index required after upgrade.
- **Diagram truncation left orphan floating nodes** — `export_diagram` broke only the inner
  loop at the 100-edge cap, so outer loop continued adding caller node declarations with no
  edges attached. Both `_call_graph_diagram` and `_imports_diagram` now break the outer loop
  at the limit. A `%% Truncated...` Mermaid comment is appended when the cap is hit.

### Changed
- **README**: `claude mcp add` example now shows both project-scoped and `--global` install forms.

### Upgrade steps (existing installs)
After `git pull`, re-index any repos to rebuild the call graph with cleaner edges:
```
uv run snip-mcp-index /path/to/your/repo
```

---

## [0.3.1] — 2026-05-07

### Fixed
- **Session tracking broken across conversations** — `token_tracker._load_session()` was silently
  dropping the `session_id` field on every `record_retrieval()` call, so the statusline's
  cross-conversation reset never fired. Stats now correctly reset when a new Claude Code
  conversation starts.
- **Inflated token savings percentage in `get_symbol`** — `full_tokens` was estimated from
  file size in bytes (`file_size // 4`) while `returned_tokens` used accurate tiktoken counts,
  creating an apples-to-oranges comparison. Both sides now use `estimate_tokens()` on actual
  file content, matching the approach in `get_file_content`. The batch `get_symbols` path
  caches file reads to avoid redundant I/O.

### Upgrade steps (existing installs)
After `git pull`, re-run the statusline installer to sync the deployed script:
```
uv run snip-mcp --setup-statusline
```
Then restart Claude Code.

---

## [0.3.0] — 2026-04-15

### Added
- **`snip-mcp-index` CLI entry point** — index a folder from the terminal without starting
  the MCP server (`uv run snip-mcp-index <path>`).
- **Document support in `search_text` and `find_references`** — both tools now search across
  indexed document files (PDF, Word, Excel, etc.) in addition to source code.
- **Session-aware statusline reset** — statusline detects new Claude Code conversations via
  `session_id` and resets per-session Snip stats automatically.

### Changed
- **Call graph performance** — file caching and set-intersection pruning reduce redundant work
  on large graphs.
- **`index_folder` uses `os.walk` with directory pruning** — gitignore-matched directories are
  skipped before descending, not after.
- **Async tool dispatch** — tools now run via `asyncio.to_thread` to avoid blocking the MCP
  event loop during heavy I/O.

---

## [0.2.0] — 2026-04-02

### Added
- **14 new tools** (29 total):
  - Call graph: `get_call_graph`, `get_callers`
  - Change analysis: `get_change_impact`, `get_changes`
  - Quality: `get_dead_code`, `get_test_coverage`
  - Documents: `get_document_outline`, `get_document_section`, `search_documents`, `export_docs`
  - Discovery: `search_annotations`, `find_importers`
  - Cross-repo: `resolve_cross_repo`
  - Diagrams: `export_diagram`
- **Document parsing** — PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), CSV, Markdown
  via optional `[docs]` extra (`uv sync --extra docs`).
- **23 language support** (up from 11) — Go, Rust, Java, C#, C/C++, Kotlin, Swift, PHP, Scala,
  Lua, Bash, HTML, CSS, YAML, TOML added alongside existing Python, JS, TS, SQL, Ruby.
- **Live file watcher** — `watch_repo` tool triggers incremental re-index on file changes
  (requires `[watch]` extra).
- **Import resolver** — tracks import relationships for cross-file and cross-repo analysis.
- **Accurate token counting** — `tiktoken` integration via `[tokens]` extra
  (`uv sync --extra tokens` or `uv sync --extra all`).

### Changed
- Index format extended to store call edges, import graph, and document content.

---

## [0.1.0] — 2026-03-13

### Added
- Initial release with 15 tools: `index_folder`, `get_symbol`, `get_symbols`,
  `get_file_content`, `get_file_outline`, `get_file_tree`, `get_repo_outline`,
  `search_symbols`, `search_text`, `search_columns`, `find_references`,
  `get_stats`, `list_repos`, `invalidate_cache`, `watch_repo`.
- Tree-sitter AST parsing for 11 languages (Python, JS, TS, TSX, Go, Rust, Java, C#, Ruby, SQL, Lua).
- Incremental indexing with content-hash caching.
- Token savings tracking: records `full_tokens` vs `returned_tokens` per retrieval
  and persists session and cumulative stats to `~/.snip/`.
- Statusline integration for Claude Code (`snip-mcp --setup-statusline`).
- Security layer: path traversal prevention, secret file detection, binary detection,
  `.gitignore` / `.snipignore` support.
