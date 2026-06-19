"""Embeddings for retrieval — semantic if a model is installed, lexical otherwise.

Resolution (best available, $0):
  1. model2vec  — static distilled embeddings, tiny + fast, NO torch (truly semantic)
  2. sentence-transformers — if already installed (semantic)
  3. pure-Python hashing embedder — char-trigram + token features, L2-normalized; needs
     NOTHING. Not transformer-semantic, but a real vector space that matches subwords/
     morphology, so it beats exact-token overlap and works everywhere.

The point: the RAG gets vector retrieval with zero install, and upgrades to true semantic
retrieval the moment model2vec is present — no code change.
"""
from __future__ import annotations

import hashlib
import math
import re

_DIM = 256
_BACKEND = None          # cached (name, encode_fn)


def _hash_vector(text: str, dim: int = _DIM) -> list[float]:
    """Dependency-free embedding: hashed tokens + char-trigrams (subword aware),
    signed-accumulated into `dim` buckets, then L2-normalized."""
    vec = [0.0] * dim
    toks = re.findall(r"[a-z0-9]+", text.lower())
    feats = list(toks)
    for t in toks:
        for i in range(len(t) - 2):
            feats.append(t[i:i + 3])              # char trigram -> subword similarity
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _resolve():
    """Pick the best available backend once, and cache it."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    try:
        from model2vec import StaticModel
        model = StaticModel.from_pretrained("minishlab/potion-base-8M")

        def enc(texts):
            import numpy as np
            v = model.encode(list(texts))
            v = np.asarray(v, dtype=float)
            n = np.linalg.norm(v, axis=1, keepdims=True)
            n[n == 0] = 1.0
            return (v / n).tolist()
        _BACKEND = ("model2vec", enc)
        return _BACKEND
    except Exception:
        pass
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")

        def enc(texts):
            return [list(map(float, row))
                    for row in model.encode(list(texts), normalize_embeddings=True)]
        _BACKEND = ("sentence-transformers", enc)
        return _BACKEND
    except Exception:
        pass
    _BACKEND = ("hashing", lambda texts: [_hash_vector(t) for t in texts])
    return _BACKEND


def backend_name() -> str:
    return _resolve()[0]


def embed(texts: list[str]) -> list[list[float]]:
    """Return one L2-normalized vector per input text (cosine == dot product)."""
    return _resolve()[1](list(texts))


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(n))     # inputs are L2-normalized
