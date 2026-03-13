"""Tests for the security module."""

from __future__ import annotations

from pathlib import Path

import pytest

from snip_mcp.security import (
    is_binary,
    is_ignored,
    is_path_safe,
    load_ignore_patterns,
    looks_like_secret,
    safe_read,
    should_index,
)


class TestPathSafety:
    def test_safe_path(self, tmp_path: Path) -> None:
        child = tmp_path / "src" / "main.py"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        assert is_path_safe(child, tmp_path) is True

    def test_traversal_blocked(self, tmp_path: Path) -> None:
        malicious = tmp_path / ".." / "etc" / "passwd"
        assert is_path_safe(malicious, tmp_path) is False

    def test_same_as_root(self, tmp_path: Path) -> None:
        assert is_path_safe(tmp_path, tmp_path) is True


class TestSecretsDetection:
    @pytest.mark.parametrize(
        "filename",
        [".env", ".env.local", "id_rsa", "credentials.json", "service-account.json"],
    )
    def test_secret_filenames(self, tmp_path: Path, filename: str) -> None:
        f = tmp_path / filename
        f.touch()
        assert looks_like_secret(f, scan_content=False) is True

    @pytest.mark.parametrize("ext", [".pem", ".key", ".p12", ".pfx", ".keystore"])
    def test_secret_extensions(self, tmp_path: Path, ext: str) -> None:
        f = tmp_path / f"cert{ext}"
        f.touch()
        assert looks_like_secret(f, scan_content=False) is True

    def test_normal_file_not_secret(self, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text("print('hello')")
        assert looks_like_secret(f) is False

    def test_content_scan_detects_password(self, tmp_path: Path) -> None:
        f = tmp_path / "config.txt"
        f.write_text("password = mysecretpass\nother = value")
        assert looks_like_secret(f, scan_content=True) is True

    def test_content_scan_detects_aws_key(self, tmp_path: Path) -> None:
        f = tmp_path / "config.txt"
        f.write_text("aws_key = AKIAIOSFODNN7EXAMPLE")
        assert looks_like_secret(f, scan_content=True) is True


class TestBinaryDetection:
    @pytest.mark.parametrize("ext", [".exe", ".dll", ".png", ".zip", ".pdf"])
    def test_binary_extensions(self, tmp_path: Path, ext: str) -> None:
        f = tmp_path / f"file{ext}"
        f.touch()
        assert is_binary(f) is True

    def test_text_file_not_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text("print('hello')")
        assert is_binary(f) is False

    def test_null_byte_detection(self, tmp_path: Path) -> None:
        f = tmp_path / "mystery"
        f.write_bytes(b"hello\x00world")
        assert is_binary(f) is True


class TestSafeRead:
    def test_utf8_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert safe_read(f) == "hello world"

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nope.txt"
        assert safe_read(f) is None

    def test_too_large(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("x" * 100)
        assert safe_read(f, max_bytes=50) is None


class TestShouldIndex:
    def test_normal_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text("print('hello')")
        ok, reason = should_index(f, tmp_path)
        assert ok is True

    def test_rejects_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "app.exe"
        f.touch()
        ok, reason = should_index(f, tmp_path)
        assert ok is False
        assert "binary" in reason

    def test_rejects_secret(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("SECRET=value")
        ok, reason = should_index(f, tmp_path)
        assert ok is False
        assert "secret" in reason.lower()


class TestGitignore:
    def test_load_and_match(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__/\n*.pyc\n.env\n")
        spec = load_ignore_patterns(tmp_path)

        pyc_file = tmp_path / "module.pyc"
        pyc_file.touch()
        assert is_ignored(pyc_file, tmp_path, spec) is True

        py_file = tmp_path / "main.py"
        py_file.touch()
        assert is_ignored(py_file, tmp_path, spec) is False

    def test_no_gitignore(self, tmp_path: Path) -> None:
        spec = load_ignore_patterns(tmp_path)
        f = tmp_path / "anything.py"
        f.touch()
        assert is_ignored(f, tmp_path, spec) is False
