"""Génère les 3 workflows (PNG 1080x1620, lisibles sur mobile) depuis des pages HTML.

    python tools/render_workflows.py          # écrit docs/workflows/*.png (+ sources HTML dans docs/workflows/src)
Nécessite Playwright + Chromium (pip install playwright && playwright install chromium).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "workflows"
W, H, SCALE = 1080, 1620, 2   # 2:3 — les schémas détaillés demandent plus que 4:5

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1620px}
body{font-family:'Inter','Segoe UI',Arial,sans-serif;color:#F3F5FF;overflow:hidden;
 background:radial-gradient(900px 500px at 85% -5%,#2b1f78 0%,transparent 60%),
 radial-gradient(800px 500px at -5% 105%,#0f4a8a 0%,transparent 60%),#090D26}
.page{padding:40px 48px 30px;height:1620px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;justify-content:space-between}
.pill{font-weight:700;font-size:22px;letter-spacing:.08em;padding:8px 18px;border-radius:999px;
 background:linear-gradient(90deg,#7C5CFF,#3CC8F0);color:#fff}
.brand{font-size:24px;font-weight:600;color:#B8C2F0}
h1{font-size:54px;line-height:1.05;margin:12px 0 4px;font-weight:800;letter-spacing:-.02em}
.sub{font-size:25px;color:#B8C2F0;margin-bottom:12px;line-height:1.3}
.flow{flex:1;display:flex;flex-direction:column;justify-content:space-between;min-height:0}
.card{background:#141A45;border:2px solid #2B3570;border-radius:22px;padding:12px 22px 13px;position:relative}
.card.v{border-color:#7C5CFF}.card.c{border-color:#3CC8F0}.card.p{border-color:#FF6FB5}
.card.g{border-color:#43D9A3}.card.a{border-color:#FFC857}
.row{display:flex;gap:16px}.row>*{flex:1;min-width:0}
.hd{display:flex;align-items:center;gap:14px;margin-bottom:3px}
.num{flex:none;width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-weight:800;font-size:24px;color:#090D26;background:#7C5CFF}
.v .num{background:#9C84FF}.c .num{background:#3CC8F0}.p .num{background:#FF6FB5}
.g .num{background:#43D9A3}.a .num{background:#FFC857}
.t{font-size:30px;font-weight:800;line-height:1.1}
.d{font-size:24px;line-height:1.3;color:#D6DCFF}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.chip{font-size:21px;font-weight:600;padding:4px 14px;border-radius:999px;background:#0D1235;
 border:1.5px solid #3A4590;color:#E6EAFF;white-space:nowrap}
.chip.v{border-color:#9C84FF;color:#CFC3FF}.chip.c{border-color:#3CC8F0;color:#A8E7FA}
.chip.p{border-color:#FF6FB5;color:#FFC0DE}.chip.g{border-color:#43D9A3;color:#A6F0D2}
.chip.a{border-color:#FFC857;color:#FFE3A3}
.arrow{height:22px;display:flex;align-items:center;justify-content:center;color:#7C8CE8;font-size:24px;line-height:1}
.arrow{position:relative}.arrow small{position:absolute;left:calc(50% + 28px);font-size:20px;color:#9AA6D6;font-weight:600}
.mini{border:2px dashed #3CC8F0;border-radius:24px;padding:14px 18px 16px;background:rgba(60,200,240,.06)}
.mini .cap{font-size:23px;font-weight:700;color:#7DDCF7;margin-bottom:10px;letter-spacing:.02em}
.lane{display:flex;flex-direction:column;align-items:center;gap:0}
.box{width:100%;text-align:center;border-radius:16px;padding:10px 10px;font-size:23px;font-weight:700;line-height:1.2;
 background:#0D1235;border:2px solid #3A4590}
.box small{display:block;font-size:19px;font-weight:500;color:#B8C2F0;margin-top:2px}
.box.v{border-color:#9C84FF}.box.c{border-color:#3CC8F0}.box.p{border-color:#FF6FB5}.box.g{border-color:#43D9A3}.box.a{border-color:#FFC857}
.lane .arrow{height:20px;font-size:20px}
.merge{margin-top:8px;text-align:center;font-size:23px;font-weight:700;padding:9px;border-radius:14px;
 background:linear-gradient(90deg,rgba(124,92,255,.35),rgba(60,200,240,.35));border:2px solid #7C8CE8}
.note{border-radius:22px;padding:16px 22px;background:linear-gradient(100deg,rgba(255,111,181,.18),rgba(124,92,255,.22));
 border:2px solid #FF6FB5;font-size:25px;line-height:1.3;color:#FFE3F1}
.note b{color:#fff}
.foot{margin-top:12px;display:flex;justify-content:space-between;font-size:21px;color:#8F9BD0}
.sec{font-size:21px;font-weight:800;letter-spacing:.12em;color:#8F9BD0;margin:0 0 8px 4px}
"""


