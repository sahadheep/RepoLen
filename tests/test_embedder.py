"""
test_embedder.py — Tests for the embedding and search functionality.

We avoid loading the full model in unit tests for speed. Instead:
- We test the numpy math directly (cosine similarity via dot product)
- We test byte serialization (saving/loading vectors from SQLite)
- We do one small integration test that loads the real model
"""

import io
import numpy as np
import pytest

from app.embedder import _array_to_bytes, _bytes_to_array, embed_text


class TestSerializiation:
    """Tests for converting numpy arrays to/from bytes (for SQLite storage)."""

    def test_round_trip(self):
        """A vector saved and loaded should be identical."""
        original = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        blob = _array_to_bytes(original)
        restored = _bytes_to_array(blob)
        np.testing.assert_array_almost_equal(original, restored)

    def test_returns_bytes(self):
        """_array_to_bytes returns bytes (for SQLite BLOB storage)."""
        arr = np.zeros(10, dtype=np.float32)
        result = _array_to_bytes(arr)
        assert isinstance(result, bytes)

    def test_large_vector(self):
        """Serialization works for the 384-dimensional vectors our model produces."""
        big = np.random.rand(384).astype(np.float32)
        blob = _array_to_bytes(big)
        restored = _bytes_to_array(blob)
        np.testing.assert_array_almost_equal(big, restored)


class TestCosineSimilarity:
    """
    Test the core math of semantic search.
    
    We don't call the model here — we just verify that the dot-product
    approach for cosine similarity works correctly with known vectors.
    """

    def test_identical_vectors_have_similarity_1(self):
        """A vector compared with itself should give cosine similarity 1.0."""
        v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        # L2-normalize (already normalized in this case)
        v_norm = v / np.linalg.norm(v)
        score = float(v_norm @ v_norm)
        assert abs(score - 1.0) < 1e-6

    def test_orthogonal_vectors_have_similarity_0(self):
        """Perpendicular vectors have cosine similarity 0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        score = float(a @ b)
        assert abs(score) < 1e-6

    def test_opposite_vectors_have_negative_similarity(self):
        """Opposite vectors have cosine similarity -1."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        score = float(a @ b)
        assert abs(score - (-1.0)) < 1e-6

    def test_batch_dot_product(self):
        """Matrix × vector gives per-row dot products (used in search)."""
        # 3 stored vectors, each 4-dimensional
        stored = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.7, 0.7, 0.0, 0.0],
        ], dtype=np.float32)

        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        scores = stored @ query

        # First vector is identical to query → score 1.0
        assert abs(scores[0] - 1.0) < 1e-6
        # Second vector is orthogonal → score 0.0
        assert abs(scores[1]) < 1e-6
        # Third vector is closer to query than to nothing → positive
        assert scores[2] > 0


class TestEmbedText:
    """Integration test — actually loads the model."""

    def test_embed_returns_array(self):
        """embed_text returns a numpy float32 array."""
        vec = embed_text("def login(user, password): pass")
        assert isinstance(vec, np.ndarray)
        assert vec.dtype == np.float32

    def test_embed_is_normalized(self):
        """The returned vector should have L2-norm ≈ 1 (normalized)."""
        vec = embed_text("def logout(): pass")
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-5

    def test_similar_queries_closer_than_different(self):
        """
        'user login' and 'authenticate user' should be more similar to each
        other than to 'sort a list of numbers'.
        """
        login1 = embed_text("user login function")
        login2 = embed_text("authenticate user credentials")
        unrelated = embed_text("sort a list of numbers in ascending order")

        sim_login = float(login1 @ login2)
        sim_unrelated = float(login1 @ unrelated)

        assert sim_login > sim_unrelated, (
            f"Expected login similarity ({sim_login:.3f}) > "
            f"unrelated similarity ({sim_unrelated:.3f})"
        )
