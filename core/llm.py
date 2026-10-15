"""Couche LLM : Gemini (vision) + Groq (raisonnement, routage, vérification, commandes d'édition).

Les clients sont créés à la demande (une clé manquante ne bloque que la fonction concernée)
et peuvent être injectés pour les tests. Les appels réseau ont un timeout et des retries
avec backoff exponentiel sur les erreurs transitoires.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, TypeVar

from . import prompts
from .config import GEMINI_MODEL, GROQ_MODEL, LLM_MAX_RETRIES, LLM_TIMEOUT_S, secret
from .plan import sanitize_actions
from .prompts import LANG_NAMES  # noqa: F401  (ré-exporté : compatibilité)

log = logging.getLogger(__name__)
T = TypeVar("T")

VERDICTS = ("fidèle", "partiel", "non soutenu")
NA_VERDICT = {"score": None, "verdict": "n/a", "unsupported": ""}
TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_VERIFY_CHARS = 12_000
SUMMARY_CHARS = 9_000


class MissingAPIKeyError(RuntimeError):
    """Clé API absente (st.secrets ou variable d'environnement)."""


# ---------------------------------------------------------------- utilitaires purs
def extract_json(raw: str | None, expect: type | tuple = (dict, list)) -> Any:
    """Premier objet JSON du type attendu dans ``raw`` (tolère texte autour et blocs ```json)."""
    if not raw:
        return None
    raw = raw[:50_000]
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch in "{[":
            try:
                obj, _ = decoder.raw_decode(raw[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, expect):
                return obj
    return None


def normalize_verdict(out: Any) -> dict:
    """Force la sortie du juge dans {score:int|None, verdict:str, unsupported:str}."""
    if not isinstance(out, dict):
        return dict(NA_VERDICT)
    try:
        score: int | None = max(0, min(100, int(round(float(out.get("score"))))))
    except (TypeError, ValueError):
        score = None
    verdict = str(out.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        verdict = ("n/a" if score is None else
                   "fidèle" if score >= 80 else "partiel" if score >= 50 else "non soutenu")
    return {"score": score, "verdict": verdict, "unsupported": str(out.get("unsupported") or "")}


def sample_text(text: str, limit: int = SUMMARY_CHARS) -> str:
    """Réduit un long texte à ``limit`` caractères en gardant début, milieu et fin."""
    if len(text) <= limit:
        return text
    third = limit // 3
    mid = len(text) // 2
    return "\n[…]\n".join([text[:third], text[mid - third // 2: mid + third // 2], text[-third:]])


def is_transient(exc: Exception) -> bool:
    """Vrai pour les erreurs réseau / quota / serveur qui valent un nouvel essai."""
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(code, int):
        return code in TRANSIENT_CODES
    return isinstance(exc, (TimeoutError, ConnectionError))


def with_retries(fn: Callable[[], T], attempts: int = LLM_MAX_RETRIES,
                 base_delay: float = 1.0, what: str = "appel LLM") -> T:
    """Exécute ``fn`` avec backoff exponentiel sur erreurs transitoires uniquement."""
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-levée si non transitoire / dernier essai
            if attempt >= attempts or not is_transient(exc):
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning("%s : erreur transitoire (%s), nouvel essai dans %.1fs", what, exc, delay)
            time.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------- client
class LLM:
    """Façade Groq (texte) + Gemini (vision). Clients injectables pour les tests."""

    def __init__(self, groq_client: Any = None, gemini_client: Any = None,
                 groq_model: str | None = None, gemini_model: str | None = None) -> None:
        self._groq, self._gemini = groq_client, gemini_client
        self.groq_model = groq_model or GROQ_MODEL
        self.gemini_model = gemini_model or GEMINI_MODEL

    @property
    def groq(self) -> Any:
        if self._groq is None:
            key = secret("GROQ_API_KEY")
            if not key:
                raise MissingAPIKeyError("GROQ_API_KEY manquante (secrets.toml ou variable d'environnement).")
            from groq import Groq
            self._groq = Groq(api_key=key, timeout=LLM_TIMEOUT_S, max_retries=LLM_MAX_RETRIES)
        return self._groq

    @property
    def gemini(self) -> Any:
        if self._gemini is None:
            key = secret("GEMINI_API_KEY")
            if not key:
                raise MissingAPIKeyError("GEMINI_API_KEY manquante (secrets.toml ou variable d'environnement).")
            from google import genai
            self._gemini = genai.Client(api_key=key)
        return self._gemini

    # ---------- primitives ----------
    def chat(self, prompt: str, temperature: float = 0.2) -> str:
        """Complétion texte Groq (le client Groq gère timeout et retries HTTP)."""
        r = self.groq.chat.completions.create(
            model=self.groq_model, temperature=temperature,
            messages=[{"role": "user", "content": prompt}])
        return (r.choices[0].message.content or "").strip()

    def chat_json(self, prompt: str, expect: type | tuple = (dict, list)) -> Any:
        """Complétion à température 0 dont on extrait le premier JSON du type attendu (ou None)."""
        return extract_json(self.chat(prompt, temperature=0), expect)

    # ---------- vision ----------
    def describe_image(self, image_bytes: bytes, mime: str) -> str:
        """Légende « moteur de recherche » d'une image via Gemini Vision."""
        from google.genai import types

        def call() -> str:
            r = self.gemini.models.generate_content(
                model=self.gemini_model,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime),
                          prompts.DESCRIBE_IMAGE])
            return (r.text or "").strip()

        return with_retries(call, what="Gemini Vision")

    # ---------- routage ----------
    def route(self, question: str, has_text: bool, has_visual: bool) -> str:
        """Choisit l'espace de recherche : text | visual | both."""
        if has_text and not has_visual:
            return "text"
        if has_visual and not has_text:
            return "visual"
        try:
            out = self.chat_json(prompts.route_prompt(question), expect=dict)
            if out and out.get("route") in ("text", "visual", "both"):
                return out["route"]
        except Exception as exc:  # noqa: BLE001
            log.warning("Routage impossible, repli sur « both » : %s", exc)
        return "both"

    # ---------- génération ancrée ----------
    def answer(self, question: str, passages: list[dict], image_desc: str | None = None,
               lang: str = "fr") -> str:
        """Réponse ancrée dans les passages (et la description d'image éventuelle)."""
        ctx = "\n\n".join(
            f"[{p['kind'].upper()} | {p['source']} | p.{p['page']}]\n{p['text']}" for p in passages
        ) or "Aucun passage pertinent trouvé."
        return self.chat(prompts.answer_prompt(question, ctx, image_desc, lang))

    # ---------- auto-vérification (anti-hallucination) ----------
    def verify(self, question: str, answer: str, passages: list[dict],
               image_desc: str | None = None) -> dict:
        """Seconde passe LLM : la réponse est-elle soutenue par les sources ?"""
        parts = [p["text"] for p in passages]
        if image_desc:
            parts.append(f"[IMAGE UTILISATEUR]\n{image_desc}")
        ctx = "\n".join(parts)[:MAX_VERIFY_CHARS]
        try:
            out = self.chat_json(prompts.verify_prompt(question, answer, ctx), expect=dict)
        except Exception as exc:  # noqa: BLE001
            log.warning("Vérification de fidélité indisponible : %s", exc)
            return dict(NA_VERDICT)
        return normalize_verdict(out)

    def summarize(self, text: str, lang: str = "fr") -> str:
        return self.chat(prompts.summary_prompt(sample_text(text), lang))

    # ---------- éditeur PDF en langage naturel ----------
    def parse_edit(self, command: str, n_pages: int) -> list[dict]:
        """Commande libre -> liste d'actions JSON, nettoyée par ``plan.sanitize_actions``."""
        out = self.chat_json(prompts.edit_prompt(command, n_pages), expect=dict)
        actions, warnings = sanitize_actions((out or {}).get("actions", []))
        for w in warnings:
            log.info("parse_edit : %s", w)
        return actions
