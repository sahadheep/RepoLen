import networkx as nx


def build_graph(files_with_imports: list[tuple[str, list[str]]]) -> nx.DiGraph:
    graph = nx.DiGraph()
    all_paths = {path for path, _ in files_with_imports}
    for path in all_paths:
        graph.add_node(path)

    path_lookup = _build_path_lookup(all_paths)

    for from_path, imports in files_with_imports:
        for module in imports:
            resolved = _resolve_module(module, from_path, path_lookup)
            if resolved and resolved != from_path:
                graph.add_edge(from_path, resolved)

    return graph


def _build_path_lookup(all_paths: set[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for path in all_paths:
        no_ext = path.replace("\\", "/")
        if no_ext.endswith(".py") or no_ext.endswith(".js"):
            no_ext = no_ext.rsplit(".", 1)[0]

        lookup[no_ext] = path
        lookup[no_ext.replace("/", ".")] = path
        lookup[no_ext.split("/")[-1]] = path
        lookup[no_ext.split("/")[-1].replace("-", "_")] = path

    return lookup


def _resolve_module(module: str, from_path: str, lookup: dict[str, str]) -> str | None:
    module = module.strip().replace("\\", "/")

    if module in lookup:
        return lookup[module]

    clean = module.lstrip("./")
    if clean in lookup:
        return lookup[clean]

    last = module.split(".")[-1].split("/")[-1]
    if last in lookup:
        return lookup[last]

    return None


def rank_files(graph: nx.DiGraph, top_n: int = 10) -> list[tuple[str, float]]:
    if len(graph.nodes) < 2:
        ranked = sorted(
            ((n, float(graph.in_degree(n))) for n in graph.nodes),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_n]

    try:
        scores = nx.pagerank(graph, alpha=0.85, max_iter=100)
    except nx.PowerIterationFailedConvergence:
        scores = {n: float(graph.in_degree(n)) for n in graph.nodes}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


def get_graph_stats(graph: nx.DiGraph) -> dict:
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "is_dag": nx.is_directed_acyclic_graph(graph),
    }
