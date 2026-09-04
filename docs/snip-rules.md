# Rule: Snip MCP — Preferred Code Retrieval

## Purpose

Snip MCP is a local code indexing server (v0.1.0, 29 tools) that saves context window tokens by returning only the specific symbols, documents, or code sections you need instead of reading entire files. It uses tree-sitter AST parsing for O(1) byte-offset retrieval, saving 87-96% of tokens. **Always prefer Snip tools over built-in Read/Grep/Glob when working with indexed codebases.**

## Complete Tool Reference (29 tools)

### Setup & Browse (5 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `index_folder` | — | Scan a folder and build/update the code index (incremental — only re-parses changed files) |
| `list_repos` | — | List all locally indexed folders with statistics |
| `get_file_tree` | `ls`/`Glob` | Directory tree view with language annotations and optional symbol counts |
| `get_repo_outline` | — | High-level repo overview: languages, symbol distribution, top files |
| `get_file_outline` | Reading whole file | Symbol hierarchy for a file (functions, classes, methods with signatures) |

### Read (3 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `get_file_content` | `Read` | Get file content with optional line range (more efficient for indexed repos) |
| `get_symbol` | `Read` | Retrieve single symbol via O(1) byte-offset seek (saves 80-95% tokens) |
| `get_symbols` | Multiple `Read` calls | Batch retrieve multiple symbols in one call |

### Search (7 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `search_symbols` | `Grep` | Weighted fuzzy symbol search (exact +100, prefix +20, substring +10, signature +8) |
| `search_text` | `Grep` | Full-text search with context lines, regex support, case-sensitive mode |
| `search_columns` | `Grep` | Search column metadata from dbt/schema files |
| `search_annotations` | `Grep` | Find symbols by decorator/annotation (e.g., `@pytest.mark`, `@router.get`) |
| `find_importers` | `Grep` | Reverse import graph: who imports a given module/file |
| `find_references` | `Grep` | Find all usages of a symbol name (word-boundary matching) |
| `search_documents` | `Grep` on docs | Search document sections by title/content (Markdown, Excel, Word, PDF, CSV) |

### Code Intelligence (5 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `get_call_graph` | Manual tracing | What does a symbol call? Returns callees with depth traversal |
| `get_callers` | `Grep` for function name | Who calls this symbol? Reverse call graph lookup |
| `get_change_impact` | Manual diff analysis | Identifies changed symbols, finds dependents via call graph |
| `get_test_coverage` | Manual search | Find test files/functions for a symbol via naming, imports, call graph |
| `get_dead_code` | Manual audit | Detect unused symbols (zero callers, not imported, not entry points) and circular imports |

### Documents (3 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `get_document_outline` | Reading whole doc | Section hierarchy of a document (Markdown, Excel, Word, PDF, CSV) |
| `get_document_section` | `Read` with offset | Retrieve specific document section content by section ID |
| `get_changes` | `git diff` | Symbols added/modified/removed since last index (requires 2+ index runs) |

### Export & Manage (6 tools)
| Tool | Use Instead Of | Purpose |
|------|---------------|---------|
| `export_diagram` | Manual Mermaid | Generate Mermaid diagrams: class hierarchy, call graph, or imports |
| `export_docs` | Manual writing | Generate markdown documentation from the code index |
| `resolve_cross_repo` | Manual tracing | Resolve imports across indexed repos |
| `watch_repo` | Manual reindex | Start/stop auto-reindexing on file changes |
| `invalidate_cache` | — | Delete cached index, force full re-index next time |
| `get_stats` | — | Session and cumulative token savings statistics |

## When to Use Snip

### ALWAYS use Snip for:
- **Finding a function/class/method by name** — `search_symbols` instead of Grep
- **Reading a specific function or class** — `get_symbol` instead of Read
- **Reading multiple symbols** — `get_symbols` to batch-retrieve
- **Getting a file's structure/outline** — `get_file_outline` instead of reading the whole file
- **Exploring a project structure** — `get_file_tree` or `get_repo_outline`
- **Searching code content** — `search_text` instead of Grep for indexed repos
- **Finding who imports a module** — `find_importers`
- **Finding all usages of a symbol** — `find_references`
- **Searching column metadata** — `search_columns` for dbt/schema files
- **Finding decorated/annotated code** — `search_annotations` (e.g., `@pytest.mark`, `@task`)
- **Understanding call chains** — `get_call_graph` (callees) and `get_callers` (reverse)
- **Pre-refactor impact analysis** — `get_change_impact` to see what depends on changed code
- **Finding tests for a symbol** — `get_test_coverage` links tests via naming, imports, call graph
- **Detecting unused code** — `get_dead_code` finds zero-caller symbols and circular imports
- **Reading document sections** — `search_documents` + `get_document_section` for Markdown, Excel, Word, PDF, CSV
- **Generating architecture diagrams** — `export_diagram` for Mermaid class/call/import diagrams
- **Generating API docs** — `export_docs` for markdown documentation from code

### Use built-in tools ONLY when:
- The file is **not in an indexed repo** (e.g., config files, generated JSON)
- You need to **edit a file** (Snip is read-only — use Edit tool for modifications)
- You need to **create or write files** (use Write tool)
- The repo has **not been indexed yet** (index it first with `index_folder`)

**Note:** Snip now indexes documents (Markdown, Excel, Word, PDF, CSV) — so for indexed repos, prefer `search_documents` + `get_document_section` even for non-code files.

## Workflow

### First time working with a codebase
1. Check if already indexed: `list_repos`
2. If not indexed: `index_folder` with the repo path
3. Then use Snip tools for all code exploration

### Typical code exploration pattern
1. `get_repo_outline` — understand the project structure
2. `search_symbols` — find the function/class you need
3. `get_symbol` — read just that symbol's source code
4. `find_references` — see where it's used
5. `get_call_graph` / `get_callers` — understand dependency chain
6. Only use Read tool if you need to see the full file for editing context

### Pre-refactor workflow
1. `get_change_impact` — see what's affected by your changes
2. `get_callers` — who calls the symbol you're changing
3. `get_test_coverage` — which tests cover this code
4. `export_diagram type="call_graph"` — visualize the dependency chain
5. Make changes, then `get_dead_code` — check nothing became orphaned

### Document exploration workflow
1. `search_documents` — find relevant document sections across the repo
2. `get_document_outline` — see the section structure of a specific document
3. `get_document_section` — read a specific section by ID

## Indexed Repositories

<!-- Add your team's repos here -->
| Repo | Path | Purpose |
|------|------|---------|
| my-project | `/path/to/my-project` | Example — replace with your repos |

If a repo is not indexed when needed, index it first: `index_folder` with `folder_path` set to the repo path.

## Supported Languages (23)

Python, JavaScript, TypeScript, TSX, Go, Rust, Java, C#, C, C++, SQL, Ruby, Kotlin, Swift, PHP, Scala, Lua, Bash, HTML, CSS, YAML, JSON, TOML

## Supported Document Formats

Markdown, Excel (.xlsx), Word (.docx), PowerPoint (.pptx), PDF, CSV — requires `[docs]` or `[all]` optional dependencies.

## Token Savings Tracking

- Use `get_stats` to check how many tokens Snip has saved in the current session
- The status bar at the bottom of the terminal shows live savings if the statusline is configured

## Key Principle

**Every time you are about to use Read or Grep to look at source code in an indexed repo, stop and use the equivalent Snip tool instead.** The savings compound — a session with 50 code lookups might save 100K+ tokens, which is real context window space that keeps the conversation coherent for longer.
