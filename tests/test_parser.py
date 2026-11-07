"""
test_parser.py — Tests for the tree-sitter parser.

We create tiny snippets of Python and JavaScript code in memory
(no files needed) and check that we extract the right things.
"""

import pytest
from pathlib import Path
import tempfile
import os

from app.parser import parse_file, _parse_python, _parse_javascript


# ── Python tests ─────────────────────────────────────────────────────────────

class TestPythonParsing:

    def test_simple_function(self):
        """Parser finds a basic function definition."""
        source = """\
def hello(name):
    return f"Hello, {name}"
"""
        symbols, imports = _parse_python(source)
        assert len(symbols) == 1
        assert symbols[0].name == "hello"
        assert symbols[0].kind == "function"
        assert symbols[0].start_line == 1

    def test_class_with_methods(self):
        """Parser finds a class and its methods."""
        source = """\
class Dog:
    def bark(self):
        print("Woof!")

    def sit(self):
        pass
"""
        symbols, imports = _parse_python(source)
        names = [s.name for s in symbols]
        assert "Dog" in names
        assert "bark" in names
        assert "sit" in names

    def test_import_statement(self):
        """Parser extracts regular imports."""
        source = "import os\nimport sys\n"
        _, imports = _parse_python(source)
        assert "os" in imports
        assert "sys" in imports

    def test_from_import(self):
        """Parser extracts from-imports."""
        source = "from pathlib import Path\nfrom app.utils import hash_file\n"
        _, imports = _parse_python(source)
        assert "pathlib" in imports
        assert "app.utils" in imports

    def test_multiple_functions(self):
        """Parser finds multiple top-level functions."""
        source = """\
def alpha():
    pass

def beta():
    pass

def gamma():
    pass
"""
        symbols, _ = _parse_python(source)
        names = [s.name for s in symbols]
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" in names

    def test_empty_file(self):
        """Parser handles an empty file without crashing."""
        symbols, imports = _parse_python("")
        assert symbols == []
        assert imports == []


# ── JavaScript tests ──────────────────────────────────────────────────────────

class TestJavaScriptParsing:

    def test_function_declaration(self):
        """Parser finds a regular JS function."""
        source = """\
function greet(name) {
    return "Hello " + name;
}
"""
        symbols, _ = _parse_javascript(source)
        assert any(s.name == "greet" and s.kind == "function" for s in symbols)

    def test_arrow_function(self):
        """Parser finds arrow functions assigned to variables."""
        source = "const add = (a, b) => a + b;\n"
        symbols, _ = _parse_javascript(source)
        assert any(s.name == "add" for s in symbols)

    def test_class_declaration(self):
        """Parser finds a JS class."""
        source = """\
class Animal {
    constructor(name) {
        this.name = name;
    }
    speak() {
        console.log(this.name);
    }
}
"""
        symbols, _ = _parse_javascript(source)
        names = [s.name for s in symbols]
        assert "Animal" in names

    def test_es_module_import(self):
        """Parser finds ES module imports."""
        source = "import express from 'express';\nimport { Router } from 'express';\n"
        _, imports = _parse_javascript(source)
        assert "express" in imports

    def test_require_import(self):
        """Parser finds CommonJS require() calls."""
        source = "const fs = require('fs');\nconst path = require('path');\n"
        _, imports = _parse_javascript(source)
        assert "fs" in imports
        assert "path" in imports


# ── parse_file integration test ───────────────────────────────────────────────

class TestParseFile:

    def test_parses_python_file(self, tmp_path):
        """parse_file correctly handles a real .py file on disk."""
        source = "def main():\n    pass\n"
        f = tmp_path / "script.py"
        f.write_text(source)

        result = parse_file(f, tmp_path)
        assert result is not None
        assert result.language == "python"
        assert result.path == "script.py"
        assert any(s.name == "main" for s in result.symbols)

    def test_parses_javascript_file(self, tmp_path):
        """parse_file correctly handles a real .js file on disk."""
        source = "function run() { return 42; }\n"
        f = tmp_path / "app.js"
        f.write_text(source)

        result = parse_file(f, tmp_path)
        assert result is not None
        assert result.language == "javascript"
        assert any(s.name == "run" for s in result.symbols)

    def test_skips_unsupported_extension(self, tmp_path):
        """parse_file returns None for unsupported file types."""
        f = tmp_path / "style.css"
        f.write_text("body { color: red; }")
        result = parse_file(f, tmp_path)
        assert result is None

    def test_skips_tiny_file(self, tmp_path):
        """parse_file returns None for nearly-empty files."""
        f = tmp_path / "empty.py"
        f.write_text("   ")
        result = parse_file(f, tmp_path)
        assert result is None
