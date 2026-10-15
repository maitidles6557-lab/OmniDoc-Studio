"""Éditeur PDF : opérations déterministes validées + rendu des citations surlignées."""
from __future__ import annotations

import logging

import pymupdf

from .pii import PII_PATTERNS, count_pii, unique_pii  # noqa: F401  (PII_PATTERNS ré-exporté)
from .plan import sanitize_actions

log = logging.getLogger(__name__)


def page_count(pdf_bytes: bytes) -> int:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as d:
        return len(d)


def _valid(pages, n: int) -> list[int]:
    """Pages uniques et triées, bornées à [1, n]."""
    return sorted({int(p) for p in (pages or []) if 1 <= int(p) <= n})


def scan_pii(pdf_bytes: bytes) -> dict[str, int]:
    """Compte les données personnelles détectées, par type."""
    totals: dict[str, int] = {}
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            for kind, c in count_pii(page.get_text("text")).items():
                totals[kind] = totals.get(kind, 0) + c
    return totals


def _redact(page, terms) -> int:
    n = 0
    for t in terms:
        for rect in page.search_for(t):
            page.add_redact_annot(rect, fill=(0, 0, 0))
            n += 1
    if n:
        page.apply_redactions()   # suppression réelle du texte sous-jacent
    return n


def apply_actions(pdf_bytes: bytes, actions: list[dict]) -> tuple[bytes, list[str]]:
    """Applique une liste d'actions (validée par ``plan.sanitize_actions``).

    Retourne ``(nouveau_pdf, journal)``.
    """
    actions, log_lines = sanitize_actions(actions)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for a in actions:
            op, n = a["op"], len(doc)
            if op == "delete_pages":
                pages = _valid(a.get("pages"), n)
                if len(pages) >= n:
                    log_lines.append("⚠️ Suppression ignorée : elle viderait le document.")
                    continue
                if pages:
                    doc.delete_pages([p - 1 for p in pages])
                    log_lines.append(f"🗑️ Pages supprimées : {pages}")
            elif op == "keep_pages":
                pages = _valid(a.get("pages"), n)
                if pages:
                    doc.select([p - 1 for p in pages])
                    log_lines.append(f"✂️ Pages conservées : {pages}")
            elif op == "reorder":
                order = [int(p) for p in a.get("order", []) if 1 <= int(p) <= n]
                if order and sorted(order) == list(range(1, n + 1)):
                    doc.select([p - 1 for p in order])
                    log_lines.append(f"🔀 Nouvel ordre : {order}")
                else:
                    log_lines.append("⚠️ Réordonnancement ignoré (ordre incomplet).")
            elif op == "rotate":
                angle = a["angle"]
                for p in _valid(a.get("pages") or range(1, n + 1), n):
                    pg = doc[p - 1]
                    pg.set_rotation((pg.rotation + angle) % 360)
                log_lines.append(f"🔄 Rotation de {angle}°")
            elif op == "watermark":
                text = a["text"]
                for pg in doc:
                    c = pymupdf.Point(pg.rect.width * 0.2, pg.rect.height * 0.6)
                    pg.insert_text(c, text, fontsize=56, color=(0.6, 0.6, 0.6),
                                   fill_opacity=0.3, morph=(c, pymupdf.Matrix(-35)))
                log_lines.append(f"💧 Filigrane « {text} »")
            elif op == "redact":
                total = sum(_redact(pg, a["terms"]) for pg in doc)
                log_lines.append(f"⬛ {total} occurrence(s) caviardée(s) : {a['terms']}")
            elif op == "redact_pii":
                total = 0
                for pg in doc:
                    total += _redact(pg, sorted(unique_pii(pg.get_text("text"))))
                log_lines.append(f"🛡️ {total} donnée(s) personnelle(s) caviardée(s)")
            elif op == "highlight":
                total = 0
                for pg in doc:
                    for t in a["terms"]:
                        for rect in pg.search_for(t):
                            pg.add_highlight_annot(rect)
                            total += 1
                log_lines.append(f"🖍️ {total} surlignage(s)")
        return doc.tobytes(garbage=3, deflate=True), log_lines
    finally:
        doc.close()


def merge_pdfs(pdf_list: list[bytes]) -> bytes:
    out = pymupdf.open()
    try:
        for b in pdf_list:
            with pymupdf.open(stream=b, filetype="pdf") as d:
                out.insert_pdf(d)
        return out.tobytes(garbage=3, deflate=True)
    finally:
        out.close()


def _fragments(text: str, size: int = 6) -> list[str]:
    """Fragments courts d'un passage, plus robustes pour search_for."""
    words = text.split()
    if len(words) <= size:
        return [text]
    mids = len(words) // 2
    return [" ".join(words[:size]), " ".join(words[mids:mids + size]), " ".join(words[-size:])]


def render_page(pdf_bytes: bytes, page_no: int, passages=(), dpi: int = 110) -> bytes:
    """Rend une page en PNG en surlignant les passages cités."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[max(1, min(page_no, len(doc))) - 1]
        for p in passages:
            for frag in _fragments(p):
                for rect in page.search_for(frag):
                    page.add_highlight_annot(rect)
        return page.get_pixmap(dpi=dpi, alpha=False).tobytes("png")
