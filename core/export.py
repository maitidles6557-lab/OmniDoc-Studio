"""Export de la conversation en texte brut (.txt), lisible dans n'importe quel éditeur."""
from __future__ import annotations

import re
from datetime import datetime

LABELS = {
    "fr": {"title": "Conversation OmniDoc Studio", "exported": "Exportée le", "user": "Vous",
           "assistant": "OmniDoc", "sources": "Sources", "fidelity": "Fidélité", "page": "p."},
    "en": {"title": "OmniDoc Studio conversation", "exported": "Exported on", "user": "You",
           "assistant": "OmniDoc", "sources": "Sources", "fidelity": "Faithfulness", "page": "p."},
    "ar": {"title": "محادثة OmniDoc Studio", "exported": "تاريخ التصدير", "user": "أنت",
           "assistant": "OmniDoc", "sources": "المصادر", "fidelity": "الموثوقية", "page": "ص."},
}


def strip_markdown(text: str) -> str:
    """Retire la syntaxe Markdown courante pour obtenir un texte brut propre."""
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)                  # clôtures de code
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)               # images
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)         # liens
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)           # titres
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text, flags=re.S)         # gras
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)  # italique
    text = re.sub(r"`([^`]+)`", r"\1", text)                            # code en ligne
    text = re.sub(r"^\s*[*+]\s+", "- ", text, flags=re.M)               # puces uniformes
    return text.strip()


def conversation_to_txt(messages: list[dict], lang: str = "fr", now: datetime | None = None) -> str:
    """Texte brut : un bloc par message, avec sources et score de fidélité de l'assistant."""
    lb = LABELS.get(lang, LABELS["fr"])
    now = now or datetime.now()
    bar = "=" * 60
    out = [lb["title"], f"{lb['exported']} {now:%Y-%m-%d %H:%M}", bar, ""]
    for m in messages:
        who = lb["user"] if m["role"] == "user" else lb["assistant"]
        out += [f"[{who}]", strip_markdown(m["content"])]
        meta = m.get("meta") or {}
        hits = meta.get("hits") or []
        if hits:
            refs = sorted({f"{h['source']} {lb['page']}{h['page']}" for h in hits})
            out.append(f"{lb['sources']} : " + " ; ".join(refs))
        if meta.get("verdict") and meta["verdict"] != "n/a":
            out.append(f"{lb['fidelity']} : {meta['verdict']} {meta.get('score') or ''}".rstrip())
        out += ["", "-" * 60, ""]
    return "\n".join(out)


def export_filename(now: datetime | None = None) -> str:
    return f"conversation_{(now or datetime.now()):%Y%m%d_%H%M}.txt"
