from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import database
from app import analyzer as repo_analyzer
from app import embedder
from app.graph import build_graph, rank_files
from app.models import (
    AnalyzeRequest, AnalyzeResponse,
    StructureResponse, FileInfo, SymbolInfo,
    ImportantFilesResponse, ImportantFile,
    SearchRequest, SearchResponse, SearchResult,
)

app = FastAPI(
    title="RepoLens",
    description="A code analysis engine: give it a GitHub repo, explore its structure.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    database.init_db()


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "message": "RepoLens is running. POST /analyze to start."}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
def analyze(request: AnalyzeRequest):
    try:
        result = repo_analyzer.analyze_repo(request.url)
        return AnalyzeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@app.get("/repos/{repo_id}/structure", response_model=StructureResponse, tags=["analysis"])
def structure(repo_id: int):
    conn = database.get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM repos WHERE id = ?", (repo_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Repo {repo_id} not found.")

        cursor.execute(
            "SELECT id, path, language FROM files WHERE repo_id = ?", (repo_id,)
        )
        files_rows = cursor.fetchall()

        result_files = []
        for file_row in files_rows:
            file_id = file_row["id"]

            cursor.execute(
                "SELECT kind, name, start_line, end_line FROM symbols WHERE file_id = ?",
                (file_id,),
            )
            symbols = [
                SymbolInfo(
                    kind=r["kind"],
                    name=r["name"],
                    start_line=r["start_line"],
                    end_line=r["end_line"],
                )
                for r in cursor.fetchall()
            ]

            cursor.execute(
                "SELECT to_module FROM imports WHERE repo_id = ? AND from_file = ?",
                (repo_id, file_row["path"]),
            )
            imports = [r["to_module"] for r in cursor.fetchall()]

            result_files.append(FileInfo(
                path=file_row["path"],
                language=file_row["language"],
                symbols=symbols,
                imports=imports,
            ))

        return StructureResponse(repo_id=repo_id, files=result_files)

    finally:
        conn.close()


@app.get("/repos/{repo_id}/important", response_model=ImportantFilesResponse, tags=["analysis"])
def important_files(repo_id: int):
    conn = database.get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM repos WHERE id = ?", (repo_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Repo {repo_id} not found.")

        cursor.execute("SELECT path FROM files WHERE repo_id = ?", (repo_id,))
        file_paths = [r["path"] for r in cursor.fetchall()]

        files_with_imports = []
        for path in file_paths:
            cursor.execute(
                "SELECT to_module FROM imports WHERE repo_id = ? AND from_file = ?",
                (repo_id, path),
            )
            imps = [r["to_module"] for r in cursor.fetchall()]
            files_with_imports.append((path, imps))

        graph = build_graph(files_with_imports)
        ranked = rank_files(graph, top_n=10)

        result = [
            ImportantFile(path=path, score=round(score, 6), rank=i + 1)
            for i, (path, score) in enumerate(ranked)
        ]

        return ImportantFilesResponse(repo_id=repo_id, files=result)

    finally:
        conn.close()


@app.post("/repos/{repo_id}/search", response_model=SearchResponse, tags=["search"])
def search(repo_id: int, request: SearchRequest):
    conn = database.get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM repos WHERE id = ?", (repo_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Repo {repo_id} not found.")

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM embeddings e
            JOIN symbols s ON s.id = e.symbol_id
            JOIN files f ON f.id = s.file_id
            WHERE f.repo_id = ?
        """, (repo_id,))
        if cursor.fetchone()["cnt"] == 0:
            raise HTTPException(
                status_code=400,
                detail="No embeddings found. Run POST /analyze first.",
            )

        raw_results = embedder.search(conn, repo_id, request.query, top_k=request.top_k)

        results = [
            SearchResult(
                file_path=r["file_path"],
                symbol_name=r["symbol_name"],
                kind=r["kind"],
                start_line=r["start_line"],
                end_line=r["end_line"],
                score=round(r["score"], 4),
                snippet=r["snippet"],
            )
            for r in raw_results
        ]

        return SearchResponse(repo_id=repo_id, query=request.query, results=results)

    finally:
        conn.close()


@app.get("/repos", tags=["analysis"])
def list_repos():
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.url, r.created_at, r.updated_at,
                   COUNT(DISTINCT f.id) AS file_count,
                   COUNT(DISTINCT s.id) AS symbol_count
            FROM repos r
            LEFT JOIN files   f ON f.repo_id = r.id
            LEFT JOIN symbols s ON s.file_id = f.id
            GROUP BY r.id
            ORDER BY r.updated_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
