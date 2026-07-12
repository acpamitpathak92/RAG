import numpy as np


def normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize rows of a 2D array (or a single 1D vector)."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        norm = np.linalg.norm(vectors)
        return vectors / norm if norm > 0 else vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms
