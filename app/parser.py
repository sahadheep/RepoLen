from pathlib import Path
from dataclasses import dataclass, field

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser


PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())


@dataclass
class Symbol:
    kind: str
    name: str
    start_line: int
    end_line: int
    source: str


@dataclass
class FileAnalysis:
    path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def _make_parser(language: Language) -> Parser:
    return Parser(language)


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _first_named_child_text(node, kind: str, source_bytes: bytes) -> str | None:
    for child in node.children:
        if child.type == kind:
            return _node_text(child, source_bytes)
    return None


def _parse_python(source: str) -> tuple[list[Symbol], list[str]]:
    parser = _make_parser(PY_LANGUAGE)
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    symbols: list[Symbol] = []
    imports: list[str] = []

    def visit(node, depth: int = 0):
        if depth > 2:
            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            symbols.append(Symbol(
                kind="function",
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_node_text(node, source_bytes),
            ))

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            symbols.append(Symbol(
                kind="class",
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_node_text(node, source_bytes),
            ))
            for child in node.children:
                visit(child, depth + 1)
            return

        elif node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    raw = _node_text(child, source_bytes)
                    imports.append(raw.split(" as ")[0].strip())

        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node:
                imports.append(_node_text(module_node, source_bytes))

        for child in node.children:
            visit(child, depth)

    visit(root)
    return symbols, imports


def _parse_javascript(source: str) -> tuple[list[Symbol], list[str]]:
    parser = _make_parser(JS_LANGUAGE)
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    symbols: list[Symbol] = []
    imports: list[str] = []

    def visit(node, depth: int = 0):
        if depth > 3:
            return

        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            symbols.append(Symbol(
                kind="function",
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_node_text(node, source_bytes),
            ))

        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            symbols.append(Symbol(
                kind="class",
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_node_text(node, source_bytes),
            ))
            for child in node.children:
                visit(child, depth + 1)
            return

        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            symbols.append(Symbol(
                kind="function",
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_node_text(node, source_bytes),
            ))

        elif node.type in ("lexical_declaration", "variable_declaration"):
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    if name_node and value_node and value_node.type in (
                        "arrow_function", "function_expression"
                    ):
                        name = _node_text(name_node, source_bytes)
                        symbols.append(Symbol(
                            kind="function",
                            name=name,
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                            source=_node_text(child, source_bytes),
                        ))

        elif node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                raw = _node_text(source_node, source_bytes).strip("'\"")
                imports.append(raw)

        elif node.type == "call_expression":
            fn = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")
            if fn and _node_text(fn, source_bytes) == "require" and args:
                for arg in args.children:
                    if arg.type == "string":
                        raw = _node_text(arg, source_bytes).strip("'\"")
                        imports.append(raw)

        for child in node.children:
            visit(child, depth)

    visit(root)
    return symbols, imports


def parse_file(file_path: Path, repo_root: Path) -> FileAnalysis | None:
    lang_map = {".py": "python", ".js": "javascript"}
    language = lang_map.get(file_path.suffix.lower())
    if not language:
        return None

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[PARSER] Could not read {file_path}: {e}")
        return None

    if len(source.strip()) < 5:
        return None

    try:
        if language == "python":
            symbols, imports = _parse_python(source)
        else:
            symbols, imports = _parse_javascript(source)
    except Exception as e:
        print(f"[PARSER] Parse error in {file_path}: {e}")
        return None

    rel_path = str(file_path.relative_to(repo_root))

    return FileAnalysis(
        path=rel_path,
        language=language,
        symbols=symbols,
        imports=imports,
    )
