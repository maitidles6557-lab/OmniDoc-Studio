"""Configuration centrale : chemins, clés API, modèles et paramètres de recherche.

Les valeurs sont lues dans ``st.secrets`` (si Streamlit est disponible), puis dans les
variables d'environnement. Aucune clé n'est jamais écrite en dur.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

try:  # Streamlit est optionnel : le moteur reste utilisable en script / en test.
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = os.environ.get("OMNIDOC_DB") or str(BASE_DIR / "omnidoc.db")


def secret(name: str, default: Any = None) -> Any:
    """Lit une clé dans st.secrets, puis dans les variables d'environnement."""
    if st is not None:
        try:
            return st.secrets[name]
        except Exception:  # secrets.toml absent ou clé manquante
            pass
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    try:
        return int(secret(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(secret(name, default))
    except (TypeError, ValueError):
        return default


# Tesseract : variable d'environnement > PATH > chemin Windows par défaut.
TESSERACT_CMD = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# --- Modèles (configurables sans toucher au code) ---------------------------------
EMBED_MODEL = secret("EMBED_MODEL", "BAAI/bge-m3")
GROQ_MODEL = secret("GROQ_MODEL", "openai/gpt-oss-20b")
GEMINI_MODEL = secret("GEMINI_MODEL", "gemini-3.6-flash")

# --- Ingestion ---------------------------------------------------------------------
MAX_PDF_IMAGES = _int("MAX_PDF_IMAGES", 12)   # images intégrées légendées par PDF (coût API)
CHUNK_SIZE = _int("CHUNK_SIZE", 900)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)
OCR_TIMEOUT_S = _int("OCR_TIMEOUT_S", 120)

# --- Recherche ---------------------------------------------------------------------
MIN_DENSE_SCORE = _float("MIN_DENSE_SCORE", 0.25)  # seuil cosinus du dense (si absent de BM25)
RRF_K = _int("RRF_K", 60)

# --- Appels LLM --------------------------------------------------------------------
LLM_TIMEOUT_S = _float("LLM_TIMEOUT_S", 60.0)
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 3)

LOG_LEVEL = str(secret("LOG_LEVEL", "INFO")).upper()


def setup_logging(level: str | None = None) -> None:
    """Configure le logging une seule fois (idempotent, compatible avec les reruns Streamlit)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=getattr(logging, level or LOG_LEVEL, logging.INFO),
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
