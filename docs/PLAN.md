# Snip MCP v2.0 — Full Enhancement Plan

## Context

Snip MCP is currently a solid token-efficient code retrieval tool with 15 MCP tools, 11 languages, and O(1) byte-offset symbol retrieval. This plan transforms it into a **comprehensive code intelligence + document knowledge engine** — adding call graphs, type info, cross-file resolution, change impact analysis, document indexing (Markdown, Excel, Word, PowerPoint, PDF, CSV), fuzzy search, export, watch mode, and more.

**21 features across 5 phases**, adding **13 new MCP tools** (total: 28), **12 new languages**, and a full document parsing layer.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Document storage | Unified `CodeIndex` with new `documents: dict[str, DocumentFile]` field | Single index file per repo, simpler cross-referencing |
| Call graph storage | `call_graph: dict[str, list[str]]` in `CodeIndex` (caller->callees). Reverse index computed on-the-fly | Self-contained, no separate file |
| Watch mode | `asyncio.Task` inside the MCP server process using `watchfiles` | MCP server already has an event loop |
| Dependencies | Core: `orjson`, `rapidfuzz`. Optional extras: `[tokens]` tiktoken, `[docs]` openpyxl/docx/pptx/pymupdf, `[watch]` watchfiles | Keeps core lean, optional heavy deps |
| Index versioning | `schema_version` field (v1=legacy, v2=new). Deserializer uses `.get()` with defaults | Full backward compatibility |

---

## Phase 1: Foundation Improvements

### 1.1 More Languages (12 new)
**Modify:** `parser/languages.py`, `parser/imports.py`

| Language | ID | Extensions | Key Symbols |
|----------|----|-----------|-------------|
| Ruby | `ruby` | .rb, .rake, .gemspec | method, class, module |
| Kotlin | `kotlin` | .kt, .kts | function, class, interface |
| Swift | `swift` | .swift | function, class, struct, enum, protocol |
| PHP | `php` | .php | function, class, method, interface |
| Scala | `scala` | .scala, .sc | function, class, trait, object |
| Lua | `lua` | .lua | function, variable |
| Bash | `bash` | .sh, .bash | function |
| HTML | `html` | .html, .htm | (no symbols — enables text search/file tree) |
| CSS | `css` | .css | (no symbols — structural indexing) |
| YAML | `yaml` | .yml, .yaml | (no symbols — text search) |
| JSON | `json` | .json | (no symbols — text search) |
| TOML | `toml` | .toml | (no symbols — text search) |

For HTML/CSS/YAML/JSON/TOML, `symbol_queries` is empty `{}`, which means `extract_file_symbols` returns `[]`. These files still get tracked in the index for `search_text`, `get_file_tree`, and `get_file_content`.

Import extractors for new languages:
- Ruby: `require 'X'`, `require_relative 'X'`
- Kotlin: `import X.Y.Z`
- Swift: `import X`
- PHP: `use X\Y\Z;`, `require_once 'X';`
- Scala: `import X.Y.Z`
- Lua: `require("X")`
- Bash: `source X`, `. X`

### 1.2 Index Compression (orjson + optional gzip)
**Modify:** `storage/index_store.py`, `pyproject.toml`

- Replace `json.dumps`/`json.loads` with `orjson.dumps`/`orjson.loads` (10x faster)
- Add `compress: bool = False` parameter to `IndexStore` — saves as `.json.gz` when enabled
- Loader auto-detects gzip via magic bytes, reads both formats transparently
- Old JSON files remain readable without changes

### 1.3 Accurate Token Counting
**Modify:** `storage/token_tracker.py`, `pyproject.toml`

- Optional `tiktoken` dependency under `[tokens]` extra
- Graceful fallback to chars/4 when not installed
- `estimate_tokens()` signature unchanged

```python
try:
    import tiktoken
    _ENC = tiktoken.encoding_for_model("gpt-4o")
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

def estimate_tokens(text: str) -> int:
    if HAS_TIKTOKEN:
        return len(_ENC.encode(text))
    return len(text) // 4
```

---

## Phase 2: Code Intelligence

### 2.1 Type Information Extraction
**Modify:** `parser/symbols.py`, `parser/extractor.py`, `storage/index_store.py`

New Symbol fields (all with defaults for backward compat):
```python
return_type: str = ""
parameters: tuple[Parameter, ...] = ()
```

New dataclass:
```python
@dataclass(frozen=True)
class Parameter:
    name: str
    type_annotation: str = ""
    default_value: str = ""
```