def page(tag: str, title: str, sub: str, body: str, foot: str = "OmniDoc Studio") -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="page"><div class="top"><span class="pill">{tag}</span><span class="brand">OmniDoc Studio</span></div>
<h1>{title}</h1><div class="sub">{sub}</div><div class="flow">{body}</div>
<div class="foot"><span>{foot}</span><span>#RAG #MultiRAG #GenAI #Python</span></div></div></body></html>"""


def chips(items: list[tuple[str, str]]) -> str:
    return '<div class="chips">' + "".join(f'<span class="chip {c}">{t}</span>' for t, c in items) + "</div>"


def step(n: str, title: str, desc: str, ch: list[tuple[str, str]], color: str = "v") -> str:
    return (f'<div class="card {color}"><div class="hd"><span class="num">{n}</span><span class="t">{title}</span></div>'
            f'<div class="d">{desc}</div>{chips(ch)}</div>')


def arrow(label: str = "") -> str:
    return f'<div class="arrow">▼{f"<small>{label}</small>" if label else ""}</div>'


# --------------------------------------------------------------------------- 1 · RAG
def wf_rag() -> str:
    lanes = ""
    for src, tech, sub, c in [("PDF texte", "PyMuPDF", "extraction du texte", "v"),
                              ("PDF scanné", "Tesseract OCR", "fra · ara · eng", "a"),
                              ("Images", "Gemini Vision", "légende + texte lu", "p")]:
        lanes += (f'<div class="lane"><div class="box {c}">{src}</div><div class="arrow">▼</div>'
                  f'<div class="box {c}">{tech}<small>{sub}</small></div></div>')
    mini = (f'<div class="mini"><div class="cap">MINI-WORKFLOW · IMPORT DES RESSOURCES</div>'
            f'<div class="row">{lanes}</div>'
            f'<div class="merge">Texte propre + métadonnées (fichier · page)</div></div>')
    body = (mini + arrow() +
            step("1", "Chunking", "Le texte est découpé en blocs de 900 caractères, avec 150 de recouvrement.",
                 [("Python", "v"), ("coupe sur espace", ""), ("fichier · page · n°", "")], "v") + arrow() +
            '<div class="row">' +
            step("2", "Embedding", "Chaque chunk devient un vecteur de sens, rangé dans un index.",
                 [("BGE-M3", "c"), ("Sentence-Transformers", "c"), ("FAISS", "c")], "c") +
            step("2b", "Index lexical", "Mots-clés exacts, insensible aux accents.",
                 [("BM25 Okapi", "g"), ("index inversé", "g")], "g") + '</div>' + arrow() +
            step("3", "Recherche hybride", "Dense + BM25 fusionnés, puis filtrés par seuil de pertinence.",
                 [("RRF (k=60)", "a"), ("top-k", "a"), ("seuil cosinus", "a")], "a") + arrow() +
            step("4", "Génération", "Réponse ancrée dans les passages, avec citations [fichier, p.X].",
                 [("Groq", "p"), ("gpt-oss-20b", "p"), ("anti-injection", "p")], "p") + arrow() +
            step("5", "Vérification", "2ᵉ passe LLM : score de fidélité 0-100. Sources surlignées sur la page.",
                 [("LLM juge", "v"), ("PyMuPDF", "v")], "v") + '<div style="height:10px"></div>' +
            '<div class="note"><b>Attention : ce n\'est pas « un seul RAG ».</b> OmniDoc est un <b>MultiRAG</b> : '
            'deux index (TEXTE + VISUEL) sont interrogés via un routeur texte / visuel / mixte, puis fusionnés.</div>')
    return page("WORKFLOW 1/3", "Le pipeline RAG", "De vos fichiers à une réponse citée et vérifiée", body)


