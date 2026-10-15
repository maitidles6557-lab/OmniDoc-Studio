"""Détection de données personnelles (regex). Module pur Python, sans dépendance."""
from __future__ import annotations

import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "iban": r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b",
    "téléphone": r"(?:\+|00)?\d{2,3}[ .-]?\(?\d\)?(?:[ .-]?\d{2}){4}",
    "CIN": r"\b[A-Z]{1,2}\d{5,6}\b",
}
_COMPILED = {kind: re.compile(pat) for kind, pat in PII_PATTERNS.items()}


def count_pii(text: str) -> dict[str, int]:
    """Nombre d'occurrences détectées dans ``text``, par type."""
    return {kind: sum(1 for _ in rx.finditer(text)) for kind, rx in _COMPILED.items()}


def unique_pii(text: str) -> set[str]:
    """Ensemble des chaînes sensibles distinctes trouvées dans ``text`` (tous types)."""
    return {m.group(0) for rx in _COMPILED.values() for m in rx.finditer(text)}