New extractor function `_extract_type_info(node, source_bytes, language_id)` handles:
- **Python**: `parameters` child -> `typed_parameter` with `type`; return annotation via `->`
- **TypeScript**: `formal_parameters` -> `required_parameter`/`optional_parameter` with `type_annotation`
- **Go**: `parameter_list`; result type from `type_identifier` sibling
- **Rust**: `parameters` -> `parameter` with type; `-> type` return
- **Java/C#**: method return type from first child `type_identifier`; `formal_parameters`

### 2.2 Call Graph / Dependency Graph
**Create:** `parser/call_graph.py`, `tools/get_call_graph.py`, `tools/get_callers.py`
**Modify:** `storage/index_store.py`, `tools/index_folder.py`, `server.py`

New `CodeIndex` field: `call_graph: dict[str, list[str]]` (caller_id -> [callee_ids])

Algorithm:
1. Build name-to-symbol-id lookup: `{symbol.name: [symbol.id, ...]}`
2. For each function/method symbol, read source text via byte offsets
3. Find identifiers matching known symbol names (`\b{name}\b` regex)
4. Exclude self-references, record edges
5. Reverse index computed on-the-fly by `get_callers`

**New tools:**

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_call_graph` | `repo_path`, `symbol_id`, `depth=1` | What does this symbol call? (with depth traversal) |
| `get_callers` | `repo_path`, `symbol_id` | Who calls this symbol? |

### 2.3 Cross-File Symbol Resolution
**Create:** `parser/resolver.py`
**Modify:** `parser/symbols.py`, `storage/index_store.py`, `tools/index_folder.py`

New `FileSymbols` field: `resolved_imports: dict[str, str] = {}` (import_string -> symbol_id)

Per-language resolvers:
1. Parse import string (e.g., `from app.services.orders import OrderService`)
2. Convert module path to file path candidate (e.g., `app/services/orders.py`)
3. Check if file exists in `index.files`
4. Search its symbols for matching name
5. Store resolution: `resolved_imports["..."] = symbol_id`

### 2.4 Change Impact Analysis
**Create:** `tools/get_change_impact.py`
**Modify:** `server.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_change_impact` | `repo_path`, `file_path?` | Compares current files to index, identifies changed symbols + their dependents via call graph |

Implementation:
1. Re-hash files, compare with stored `file_hashes`
2. Re-extract changed files, diff symbols by `content_hash`
3. Classify: added/modified/removed symbols
4. Traverse call graph callers for impacted symbols
5. Return `{changed: [...], impacted: [...]}`

---

## Phase 3: Search Enhancement

### 3.1 Fuzzy Search
**Modify:** `tools/search_symbols.py`, `pyproject.toml`

- Add `rapidfuzz` as core dependency
- `_normalize(name)` converts camelCase/snake_case/kebab-case to uniform form
- After existing exact/prefix/substring scoring, add fuzzy score (threshold 60%)
- Results include `fuzzy_score` for transparency

```python
from rapidfuzz import fuzz

normalized_query = _normalize(query)
normalized_name = _normalize(sym.name)
fuzzy_score = fuzz.ratio(normalized_query, normalized_name)
if fuzzy_score >= 60:
    score += fuzzy_score / 10  # scale to 0-10 range
```

### 3.2 Annotation/Tag Search
**Create:** `tools/search_annotations.py`
**Modify:** `server.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_annotations` | `repo_path`, `pattern`, `max_results=50` | Find symbols by decorator/annotation (e.g., "router.get", "pytest.mark") |

Searches existing `Symbol.decorators` tuple — no new extraction needed.

### 3.3 Symbol Changelog
**Create:** `tools/get_changes.py`
**Modify:** `storage/index_store.py`, `tools/index_folder.py`, `server.py`

New `CodeIndex` field: `previous_symbol_hashes: dict[str, str] = {}`

On re-index, saves old `{sym.id: sym.content_hash}`. Tool compares previous vs current:
- **Added**: in current, not in previous
- **Removed**: in previous, not in current
- **Modified**: in both, hash differs

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_changes` | `repo_path` | Shows symbols added/modified/removed since last index |

---

## Phase 4: Document Indexing

### 4.1 Document Parser Framework
**Create:** `parser/documents/__init__.py`, `parser/documents/base.py`, `parser/documents/registry.py`
**Modify:** `storage/index_store.py`, `security.py`, `tools/index_folder.py`

New dataclasses:
```python
@dataclass(frozen=True)
class DocumentSection:
    id: str                    # doc_path::section_type::title::line
    title: str
    section_type: str          # "heading", "table", "code_block", "slide", "sheet", etc.
    file_path: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    content_preview: str       # first 200 chars
    level: int = 0
    parent_id: str = ""
    children: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

@dataclass
class DocumentFile:
    file_path: str
    format: str                # "markdown", "excel", "word", "powerpoint", "pdf", "csv"
    sections: list[DocumentSection] = field(default_factory=list)
    content_hash: str = ""
    file_size: int = 0
```

