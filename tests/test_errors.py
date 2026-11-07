"""
test_api_errors.py — Tests that the API handles bad inputs gracefully.

The analyzer raises ValueError for user errors (bad URL, private repo, etc.)
which main.py catches and converts to HTTP 400. We test that the error
messages are clear and the system doesn't crash.

We test the business logic directly (not through HTTP) so we don't need
a running server.
"""

import pytest
from pathlib import Path

from app.utils import walk_source_files, hash_file


class TestBadInputs:
    """Test that bad inputs produce clear error messages, not crashes."""

    def test_bad_url_format(self):
        """A URL that isn't GitHub should raise ValueError with a clear message."""
        from app.analyzer import analyze_repo
        with pytest.raises(ValueError, match="Only public GitHub URLs"):
            analyze_repo("https://gitlab.com/user/repo")

    def test_missing_repo_name(self):
        """A GitHub URL without a repo name should raise ValueError."""
        from app.analyzer import analyze_repo
        with pytest.raises(ValueError, match="owner/repo"):
            analyze_repo("https://github.com/justausername")

    def test_empty_url(self):
        """An empty string should raise ValueError."""
        from app.analyzer import analyze_repo
        with pytest.raises(ValueError):
            analyze_repo("")

    def test_non_github_url(self):
        """A plain non-URL string should raise ValueError."""
        from app.analyzer import analyze_repo
        with pytest.raises(ValueError):
            analyze_repo("not-a-url-at-all")

    def test_private_or_nonexistent_repo_raises(self):
        """
        A repo that doesn't exist should raise ValueError.
        
        We use a clearly fake repo name. This test requires internet access
        and a working git installation. It's marked slow because git clone
        takes a few seconds to time out.
        
        NOTE: If you're offline, this test will still pass because the
        clone attempt raises a GitCommandError which we convert to ValueError.
        """
        from app.analyzer import analyze_repo
        with pytest.raises(ValueError):
            analyze_repo("https://github.com/this-user-definitely-does-not-exist-xyzxyz/fake-repo-abc123")


class TestEmptyRepo:
    """Test behavior when a repo has no Python or JavaScript files."""

    def test_empty_directory_raises(self, tmp_path):
        """walk_source_files on an empty directory returns empty list."""
        results = walk_source_files(tmp_path)
        assert results == []

    def test_directory_with_only_txt_files_returns_empty(self, tmp_path):
        """walk_source_files ignores non-.py/.js files."""
        (tmp_path / "README.txt").write_text("hello")
        (tmp_path / "LICENSE").write_text("MIT")
        (tmp_path / "data.csv").write_text("a,b,c")
        results = walk_source_files(tmp_path)
        assert results == []

    def test_directory_with_only_skipped_folders_returns_empty(self, tmp_path):
        """walk_source_files returns empty if all .py files are in skipped folders."""
        node_mod = tmp_path / "node_modules" / "some_lib"
        node_mod.mkdir(parents=True)
        (node_mod / "index.js").write_text("module.exports = {}")

        venv_dir = tmp_path / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("pass")

        results = walk_source_files(tmp_path)
        assert results == [], "Files inside skipped folders should not be found"


class TestHashEdgeCases:
    """Edge cases for the file hashing used in re-run detection."""

    def test_binary_file_hashes_without_crash(self, tmp_path):
        """hash_file works on binary files without crashing."""
        f = tmp_path / "image.bin"
        f.write_bytes(bytes(range(256)))  # all byte values 0-255
        result = hash_file(f)
        assert len(result) == 64  # SHA-256 is always 64 hex chars

    def test_empty_file_has_stable_hash(self, tmp_path):
        """An empty file has a known, stable SHA-256 hash."""
        f = tmp_path / "empty.py"
        f.write_bytes(b"")
        result = hash_file(f)
        # SHA-256 of empty input is always this value
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result == expected

    def test_large_file_hashes_correctly(self, tmp_path):
        """hash_file handles files larger than the 64KB read chunk."""
        f = tmp_path / "big.py"
        # 200 KB of content
        content = "x = 1\n" * 33334
        f.write_text(content)
        result = hash_file(f)
        assert len(result) == 64
        # Hash should be the same if we read again
        assert hash_file(f) == result
