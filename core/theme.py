"""Thèmes de l'interface : sombre, clair et « soft » (tons doux, reposants).

Streamlit ne permet pas de changer son thème natif à chaud : on part du thème sombre déclaré dans
``.streamlit/config.toml`` et on redéfinit les couleurs par CSS (variables ``--od-*``) selon le choix.
"""
from __future__ import annotations

THEMES = ("dark", "light", "soft")
DEFAULT_THEME = "dark"

PALETTES: dict[str, dict[str, str]] = {
    "dark": {"scheme": "dark", "bg": "#070B1F", "surface": "#121842", "surface2": "#1A2150",
             "text": "#E8ECFF", "muted": "#9AA6D6", "border": "#2B3570", "accent": "#7C5CFF",
             "accent_text": "#FFFFFF", "badge_bg": "#1F2A5A", "badge_text": "#CFD6FF",
             "hero": "linear-gradient(120deg,#0b1030 0%,#2a1c6b 55%,#1b6fd1 100%)", "hero_text": "#FFFFFF"},
    "light": {"scheme": "light", "bg": "#FFFFFF", "surface": "#F3F5FB", "surface2": "#E8ECF7",
              "text": "#1B2140", "muted": "#5B6490", "border": "#D3D9EC", "accent": "#5B3FE0",
              "accent_text": "#FFFFFF", "badge_bg": "#E6E9FA", "badge_text": "#33408A",
              "hero": "linear-gradient(120deg,#5B3FE0 0%,#7C5CFF 50%,#3B8FEA 100%)", "hero_text": "#FFFFFF"},
    "soft": {"scheme": "light", "bg": "#F4EFE6", "surface": "#EAE3D6", "surface2": "#E0D8C8",
             "text": "#3A3631", "muted": "#7A7266", "border": "#D2C8B6", "accent": "#7A6BC4",
             "accent_text": "#FFFFFF", "badge_bg": "#E3DCEB", "badge_text": "#52457F",
             "hero": "linear-gradient(120deg,#9C8FD6 0%,#B7A8D9 50%,#D9B99B 100%)", "hero_text": "#2E2A3F"},
}

_CSS = """
<style>
:root{--od-bg:%(bg)s;--od-surface:%(surface)s;--od-surface2:%(surface2)s;--od-text:%(text)s;
 --od-muted:%(muted)s;--od-border:%(border)s;--od-accent:%(accent)s;color-scheme:%(scheme)s}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stBottom"],
[data-testid="stBottom"]>div,[data-testid="stHeader"]{background:var(--od-bg)!important;color:var(--od-text)!important}
[data-testid="stSidebar"],[data-testid="stSidebar"]>div{background:var(--od-surface)!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp span,
.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stMetricValue"],.stApp [data-testid="stMetricLabel"]{color:var(--od-text)}
.stApp [data-testid="stCaptionContainer"],.stApp small{color:var(--od-muted)!important}
.stApp hr{border-color:var(--od-border)!important}
/* champs de saisie */
.stApp input,.stApp textarea,.stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"]>div,[data-testid="stChatInput"],[data-testid="stChatInput"]>div{
 background:var(--od-surface)!important;color:var(--od-text)!important;border-color:var(--od-border)!important}
[data-baseweb="popover"] ul,[data-baseweb="popover"] li,[data-baseweb="menu"]{
 background:var(--od-surface)!important;color:var(--od-text)!important}
[data-testid="stFileUploaderDropzone"]{background:var(--od-surface)!important;border:1px dashed var(--od-border)!important}
[data-testid="stFileUploaderDropzone"] *{color:var(--od-text)!important}
/* conteneurs */
[data-testid="stExpander"] details{background:var(--od-surface)!important;border-color:var(--od-border)!important;border-radius:12px}
[data-testid="stChatMessage"]{background:var(--od-surface)!important;border-radius:14px;border:1px solid var(--od-border)}
.stApp pre,.stApp code,[data-testid="stJson"]{background:var(--od-surface2)!important;color:var(--od-text)!important}
/* boutons */
.stApp .stButton>button,.stApp .stDownloadButton>button{background:var(--od-surface2)!important;
 color:var(--od-text)!important;border:1px solid var(--od-border)!important;border-radius:10px}
.stApp .stButton>button:hover,.stApp .stDownloadButton>button:hover{border-color:var(--od-accent)!important;color:var(--od-accent)!important}
.stApp .stButton>button[kind="primary"],.stApp .stButton>button[data-testid="stBaseButton-primary"]{
 background:var(--od-accent)!important;color:%(accent_text)s!important;border-color:var(--od-accent)!important}
.stApp .stButton>button[kind="primary"] *,.stApp .stButton>button[data-testid="stBaseButton-primary"] *{color:%(accent_text)s!important}
/* onglets */
.stApp [data-baseweb="tab"]{color:var(--od-muted)!important}
.stApp [data-baseweb="tab"][aria-selected="true"]{color:var(--od-accent)!important}
.stApp [data-baseweb="tab-highlight"]{background:var(--od-accent)!important}
.stApp [data-baseweb="tab-border"]{background:var(--od-border)!important}
/* éléments maison */
.hero{padding:1.2rem 1.5rem;border-radius:18px;margin-bottom:1rem;background:%(hero)s}
.stApp .hero h1,.stApp .hero p{color:%(hero_text)s!important;margin:0}
.stApp .hero p{margin-top:.2rem;opacity:.9}
.badge{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.8rem;margin-right:.3rem;
 background:%(badge_bg)s;color:%(badge_text)s!important}
</style>
"""


def theme_css(name: str) -> str:
    """CSS complet du thème demandé (repli sur le thème par défaut si le nom est inconnu)."""
    return _CSS % PALETTES.get(name, PALETTES[DEFAULT_THEME])


def normalize_theme(name: object) -> str:
    return name if isinstance(name, str) and name in THEMES else DEFAULT_THEME