New `CodeIndex` field: `documents: dict[str, DocumentFile] = {}`

**Security change:** Remove `.pdf`, `.docx`, `.xlsx`, `.pptx` from `BINARY_EXTENSIONS`. Add `is_document()` check so `should_index` treats documents separately from binaries.

### 4.2 Markdown Parser
**Create:** `parser/documents/markdown.py` — No external deps (pure Python regex)

Extracts: headings (with levels and byte offsets), code blocks (with language tags), tables, links, YAML frontmatter. Heading hierarchy built like code parent-child.

### 4.3 Excel Parser
**Create:** `parser/documents/excel.py` — uses `openpyxl`

Extracts: sheets as sections, table headers, named ranges, formulas. Each sheet -> section, each table -> subsection.

### 4.4 Word Parser
**Create:** `parser/documents/word.py` — uses `python-docx`

Extracts: headings/sections with levels, tables, lists. Heading hierarchy maps to parent-child.

### 4.5 PowerPoint Parser
**Create:** `parser/documents/powerpoint.py` — uses `python-pptx`

Extracts: slides (title + content), speaker notes, tables. Each slide -> section.

### 4.6 PDF Parser
**Create:** `parser/documents/pdf.py` — uses `pymupdf`

Extracts: pages, headings (font-size heuristic), tables, links. Pages and headings -> sections.

### 4.7 CSV/TSV Parser
**Create:** `parser/documents/csv_parser.py` — stdlib `csv`

Extracts: column headers, row count, inferred data types, sample rows (first 5).

### Document Tools (3 new)
**Create:** `tools/get_document_outline.py`, `tools/get_document_section.py`, `tools/search_documents.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_document_outline` | `repo_path`, `file_path` | Section hierarchy of a document |
| `get_document_section` | `repo_path`, `section_id` | Retrieve specific section content via byte offsets |
| `search_documents` | `repo_path`, `query`, `format?`, `max_results=20` | Search document sections by title/content |

---

## Phase 5: Infrastructure

### 5.1 Watch Mode / Auto-Reindex
**Create:** `watcher.py`
**Modify:** `server.py`

Async `watchfiles`-based filesystem watcher. Debounced incremental re-index (2s delay).

| Tool | Parameters | Description |
|------|-----------|-------------|
| `watch_repo` | `repo_path`, `action="start"/"stop"` | Start/stop watching a repo for changes |

### 5.2 Export Formats
**Create:** `tools/export_diagram.py`, `tools/export_docs.py`
**Modify:** `server.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `export_diagram` | `repo_path`, `type` (class_hierarchy/call_graph/imports), `file_pattern?` | Returns Mermaid markdown diagram |
| `export_docs` | `repo_path`, `file_pattern?`, `format="markdown"` | Generates markdown documentation from index |

No external deps — generates Mermaid strings and markdown directly.

### 5.3 Multi-Repo Cross-References
**Create:** `tools/cross_repo.py`
**Modify:** `storage/index_store.py`, `server.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `resolve_cross_repo` | `repo_path`, `import_string` | Resolve import to symbol in another indexed repo |

Iterates all indexed repos, searches for matching symbol. Caches results.

### 5.4 Test Coverage Mapping
**Create:** `tools/get_test_coverage.py`
**Modify:** `server.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_test_coverage` | `repo_path`, `symbol_id` | Find test files/functions for a symbol via naming conventions + imports + call graph |

Implementation:
1. Extract symbol name and file path from `symbol_id`
2. Search for test files: `test_{name}.py`, `{name}_test.py`, `{name}.test.ts`, etc.
3. Check if test files import the symbol's module
4. If call graph available, check if test functions call the target symbol
5. Return matched test files and test functions

---

## Dependency Changes

```toml
[project]
dependencies = [
    "mcp[cli]>=1.0.0",
    "tree-sitter-language-pack>=0.6.0",
    "pathspec>=0.12.0",
    "pyyaml>=6.0",
    "orjson>=3.9",             # NEW: fast JSON serialization
    "rapidfuzz>=3.0",          # NEW: fuzzy search
]

[project.optional-dependencies]
tokens = ["tiktoken>=0.7"]
docs = [
    "openpyxl>=3.1",
    "python-docx>=1.0",
    "python-pptx>=1.0",
    "pymupdf>=1.24",
]
watch = ["watchfiles>=0.21"]
all = ["snip-mcp[tokens,docs,watch]"]
```

---

## New Files Summary

