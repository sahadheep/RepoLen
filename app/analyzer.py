from pathlib import Path

from app import database, embedder
from app.parser import parse_file
from app.graph import build_graph, rank_files
from app.utils import clone_repo, walk_source_files, hash_file


def analyze_repo(url: str) -> dict:
    url = url.strip().rstrip("/")
    if not url.startswith("https://github.com/"):
        raise ValueError("Only public GitHub URLs are supported (https://github.com/…)")

    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("URL must be in the form https://github.com/owner/repo")

    clone_path = clone_repo(url)

    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO repos (url, clone_path) VALUES (?, ?)",
            (url, str(clone_path)),
        )
        cursor.execute(
            "UPDATE repos SET updated_at = datetime('now') WHERE url = ?", (url,)
        )
        conn.commit()
        cursor.execute("SELECT id FROM repos WHERE url = ?", (url,))
        repo_id = cursor.fetchone()["id"]

        source_files = walk_source_files(clone_path)
        if not source_files:
            raise ValueError("No Python or JavaScript files found in this repo.")

        processed = 0
        skipped = 0
        all_file_imports: list[tuple[str, list[str]]] = []

        for file_path, language in source_files:
            rel_path = str(file_path.relative_to(clone_path))
            new_hash = hash_file(file_path)

            cursor.execute(
                "SELECT id, file_hash FROM files WHERE repo_id = ? AND path = ?",
                (repo_id, rel_path),
            )
            existing = cursor.fetchone()

            if existing and existing["file_hash"] == new_hash:
                skipped += 1
                cursor.execute(
                    "SELECT to_module FROM imports WHERE repo_id = ? AND from_file = ?",
                    (repo_id, rel_path),
                )
                cached_imports = [r["to_module"] for r in cursor.fetchall()]
                all_file_imports.append((rel_path, cached_imports))
                continue

            analysis = parse_file(file_path, clone_path)
            if analysis is None:
                continue

            if existing:
                file_id = existing["id"]
                cursor.execute(
                    "UPDATE files SET file_hash = ? WHERE id = ?",
                    (new_hash, file_id),
                )
                cursor.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
                cursor.execute(
                    "DELETE FROM imports WHERE repo_id = ? AND from_file = ?",
                    (repo_id, rel_path),
                )
            else:
                cursor.execute(
                    "INSERT INTO files (repo_id, path, language, file_hash) VALUES (?, ?, ?, ?)",
                    (repo_id, rel_path, language, new_hash),
                )
                file_id = cursor.lastrowid

            for sym in analysis.symbols:
                cursor.execute(
                    """INSERT INTO symbols (file_id, kind, name, start_line, end_line, source)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (file_id, sym.kind, sym.name, sym.start_line, sym.end_line, sym.source),
                )

            for imp in analysis.imports:
                cursor.execute(
                    "INSERT INTO imports (repo_id, from_file, to_module) VALUES (?, ?, ?)",
                    (repo_id, rel_path, imp),
                )

            all_file_imports.append((rel_path, analysis.imports))
            processed += 1
            conn.commit()

        print(f"[ANALYZE] {processed} files processed, {skipped} unchanged (skipped)")

        if not all_file_imports:
            cursor.execute(
                "SELECT path FROM files WHERE repo_id = ?", (repo_id,)
            )
            all_paths = [r["path"] for r in cursor.fetchall()]
            all_file_imports = []
            for p in all_paths:
                cursor.execute(
                    "SELECT to_module FROM imports WHERE repo_id = ? AND from_file = ?",
                    (repo_id, p),
                )
                imps = [r["to_module"] for r in cursor.fetchall()]
                all_file_imports.append((p, imps))

        embedder.embed_symbols(conn, repo_id)

        total_files = processed + skipped
        return {
            "repo_id": repo_id,
            "url": url,
            "files_processed": total_files,
            "message": f"Done. {processed} files parsed, {skipped} unchanged (skipped).",
        }

    finally:
        conn.close()
