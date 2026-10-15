"""Orchestration indépendante de l'interface : question -> route -> recherche -> réponse -> vérification,
et légendage (avec cache) des images. Testable sans Streamlit."""
from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from . import db

log = logging.getLogger(__name__)
QUERY_IMAGE_CHARS = 600   # part de la légende de l'image active ajoutée à la requête


@dataclass
class Answer:
    text: str
    route: str
    hits: list[dict] = field(default_factory=list)
    verification: dict = field(default_factory=dict)


def ask(question: str, rag: Any, llm: Any, *, image_desc: str | None = None, lang: str = "fr",
        k: int = 4, verify: bool = True) -> Answer:
    """Pipeline de réponse : routage, recherche hybride, génération ancrée, fidélité."""
    t_n, v_n = rag.sizes if rag else (0, 0)
    route = llm.route(question, t_n > 0, v_n > 0) if rag else "none"
    query = question + (f"\n{image_desc[:QUERY_IMAGE_CHARS]}" if image_desc else "")
    hits = rag.search(query, route, k) if rag else []
    text = llm.answer(question, hits, image_desc, lang)
    ver = llm.verify(question, text, hits, image_desc) if (verify and (hits or image_desc)) else {}
    return Answer(text=text, route=route, hits=hits, verification=ver)


def make_thumb(img_bytes: bytes, side: int = 420) -> bytes:
    """Miniature JPEG pour l'affichage des citations visuelles."""
    from PIL import Image
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def describe_cached(llm: Any, data: bytes, mime: str) -> str:
    """Légende Gemini d'une image, mémorisée par empreinte SHA-256 (+ modèle) dans SQLite."""
    key = f"{getattr(llm, 'gemini_model', '')}:{hashlib.sha256(data).hexdigest()}"
    try:
        cached = db.get_caption(key)
        if cached:
            return cached
    except Exception as exc:  # noqa: BLE001 - le cache ne doit jamais bloquer l'ingestion
        log.warning("Cache de légendes indisponible : %s", exc)
    text = llm.describe_image(data, mime)
    try:
        db.set_caption(key, text)
    except Exception as exc:  # noqa: BLE001
        log.warning("Écriture du cache de légendes impossible : %s", exc)
    return text


def caption_pdf_images(llm: Any, name: str, pdf_bytes: bytes,
                       on_error: Callable[[int, Exception], None] | None = None) -> list[dict]:
    """Chunks « visual » : une légende par image significative intégrée au PDF."""
    from .extract import extract_embedded_images   # import local : PyMuPDF n'est requis qu'ici

    chunks: list[dict] = []
    for n, im in enumerate(extract_embedded_images(pdf_bytes), 1):
        try:
            desc = describe_cached(llm, im["bytes"], im["mime"])
        except Exception as exc:  # noqa: BLE001 - une image en échec n'arrête pas l'ingestion
            log.warning("Image p.%s de %s ignorée : %s", im["page"], name, exc)
            if on_error:
                on_error(im["page"], exc)
            continue
        chunks.append({"kind": "visual", "source": name, "page": im["page"], "chunk": n,
                       "text": desc, "thumb": make_thumb(im["bytes"])})
    return chunks
