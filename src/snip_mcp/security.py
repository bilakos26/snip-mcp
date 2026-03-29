"""Security module for Snip MCP.

Path safety, secrets detection, binary detection, and file filtering.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pathspec

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB

SECRET_FILENAMES: set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".pgpass",
    ".my.cnf",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

# Extensions that indicate a secret key / certificate file.
SECRET_EXTENSIONS: set[str] = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
}

SECRET_CONTENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"password\s*=", re.IGNORECASE),
    re.compile(r"api_key\s*=", re.IGNORECASE),
    re.compile(r"secret\s*=", re.IGNORECASE),
    re.compile(r"token\s*=", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE KEY-----"),
]

BINARY_EXTENSIONS: set[str] = {
    # Executables / object code
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".o",
    ".obj",
    ".a",
    ".lib",
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    # Audio / Video
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    # Documents (legacy binary formats only — modern formats handled by doc parsers)
    ".doc",
    ".xls",
    ".ppt",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    # JVM
    ".class",
    ".jar",
    ".war",
    # Python bytecode / packages
    ".pyc",
    ".pyo",
    ".whl",
    ".egg",
}

DOCUMENT_EXTENSIONS: set[str] = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".csv",
    ".tsv",
}

# Number of initial lines to scan for secret content patterns.
_SECRET_SCAN_LINES: int = 10

# Number of bytes to read when probing for binary content (null bytes).
_BINARY_PROBE_BYTES: int = 8 * 1024


# ---------------------------------------------------------------------------
# Path traversal prevention
# ---------------------------------------------------------------------------


def is_path_safe(path: Path, root: Path) -> bool:
    """Return True if *path* resolves to a location under *root*.

    Symlinks are fully resolved before comparison so that symlink-based
    traversal attacks are caught.
    """
    try:
        resolved_path = path.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
        # Use os.path-style prefix check (works cross-platform).
        # We compare the resolved POSIX-like parts so that trailing separators
        # and case (on Windows) do not matter.  ``Path.is_relative_to`` was
        # added in Python 3.9 and handles these edge-cases correctly.
        return resolved_path.is_relative_to(resolved_root)
    except (OSError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Secrets detection
# ---------------------------------------------------------------------------


def looks_like_secret(filepath: Path, scan_content: bool = True) -> bool:
    """Return True if *filepath* looks like it contains secrets.

    Checks are performed in two stages:
    1. **Filename match** — the file name (or extension) matches a known
       secret pattern.
    2. **Content scan** (optional, enabled by default) — the first few lines
       of the file are scanned for patterns such as ``password=``, AWS access
       key IDs, or PEM private key headers.
    """
    name = filepath.name.lower()

    # Stage 1: filename / extension match
    if name in SECRET_FILENAMES:
        return True
    if filepath.suffix.lower() in SECRET_EXTENSIONS:
        return True

    # Stage 2: content scan (only for existing regular files)
    if scan_content and filepath.is_file():
        try:
            with filepath.open("r", encoding="utf-8", errors="ignore") as fh:
                for _, line in zip(range(_SECRET_SCAN_LINES), fh):
                    for pattern in SECRET_CONTENT_PATTERNS:
                        if pattern.search(line):
                            return True
        except OSError:
            # If we cannot read the file, err on the safe side and do not
            # flag it as a secret (the caller may decide differently).
            pass

    return False


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------


def is_document(filepath: Path) -> bool:
    """Return True if *filepath* is a supported document format."""
    return filepath.suffix.lower() in DOCUMENT_EXTENSIONS


def is_binary(filepath: Path) -> bool:
    """Return True if *filepath* appears to be a binary file.

    Uses a two-pronged check:
    1. Known binary extensions (excludes document formats handled by parsers).
    2. Null-byte probe — read the first 8 KB and look for ``\\x00``.
    """
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Probe actual content for null bytes (handles extensionless binaries).
    if filepath.is_file():
        try:
            with filepath.open("rb") as fh:
                chunk = fh.read(_BINARY_PROBE_BYTES)
                if b"\x00" in chunk:
                    return True
        except OSError:
            # Cannot read — assume not binary so other checks can decide.
            pass

    return False


# ---------------------------------------------------------------------------
# Encoding-safe file reading
# ---------------------------------------------------------------------------


def safe_read(filepath: Path, max_bytes: int = MAX_FILE_SIZE) -> Optional[str]:
    """Read *filepath* as text, returning the content string or ``None`` on failure.

    Attempts UTF-8 first, falling back to latin-1 (which never raises a
    decoding error).  If the file exceeds *max_bytes* or cannot be read,
    ``None`` is returned.
    """
    try:
        size = filepath.stat().st_size
        if size > max_bytes:
            return None
    except OSError:
        return None

    # Try UTF-8 first.
    try:
        return filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass
    except OSError:
        return None

    # Fallback to latin-1 (never raises UnicodeDecodeError).
    try:
        return filepath.read_text(encoding="latin-1")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Gitignore-aware filtering
# ---------------------------------------------------------------------------


def load_ignore_patterns(root: Path) -> pathspec.PathSpec:
    """Load ``.gitignore`` from *root* (if present) and return a ``PathSpec``.

    If the file does not exist or cannot be read, an empty spec (matching
    nothing) is returned.
    """
    gitignore = root / ".gitignore"
    lines: list[str] = []
    if gitignore.is_file():
        try:
            text = gitignore.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
        except OSError:
            pass

    return pathspec.PathSpec.from_lines("gitignore", lines)


def is_ignored(filepath: Path, root: Path, spec: pathspec.PathSpec) -> bool:
    """Return True if *filepath* matches the gitignore *spec* relative to *root*."""
    try:
        rel = filepath.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        # Path is not under root — not ignored by this spec, but also not safe.
        return False

    # pathspec expects forward-slash separated POSIX paths.
    return spec.match_file(rel.as_posix())


# ---------------------------------------------------------------------------
# Composite file-filtering predicate
# ---------------------------------------------------------------------------


def should_index(filepath: Path, root: Path) -> tuple[bool, str]:
    """Decide whether *filepath* should be indexed.

    Combines all safety and relevance checks:
    * Path is under *root* (traversal prevention).
    * Not a binary file.
    * Not a secrets file.
    * Not too large (> ``MAX_FILE_SIZE``).

    Returns ``(True, "ok")`` when the file is safe to index, or
    ``(False, reason)`` with a human-readable reason otherwise.
    """
    if not is_path_safe(filepath, root):
        return False, "path traversal: file is outside the project root"

    if not filepath.is_file():
        return False, "not a regular file"

    # Size check (before reading content).
    try:
        size = filepath.stat().st_size
    except OSError:
        return False, "unable to stat file"

    if size > MAX_FILE_SIZE:
        return False, f"file too large ({size} bytes, max {MAX_FILE_SIZE})"

    # Documents are binary but handled by dedicated parsers — let them through
    if is_document(filepath):
        return True, "ok"

    if is_binary(filepath):
        return False, "binary file"

    if looks_like_secret(filepath):
        return False, "file appears to contain secrets"

    return True, "ok"
