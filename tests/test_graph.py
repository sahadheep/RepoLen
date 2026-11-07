"""
test_graph.py — Tests for the dependency graph and PageRank ranking.
"""

import pytest
import networkx as nx

from app.graph import build_graph, rank_files, _build_path_lookup, _resolve_module


class TestBuildGraph:

    def test_simple_edge(self):
        """A imports B creates an edge A → B."""
        data = [
            ("app/main.py",  ["app.utils"]),
            ("app/utils.py", []),
        ]
        graph = build_graph(data)
        assert "app/main.py"  in graph.nodes
        assert "app/utils.py" in graph.nodes
        # There should be an edge from main to utils
        assert graph.has_edge("app/main.py", "app/utils.py")

    def test_no_self_loops(self):
        """A file shouldn't import itself."""
        data = [("utils.py", ["utils"])]
        graph = build_graph(data)
        assert not graph.has_edge("utils.py", "utils.py")

    def test_isolated_nodes(self):
        """Files with no imports are still added as nodes."""
        data = [
            ("a.py", []),
            ("b.py", []),
        ]
        graph = build_graph(data)
        assert "a.py" in graph.nodes
        assert "b.py" in graph.nodes
        assert graph.number_of_edges() == 0

    def test_multiple_imports(self):
        """One file can import multiple others."""
        data = [
            ("main.py",   ["utils", "models", "config"]),
            ("utils.py",  []),
            ("models.py", []),
            ("config.py", []),
        ]
        graph = build_graph(data)
        # main should have 3 outgoing edges
        assert graph.out_degree("main.py") == 3


class TestRankFiles:

    def test_most_imported_ranks_first(self):
        """The file imported by the most others should rank first."""
        # utils is imported by everyone → most important
        data = [
            ("main.py",    ["utils"]),
            ("server.py",  ["utils"]),
            ("helpers.py", ["utils"]),
            ("utils.py",   []),
        ]
        graph = build_graph(data)
        ranked = rank_files(graph, top_n=4)
        top_file = ranked[0][0]
        assert top_file == "utils.py"

    def test_returns_top_n(self):
        """rank_files respects the top_n parameter."""
        data = [(f"file{i}.py", []) for i in range(20)]
        graph = build_graph(data)
        ranked = rank_files(graph, top_n=5)
        assert len(ranked) <= 5

    def test_single_node_graph(self):
        """rank_files works on a graph with just one file."""
        graph = build_graph([("only.py", [])])
        ranked = rank_files(graph, top_n=10)
        assert len(ranked) == 1
        assert ranked[0][0] == "only.py"

    def test_scores_are_floats(self):
        """Scores returned by rank_files are floats."""
        data = [("a.py", ["b"]), ("b.py", [])]
        graph = build_graph(data)
        ranked = rank_files(graph)
        for _, score in ranked:
            assert isinstance(score, float)


class TestPathLookup:

    def test_basename_lookup(self):
        """A path 'app/utils.py' should be findable by 'utils'."""
        paths = {"app/utils.py"}
        lookup = _build_path_lookup(paths)
        resolved = _resolve_module("utils", "app/main.py", lookup)
        assert resolved == "app/utils.py"

    def test_dotted_lookup(self):
        """A path 'app/utils.py' should be findable by 'app.utils'."""
        paths = {"app/utils.py"}
        lookup = _build_path_lookup(paths)
        resolved = _resolve_module("app.utils", "other.py", lookup)
        assert resolved == "app/utils.py"

    def test_external_module_returns_none(self):
        """External modules (like 'os', 'numpy') should return None."""
        paths = {"main.py"}
        lookup = _build_path_lookup(paths)
        resolved = _resolve_module("numpy", "main.py", lookup)
        assert resolved is None
