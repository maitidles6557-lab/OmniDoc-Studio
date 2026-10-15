"""Validation du plan d'édition PDF (liste d'actions JSON produite par le LLM ou l'utilisateur).

Module pur Python : il normalise les types et écarte tout ce qui n'est pas dans le schéma,
avant que ``editor.apply_actions`` ne touche au PDF. Les bornes de pages (dépendantes du
document courant) sont vérifiées à l'exécution.
"""
from __future__ import annotations

import re
from typing import Any

PAGE_OPS = {"delete_pages", "keep_pages"}
TERM_OPS = {"redact", "highlight"}
ALLOWED_OPS = PAGE_OPS | TERM_OPS | {"rotate", "reorder", "watermark", "redact_pii"}

MAX_WATERMARK_LEN = 40
MIN_TERM_LEN = 2          # évite de caviarder / surligner chaque « a » du document
MAX_RANGE = 10_000
_RANGE = re.compile(r"^\s*(\d+)\s*[-–:]\s*(\d+)\s*$")


def to_int_list(values: Any) -> list[int]:
    """Convertit ``[2, "3", "4-6", "x"]`` (ou un entier / une chaîne) en ``[2, 3, 4, 5, 6]``."""
    if values is None:
        return []
    if isinstance(values, (int, str)):
        values = [values]
    out: list[int] = []
    for v in values if isinstance(values, (list, tuple, set)) else []:
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out.append(v)
        elif isinstance(v, str):
            m = _RANGE.match(v)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                out.extend(range(min(a, b), min(max(a, b), min(a, b) + MAX_RANGE) + 1))
            elif v.strip().lstrip("-").isdigit():
                out.append(int(v))
    return out


def _terms(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    return [t for t in (str(v).strip() for v in values) if len(t) >= MIN_TERM_LEN]


def sanitize_actions(actions: Any) -> tuple[list[dict], list[str]]:
    """Retourne ``(actions_propres, avertissements)``."""
    warnings: list[str] = []
    clean: list[dict] = []
    if not isinstance(actions, list):
        return clean, ["⚠️ Plan invalide : une liste d'actions est attendue."]
    for raw in actions:
        if not isinstance(raw, dict):
            warnings.append(f"⚠️ Action ignorée (format invalide) : {raw!r}")
            continue
        op = raw.get("op")
        if op not in ALLOWED_OPS:
            warnings.append(f"⚠️ Action inconnue ignorée : {op}")
            continue
        if op in PAGE_OPS:
            clean.append({"op": op, "pages": to_int_list(raw.get("pages"))})
        elif op == "reorder":
            clean.append({"op": op, "order": to_int_list(raw.get("order"))})
        elif op == "rotate":
            try:
                angle = int(raw.get("angle", 90))
            except (TypeError, ValueError):
                warnings.append("⚠️ Rotation ignorée : angle invalide.")
                continue
            if angle % 90:
                warnings.append(f"⚠️ Rotation ignorée : {angle}° n'est pas un multiple de 90.")
                continue
            clean.append({"op": op, "pages": to_int_list(raw.get("pages")), "angle": angle % 360})
        elif op == "watermark":
            text = str(raw.get("text") or "CONFIDENTIEL").strip()[:MAX_WATERMARK_LEN]
            clean.append({"op": op, "text": text or "CONFIDENTIEL"})
        elif op in TERM_OPS:
            terms = _terms(raw.get("terms"))
            if not terms:
                warnings.append(f"⚠️ « {op} » ignoré : aucun terme valide "
                                f"(≥ {MIN_TERM_LEN} caractères).")
                continue
            clean.append({"op": op, "terms": terms})
        else:  # redact_pii
            clean.append({"op": op})
    return clean, warnings
