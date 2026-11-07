import io
import sqlite3
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[EMBED] Loading model '{MODEL_NAME}' (first run may download it)…")
        _model = SentenceTransformer(MODEL_NAME)
        print("[EMBED] Model ready.")
    return _model


def _array_to_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr.astype(np.float32))
    return buf.getvalue()


def _bytes_to_array(data: bytes) -> np.ndarray:
    buf = io.BytesIO(data)
    return np.load(buf)


def embed_text(text: str) -> np.ndarray:
    model = get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.astype(np.float32)


def embed_symbols(conn: sqlite3.Connection, repo_id: int) -> int:
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.kind, s.name, s.source
        FROM symbols s
        JOIN files f ON f.id = s.file_id
        WHERE f.repo_id = ?
          AND s.id NOT IN (SELECT symbol_id FROM embeddings)
    """, (repo_id,))
    rows = cursor.fetchall()

    if not rows:
        return 0

    texts = []
    ids = []
    for row in rows:
        text = f"{row['kind']} {row['name']}:\n{row['source'][:1000]}"
        texts.append(text)
        ids.append(row["id"])

    print(f"[EMBED] Embedding {len(texts)} symbols…")
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    for sym_id, vec in zip(ids, vectors):
        blob = _array_to_bytes(vec.astype(np.float32))
        cursor.execute(
            "INSERT OR REPLACE INTO embeddings (symbol_id, vector) VALUES (?, ?)",
            (sym_id, blob),
        )

    conn.commit()
    print(f"[EMBED] Saved {len(ids)} embeddings.")
    return len(ids)


def search(
    conn: sqlite3.Connection,
    repo_id: int,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    cursor = conn.cursor()
    query_vec = embed_text(query)

    cursor.execute("""
        SELECT
            e.symbol_id,
            e.vector,
            s.name    AS symbol_name,
            s.kind,
            s.start_line,
            s.end_line,
            s.source,
            f.path    AS file_path
        FROM embeddings e
        JOIN symbols  s ON s.id = e.symbol_id
        JOIN files    f ON f.id = s.file_id
        WHERE f.repo_id = ?
    """, (repo_id,))
    rows = cursor.fetchall()

    if not rows:
        return []

    vecs = np.stack([_bytes_to_array(row["vector"]) for row in rows])
    scores = vecs @ query_vec
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        row = rows[int(idx)]
        results.append({
            "file_path":   row["file_path"],
            "symbol_name": row["symbol_name"],
            "kind":        row["kind"],
            "start_line":  row["start_line"],
            "end_line":    row["end_line"],
            "score":       float(scores[idx]),
            "snippet":     row["source"][:300],
        })

    return results