# --------------------------------------------------------------------------- 2 · image
def wf_image() -> str:
    body = (
        step("1", "Import de l'image", "Une image téléversée (PNG, JPG, WebP) ou extraite d'un PDF "
             "(≥ 150 px, 12 max, sans doublon).", [("Streamlit", "c"), ("PyMuPDF", "c"), ("Pillow", "c")], "c") + arrow() +
        '<div class="card a"><div class="hd"><span class="num">2</span><span class="t">Empreinte + cache</span></div>'
        '<div class="d">SHA-256 de l\'image, cherché dans SQLite avant tout appel API.</div>'
        '<div class="row" style="margin-top:10px"><div class="box g">Déjà vue<small>légende instantanée, 0 appel</small></div>'
        '<div class="box p">Nouvelle image<small>on appelle le modèle de vision</small></div></div>'
        + chips([("SHA-256", "a"), ("SQLite", "a")]) + '</div>' + arrow("nouvelle image") +
        step("3", "Compréhension visuelle", "Le modèle décrit : type d'image, éléments, TOUT le texte visible, chiffres clés. "
             "Rien d'inventé.", [("Gemini Vision", "p"), ("gemini-3.6-flash", "p"), ("retries", "p")], "p") + arrow("légende mise en cache") +
        '<div class="row">' +
        step("4a", "Image active", "Sa légende enrichit la question : recherche croisée image → PDF.",
             [("BGE-M3", "c"), ("BM25 + RRF", "c")], "c") +
        step("4b", "Index visuel", "Option : l'image devient cherchable (légende + miniature).",
             [("FAISS", "g"), ("miniature 420 px", "g")], "g") + '</div>' + arrow() +
        step("5", "Routeur", "Un LLM choisit où chercher : texte, visuel ou les deux.",
             [("Groq", "v"), ("JSON {route}", "v")], "v") + arrow() +
        step("6", "Analyse par le LLM", "Réponse basée sur l'image ET les passages, en distinguant TEXTE / IMAGE.",
             [("Groq", "p"), ("gpt-oss-20b", "p"), ("citations", "p")], "p") + arrow() +
        step("7", "Vérification", "Score de fidélité (l'image compte comme preuve) + miniatures citées.",
             [("LLM juge", "a"), ("Pillow", "a")], "a"))
    return page("WORKFLOW 2/3", "Traitement d'image + LLM", "Comment une image devient une réponse fiable", body)


# --------------------------------------------------------------------------- 3 · projet
def wf_project() -> str:
    def mini(title, sub, c):
        return f'<div class="box {c}">{title}<small>{sub}</small></div>'

    inputs = ('<div class="row">' + mini("PDF", "texte ou scan", "v") + mini("Images", "PNG · JPG · WebP", "p")
              + mini("Question / commande", "en langage naturel", "c") + '</div>')
    ui = ('<div class="card c"><div class="hd"><span class="t">Interface Streamlit</span></div>'
          + chips([("Comptes PBKDF2", "c"), ("3 thèmes", "c"), ("FR · EN · AR", "c"), ("Nouvelle conversation", "c")]) + '</div>')
    ingest = ('<div class="row">' +
              step("1", "Ingestion", "Texte, OCR, légendes d'images.",
                   [("PyMuPDF", "v"), ("Tesseract", "v"), ("Gemini Vision", "v")], "v") +
              step("2", "MultiRAG", "Chunking, embeddings, deux index.",
                   [("BGE-M3", "c"), ("FAISS", "c"), ("BM25", "c")], "c") + '</div>')
    left = ('<div class="card p"><div class="hd"><span class="num">3</span><span class="t">Répondre</span></div>'
            '<div class="d">Routeur → recherche hybride RRF → réponse citée → vérification.</div>'
            + chips([("Groq", "p"), ("RRF", "p"), ("fidélité", "p")]) + '</div>')
    right = ('<div class="card a"><div class="hd"><span class="num">4</span><span class="t">Éditer</span></div>'
             '<div class="d">Commande → plan JSON validé et modifiable → PyMuPDF.</div>'
             + chips([("Groq", "a"), ("plan JSON", "a"), ("PyMuPDF", "a")]) + '</div>')
    lanes = f'<div class="row">{left}{right}</div>'
    outs = ('<div class="row">' + mini("Réponse citée", "pages surlignées + score", "v")
            + mini("PDF modifié", "caviardage · filigrane · fusion", "a")
            + mini("Export .txt", "conversation + sources", "g") + '</div>')
    db = ('<div class="card g"><div class="hd"><span class="t">SQLite</span></div>'
          '<div class="d">Comptes · historique des conversations · cache des légendes d\'images.</div></div>')
    body = (inputs + arrow() + ui + arrow() + ingest + arrow("2 index : TEXTE + VISUEL") + lanes + arrow()
            + outs + '<div style="height:10px"></div>' + db)
    return page("WORKFLOW 3/3", "Le projet en un coup d'œil", "OmniDoc Studio, de bout en bout : MultiRAG + éditeur PDF + vision", body)


def render() -> list[Path]:
    from playwright.sync_api import sync_playwright

    src = OUT / "src"
    src.mkdir(parents=True, exist_ok=True)
    jobs = {"01_rag_workflow": wf_rag(), "02_image_llm_workflow": wf_image(), "03_project_workflow": wf_project()}
    written: list[Path] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        for name, html in jobs.items():
            (src / f"{name}.html").write_text(html, encoding="utf-8")
            pg.set_content(html)
            pg.wait_for_timeout(200)
            overflow = pg.evaluate("document.querySelector('.flow').scrollHeight - document.querySelector('.flow').clientHeight")
            if overflow > 0:
                print(f"ATTENTION {name}: contenu trop haut de {overflow}px", file=sys.stderr)
            target = OUT / f"{name}.png"
            pg.screenshot(path=str(target))
            written.append(target)
        browser.close()
    return written


if __name__ == "__main__":
    for p in render():
        print(p.relative_to(ROOT))
