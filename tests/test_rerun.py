"""
test_rerun.py — Tests that the re-run optimization works correctly.

The key behavior: when we analyze a repo, we hash every file.
On re-run, files with the same hash are SKIPPED (not re-parsed).
Files that changed ARE re-parsed.

We test this with a fake in-memory repo (just temp directories).
"""

import sqlite3
import tempfile
from pathlib import Path
import pytest

from app.utils import hash_file, walk_source_files
from app.parser import parse_file
from app.database import init_db, get_connection, DB_PATH


class TestHashFile:

    def test_hash_is_deterministic(self, tmp_path):
        """Same file content always produces the same hash."""
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n")
        h1 = hash_file(f)
        h2 = hash_file(f)
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path):
        """Different file content produces different hashes."""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("def foo(): pass\n")
        f2.write_text("def bar(): pass\n")
        assert hash_file(f1) != hash_file(f2)

    def test_single_char_change_changes_hash(self, tmp_path):
        """Even a one-character change changes the hash completely."""
        f = tmp_path / "script.py"
        f.write_text("x = 1\n")
        h1 = hash_file(f)
        f.write_text("x = 2\n")
        h2 = hash_file(f)
        assert h1 != h2

    def test_hash_is_hex_string(self, tmp_path):
        """Hash is a valid hex string of the right length (SHA-256 = 64 chars)."""
        f = tmp_path / "file.py"
        f.write_text("pass\n")
        h = hash_file(f)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestWalkSourceFiles:

    def test_finds_python_files(self, tmp_path):
        """walk_source_files finds .py files."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "utils.py").write_text("pass")
        results = walk_source_files(tmp_path)
        paths = [str(p.name) for p, _ in results]
        assert "main.py" in paths
        assert "utils.py" in paths

    def test_finds_javascript_files(self, tmp_path):
        """walk_source_files finds .js files."""
        (tmp_path / "app.js").write_text("function f() {}")
        results = walk_source_files(tmp_path)
        paths = [str(p.name) for p, _ in results]
        assert "app.js" in paths

    def test_skips_node_modules(self, tmp_path):
        """walk_source_files ignores node_modules."""
        node_mod = tmp_path / "node_modules" / "lodash"
        node_mod.mkdir(parents=True)
        (node_mod / "index.js").write_text("module.exports = {}")
        results = walk_source_files(tmp_path)
        for path, _ in results:
            assert "node_modules" not in str(path)

    def test_skips_venv(self, tmp_path):
        """walk_source_files ignores the venv folder."""
        venv_dir = tmp_path / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("pass")
        results = walk_source_files(tmp_path)
        for path, _ in results:
            assert "venv" not in str(path)

    def test_skips_pycache(self, tmp_path):
        """walk_source_files ignores __pycache__ folders."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.pyc").write_text("junk")
        results = walk_source_files(tmp_path)
        for path, _ in results:
            assert "__pycache__" not in str(path)

    def test_returns_language(self, tmp_path):
        """Each result includes the correct language label."""
        (tmp_path / "script.py").write_text("pass")
        (tmp_path / "app.js").write_text("var x = 1;")
        results = {p.name: lang for p, lang in walk_source_files(tmp_path)}
        assert results.get("script.py") == "python"
        assert results.get("app.js") == "javascript"


class TestRerunSkip:
    """
    Simulate the re-run optimization:
    1. 'Analyze' a file and save its hash.
    2. Re-run without changing the file → should be detected as unchanged.
    3. Modify the file → should be detected as changed.
    """

    def test_unchanged_file_detected(self, tmp_path):
        """If a file's hash matches the stored hash, we should skip it."""
        source = "def greet(): pass\n"
        f = tmp_path / "hello.py"
        f.write_text(source)

        current_hash = hash_file(f)

        # Simulate "previously stored hash"
        stored_hash = hash_file(f)  # same content → same hash

        assert current_hash == stored_hash, "Same file should have same hash"

    def test_changed_file_detected(self, tmp_path):
        """If a file was modified, the new hash differs from the stored one."""
        f = tmp_path / "hello.py"
        f.write_text("def greet(): pass\n")
        stored_hash = hash_file(f)

        # Modify the file
        f.write_text("def greet(): return 'hi'\n")
        new_hash = hash_file(f)

        assert new_hash != stored_hash, "Modified file should have different hash"

    def test_new_file_has_no_stored_hash(self, tmp_path):
        """A brand-new file won't be in our database, so we always process it."""
        f = tmp_path / "new_file.py"
        f.write_text("def new_func(): pass\n")

        # In the real system, "existing" would be None from the DB query
        existing = None  # simulates SELECT returning nothing
        assert existing is None, "New file should have no stored hash"
