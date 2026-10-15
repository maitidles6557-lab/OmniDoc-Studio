"""MultiRAG : index hybride (dense + BM25 lexical) fusionné par RRF,
avec deux espaces d'index : TEXTE (PDF) et VISUEL (légendes d'images).

Le dense utilise FAISS s'il est installé, sinon un produit scalaire NumPy exact
(mêmes résultats, utile pour les tests et les petites collections).
"""
from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from .config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_DENSE_SCORE, RRF_K

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"\w+", re.UNICODE)


# ---------------------------------------------------------------- texte
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    """Minuscules + suppression des accents/diacritiques (« éléctricité » ~ « electricite »)."""
    folded = unicodedata.normalize("NFKD", text.lower())
    return _TOKEN.findall("".join(c for c in folded if not unicodedata.combining(c)))


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Découpe en chunks de ``size`` caractères avec recouvrement, coupés sur un espace."""
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return parts


def build_text_chunks(pages_by_doc: dict[str, list[dict]]) -> list[dict]:
    """pages_by_doc: {nom_fichier: [{page, text}, ...]} -> liste de chunks avec métadonnées."""
    chunks: list[dict] = []
    for name, pages in pages_by_doc.items():
        for p in pages:
            for n, piece in enumerate(split_text(clean_text(p["text"])), start=1):
                chunks.append({"kind": "text", "source": name, "page": p["page"],
                               "chunk": n, "text": piece})
    return chunks


# ---------------------------------------------------------------- lexical
class BM25:
    """BM25 Okapi minimal avec index inversé (seuls les documents contenant un terme sont parcourus)."""

    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.lengths = np.zeros(self.n, dtype="float32")
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, doc in enumerate(docs):
            tf = Counter(tokenize(doc))
            self.lengths[i] = sum(tf.values())
            for term, freq in tf.items():
                self.postings[term].append((i, freq))
        self.avg = float(self.lengths.mean()) if self.n else 0.0
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
                    for t, p in self.postings.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype="float32")
        for term in tokenize(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, f in self.postings[term]:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avg or 1))
                out[i] += idf * f * (self.k1 + 1) / (f + norm)
        return out


def rrf(rankings: list[list[int]], k: int = RRF_K) -> Counter:
    """Reciprocal Rank Fusion : combine plusieurs classements d'indices."""
    fused: Counter = Counter()
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            fused[idx] += 1.0 / (k + rank + 1)
    return fused


# ---------------------------------------------------------------- dense
class _NumpyFlatIP:
    """Équivalent exact de ``faiss.IndexFlatIP`` (produit scalaire) en NumPy."""

    def __init__(self, dim: int) -> None:
        self.vecs = np.zeros((0, dim), dtype="float32")

    def add(self, vecs: np.ndarray) -> None:
        self.vecs = np.vstack([self.vecs, vecs])

    def search(self, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        sims = q @ self.vecs.T
        idx = np.argsort(-sims, axis=1)[:, :min(k, sims.shape[1])]
        return np.take_along_axis(sims, idx, axis=1), idx


def _flat_ip(dim: int) -> Any:
    try:
        import faiss
        return faiss.IndexFlatIP(dim)
    except ImportError:
        log.info("faiss indisponible : repli sur le produit scalaire NumPy.")
        return _NumpyFlatIP(dim)


class HybridIndex:
    """Dense (embeddings normalisés) + BM25, fusionnés par RRF."""

    def __init__(self, chunks: list[dict], embedder: Any, min_dense: float = MIN_DENSE_SCORE) -> None:
        self.chunks, self.embedder, self.min_dense = chunks, embedder, min_dense
        self.dense = None
        if chunks:
            vecs = np.asarray(embedder.encode(
                [c["text"] for c in chunks], convert_to_numpy=True, normalize_embeddings=True,
                show_progress_bar=False, batch_size=32), dtype="float32")
            self.dense = _flat_ip(vecs.shape[1])
            self.dense.add(vecs)
        self.bm25 = BM25([c["text"] for c in chunks])

    def search(self, query: str, k: int = 4, min_dense: float | None = None) -> list[dict]:
        n = len(self.chunks)
        if n == 0 or self.dense is None:
            return []
        threshold = self.min_dense if min_dense is None else min_dense
        q = np.asarray(self.embedder.encode([query], convert_to_numpy=True,
                                            normalize_embeddings=True), dtype="float32")
        sims, ids = self.dense.search(q, min(n, k * 4))
        dense_rank = [int(i) for i in ids[0] if i != -1]
        dense_score = {int(i): float(s) for s, i in zip(sims[0], ids[0]) if i != -1}
        lex = self.bm25.scores(query)
        lex_rank = [int(i) for i in np.argsort(-lex)[: k * 4] if lex[i] > 0]
        fused = rrf([dense_rank, lex_rank])
        out: list[dict] = []
        for idx, score in fused.most_common(k * 2):
            if dense_score.get(idx, 0.0) < threshold and idx not in lex_rank[:k]:
                continue
            out.append(dict(self.chunks[idx], rrf=round(score, 4),
                            dense=round(dense_score.get(idx, 0.0), 3)))
            if len(out) == k:
                break
        return out


class MultiRAG:
    """Deux index (texte + visuel) interrogés selon la route choisie."""

    def __init__(self, embedder: Any) -> None:
        self.embedder = embedder
        self.text: HybridIndex | None = None
        self.visual: HybridIndex | None = None

    def set_text(self, chunks: list[dict]) -> None:
        self.text = HybridIndex(chunks, self.embedder) if chunks else None

    def set_visual(self, chunks: list[dict]) -> None:
        self.visual = HybridIndex(chunks, self.embedder) if chunks else None

    @property
    def sizes(self) -> tuple[int, int]:
        return (len(self.text.chunks) if self.text else 0,
                len(self.visual.chunks) if self.visual else 0)

    def search(self, query: str, route: str = "both", k: int = 4) -> list[dict]:
        hits: list[dict] = []
        if route in ("text", "both") and self.text:
            hits += self.text.search(query, k)
        if route in ("visual", "both") and self.visual:
            hits += self.visual.search(query, max(2, k // 2))
        return sorted(hits, key=lambda h: -h["rrf"])
