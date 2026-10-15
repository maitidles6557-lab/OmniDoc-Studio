"""Extraction : texte PDF (avec OCR de secours) et images intégrées."""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile

import pymupdf
from PIL import Image

from .config import MAX_PDF_IMAGES, OCR_TIMEOUT_S, TESSERACT_CMD

log = logging.getLogger(__name__)
_warned_no_tesseract = False


class EncryptedPDFError(ValueError):
    """Le PDF est protégé par mot de passe."""


def ocr_image(image: Image.Image, lang: str = "fra+ara+eng") -> str:
    """OCR Tesseract ; renvoie '' si Tesseract est indisponible ou échoue."""
    global _warned_no_tesseract
    with tempfile.TemporaryDirectory() as tmp:
        src, out = os.path.join(tmp, "p.png"), os.path.join(tmp, "o")
        image.save(src, format="PNG")
        try:
            subprocess.run([TESSERACT_CMD, src, out, "-l", lang, "--psm", "6"],
                           check=True, capture_output=True, text=True, timeout=OCR_TIMEOUT_S)
            with open(out + ".txt", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            if not _warned_no_tesseract:
                log.warning("Tesseract introuvable (%s) : OCR désactivé.", TESSERACT_CMD)
                _warned_no_tesseract = True
        except subprocess.TimeoutExpired:
            log.warning("OCR : délai dépassé (%ss).", OCR_TIMEOUT_S)
        except subprocess.CalledProcessError as exc:
            log.warning("OCR : Tesseract a échoué : %s", (exc.stderr or "").strip()[:200])
    return ""


def extract_pages(pdf_bytes: bytes, min_chars: int = 100, dpi: int = 250) -> list[dict]:
    """Liste de {page, text, ocr}. Bascule en OCR si la page n'a pas de couche texte."""
    pages: list[dict] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.needs_pass:
            raise EncryptedPDFError("PDF protégé par mot de passe.")
        for i, page in enumerate(doc):
            text, used_ocr = page.get_text("text").strip(), False
            if len(text) < min_chars:
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                ocr_text = ocr_image(Image.open(io.BytesIO(pix.tobytes("png"))))
                if ocr_text:
                    text, used_ocr = ocr_text, True
            pages.append({"page": i + 1, "text": text, "ocr": used_ocr})
    return pages


def extract_embedded_images(pdf_bytes: bytes, max_images: int = MAX_PDF_IMAGES,
                            min_side: int = 150) -> list[dict]:
    """Images significatives du PDF (logos/pictos filtrés par taille), dédupliquées."""
    found: list[dict] = []
    seen: set[int] = set()
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.needs_pass:
            return found
        for i, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    pix = pymupdf.Pixmap(doc, xref)
                    if min(pix.width, pix.height) < min_side:
                        continue
                    if pix.n - pix.alpha >= 4:          # CMYK -> RGB
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    found.append({"page": i + 1, "bytes": pix.tobytes("png"), "mime": "image/png"})
                except Exception as exc:  # noqa: BLE001 - image corrompue / format exotique
                    log.debug("Image xref=%s ignorée : %s", xref, exc)
                    continue
                if len(found) >= max_images:
                    return found
    return found