```
src/snip_mcp/
├── parser/
│   ├── call_graph.py               # Phase 2: call graph builder
│   ├── resolver.py                 # Phase 2: cross-file symbol resolution
│   └── documents/                  # Phase 4: document parsing
│       ├── __init__.py
│       ├── base.py                 # DocumentSection, DocumentFile, DocumentParser ABC
│       ├── registry.py             # Parser registry & dispatch
│       ├── markdown.py
│       ├── excel.py
│       ├── word.py
│       ├── powerpoint.py
│       ├── pdf.py
│       └── csv_parser.py
├── tools/
│   ├── get_call_graph.py           # Phase 2
│   ├── get_callers.py              # Phase 2
│   ├── get_change_impact.py        # Phase 2
│   ├── search_annotations.py       # Phase 3
│   ├── get_changes.py              # Phase 3
│   ├── get_document_outline.py     # Phase 4
│   ├── get_document_section.py     # Phase 4
│   ├── search_documents.py         # Phase 4
│   ├── export_diagram.py           # Phase 5
│   ├── export_docs.py              # Phase 5
│   ├── cross_repo.py               # Phase 5
│   └── get_test_coverage.py        # Phase 5
└── watcher.py                      # Phase 5
```

---

## All 28 MCP Tools (15 existing + 13 new)

### Existing (15)
| # | Tool | Category |
|---|------|----------|
| 1 | `index_folder` | Setup |
| 2 | `list_repos` | Browse |
| 3 | `get_file_tree` | Browse |
| 4 | `get_file_outline` | Browse |
| 5 | `get_file_content` | Read |
| 6 | `get_repo_outline` | Browse |
| 7 | `get_symbol` | Read |
| 8 | `get_symbols` | Read |
| 9 | `search_symbols` | Search |
| 10 | `search_text` | Search |
| 11 | `search_columns` | Search |
| 12 | `find_importers` | Search |
| 13 | `find_references` | Search |
| 14 | `invalidate_cache` | Manage |
| 15 | `get_stats` | Manage |

### New (13)
| # | Tool | Phase | Category |
|---|------|-------|----------|
| 16 | `get_call_graph` | 2 | Intelligence |
| 17 | `get_callers` | 2 | Intelligence |
| 18 | `get_change_impact` | 2 | Intelligence |
| 19 | `search_annotations` | 3 | Search |
| 20 | `get_changes` | 3 | Search |
| 21 | `get_document_outline` | 4 | Documents |
| 22 | `get_document_section` | 4 | Documents |
| 23 | `search_documents` | 4 | Documents |
| 24 | `watch_repo` | 5 | Manage |
| 25 | `export_diagram` | 5 | Export |
| 26 | `export_docs` | 5 | Export |
| 27 | `resolve_cross_repo` | 5 | Intelligence |
| 28 | `get_test_coverage` | 5 | Intelligence |

---

## Phase Dependencies & Execution Order

```
Phase 1 (parallel, no deps):
  1.1 Languages ──┐
  1.2 Compression ─┤── can all run in parallel
  1.3 Token count ─┘

Phase 2 (sequential):
  2.1 Type info -> 2.2 Call graph -> 2.3 Resolution -> 2.4 Change impact

Phase 3 (mostly parallel, after Phase 2):
  3.1 Fuzzy search ──┐
  3.2 Annotations ────┤── parallel
  3.3 Changelog ──────┘ (needs Phase 2 for symbol hashes)

Phase 4 (sequential then parallel):
  4.1 Framework -> 4.2-4.7 Parsers (parallel) -> Document tools

Phase 5 (parallel, after Phase 2+4):
  5.1 Watch mode ──┐
  5.2 Export ───────┤── parallel
  5.3 Multi-repo ──┤
  5.4 Test coverage┘
```

---

## Testing Strategy

- **Per-feature unit tests** following existing `tests/test_*.py` patterns
- **Fixture files**: new language samples (.rb, .kt, .swift, .php, .scala, .lua, .sh) + document samples (.md, .xlsx, .docx, .pptx, .pdf, .csv) + multi-file Python project for call graph
- **Backward compatibility test**: Load a v1 JSON index, verify all new fields default correctly
- **Integration test**: Index a fixture project end-to-end, exercise call graph -> change impact -> export flow
- **Optional deps**: Use `pytest.importorskip()` for tests requiring tiktoken/openpyxl/etc.

---

## Verification Per Phase

After each phase:
1. `uv run pytest` — all tests pass
2. `uv run ruff format . && uv run ruff check --fix .` — clean
3. `uv run snip-mcp` — server boots without errors
4. `index_folder` on a test repo — succeeds
5. New tools return expected results
6. Old indexes still load (backward compat)
