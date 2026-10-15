"""Fixtures partagées : faux embedder déterministe et faux LLM (aucun réseau, aucun modèle)."""
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("OMNIDOC_DB", ":memory:")

import numpy as np  # noqa: E402

from core.retrieval import tokenize  # noqa: E402


class FakeEmbedder:
    """Sac de mots haché en 64 dimensions, normalisé : déterministe et sans modèle."""

    dim = 64

    def encode(self, texts, **_kwargs):
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for row, text in enumerate(texts):
            for tok in tokenize(text):
                out[row, int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


class FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeGroq:
    """Imite ``client.chat.completions.create`` ; renvoie les réponses scriptées dans l'ordre."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return type("R", (), {"choices": [FakeChoice(reply)]})()
