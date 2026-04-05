"""CLI entry point for snip-mcp-index — run indexing from the command line."""

from __future__ import annotations

import json
import sys


def main() -> None:
    """Index a folder from the command line.

    Usage:
        snip-mcp-index <folder_path> [--force] [--max-files N]
    """
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage: snip-mcp-index <folder_path> [--force] [--max-files N]")
        print()
        print("Index a local folder using tree-sitter AST parsing.")
        print()
        print("Arguments:")
        print("  folder_path    Absolute path to the folder to index")
        print()
        print("Options:")
        print("  --force        Re-index all files, ignoring cache")
        print("  --max-files N  Maximum number of files to index (default: 50000)")
        print("  -h, --help     Show this help message")
        sys.exit(0)

    folder_path = args[0]
    force = "--force" in args
    max_files = 50000

    if "--max-files" in args:
        idx = args.index("--max-files")
        if idx + 1 < len(args):
            try:
                max_files = int(args[idx + 1])
            except ValueError:
                print(f"Error: --max-files requires an integer, got '{args[idx + 1]}'", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: --max-files requires a value", file=sys.stderr)
            sys.exit(1)

    from snip_mcp.tools.index_folder import index_folder

    result = index_folder(folder_path, force=force, max_files=max_files)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
