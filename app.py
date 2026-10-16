"""OmniDoc Studio - MultiRAG + éditeur PDF intelligent + analyse d'images (Streamlit)."""
import json
import logging

import streamlit as st
from PIL import Image

from core import db
from core.config import ASSETS_DIR, EMBED_MODEL, setup_logging
from core.editor import apply_actions, merge_pdfs, page_count, render_page, scan_pii
from core.export import conversation_to_txt, export_filename
from core.extract import extract_pages
from core.i18n import T
from core.pipeline import ask, caption_pdf_images, describe_cached, make_thumb
from core.retrieval import MultiRAG, build_text_chunks
from core.theme import THEMES, normalize_theme, theme_css

setup_logging()
log = logging.getLogger("omnidoc.app")

LOGO = ASSETS_DIR / "logo.png"
AVATAR = ASSETS_DIR / "avatar.png"
BOT_AVATAR = str(AVATAR) if AVATAR.exists() else ":material/auto_awesome:"
USER_AVATAR = ":material/person:"
st.set_page_config(page_title="OmniDoc Studio", layout="wide",
                   page_icon=Image.open(LOGO) if LOGO.exists() else "📄")

# ------------------------------------------------------------------ état
DEFAULTS = {"lang": "fr", "user_id": None, "username": None, "conv_id": None,
            "messages": [], "docs": {}, "pages": {}, "rag": None, "image_descs": {},
            "image_bytes": {}, "edited": {}, "plan": None}
PREFS = ("lang", "theme")   # préférences d'interface : conservées à la déconnexion
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("theme", normalize_theme(st.query_params.get("theme")))
db.init_db()


def tr(key):
    return T[st.session_state.lang][key]


@st.cache_resource(show_spinner="Chargement du modèle d'embeddings…")
def get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


@st.cache_resource
def get_llm():
    from core.llm import LLM
    return LLM()


@st.cache_data(show_spinner=False, max_entries=64)
def cached_page(pdf_bytes: bytes, page_no: int, passages: tuple = ()) -> bytes:
    """Rendu de page mis en cache : évite de re-rendre toutes les citations à chaque rerun Streamlit."""
    return render_page(pdf_bytes, page_no, list(passages))


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO))
    st.selectbox(f":material/translate: {tr('lang')}", ["fr", "en", "ar"], key="lang",
                 format_func=lambda c: {"fr": "Français", "en": "English", "ar": "العربية"}[c])
    st.radio(f":material/palette: {tr('theme')}", list(THEMES), key="theme", horizontal=True,
             format_func=lambda t: tr(f"t_{t}"))
    st.query_params["theme"] = st.session_state.theme

    # Nouvelle conversation : disponible pour tous (invités compris), sources et index conservés.
    if st.button(tr("new"), icon=":material/add_comment:", type="primary", use_container_width=True,
                 help=tr("new_hint")):
        st.session_state.update(conv_id=None, messages=[], plan=None)
        st.toast(tr("new_done"), icon=":material/check_circle:")
        st.rerun()

    if st.session_state.user_id is None:
        mode = st.radio("", [tr("login"), tr("register"), tr("guest")], label_visibility="collapsed")
        if mode != tr("guest"):
            with st.form("auth"):
                u = st.text_input(tr("user"))
                p = st.text_input(tr("pwd"), type="password")
                if st.form_submit_button(mode):
                    if len(u.strip()) < 3 or len(p) < 8:
                        st.error("≥ 3 caractères (nom) · ≥ 8 caractères (mot de passe)")
                    elif mode == tr("register"):
                        uid = db.create_user(u.strip(), p)
                        if uid:
                            st.session_state.update(user_id=uid, username=u.strip())
                            st.rerun()
                        else:
                            st.error("Nom déjà utilisé.")
                    else:
                        uid = db.authenticate(u.strip(), p)
                        if uid:
                            st.session_state.update(user_id=uid, username=u.strip())
                            st.rerun()
                        else:
                            st.error("Identifiants invalides.")
    else:
        st.success(st.session_state.username, icon=":material/account_circle:")
        st.caption(tr("history"))
        for c in db.list_conversations(st.session_state.user_id)[:15]:
            if st.button(c["title"], key=f"c{c['id']}", icon=":material/chat_bubble_outline:",
                         use_container_width=True):
                st.session_state.update(conv_id=c["id"], messages=db.get_messages(c["id"]))
                st.rerun()
        if st.button(tr("logout"), icon=":material/logout:"):
            for k, v in DEFAULTS.items():
                if k not in PREFS:      # (modifier un widget déjà rendu lèverait une exception)
                    st.session_state[k] = v
            st.rerun()

    st.divider()
    k_top = st.slider("Top-k", 2, 8, 4)
    do_verify = st.toggle("Vérification anti-hallucination", True)

# Injection du thème (après la barre latérale, où se fait le choix).
st.markdown(theme_css(normalize_theme(st.session_state.theme)), unsafe_allow_html=True)

# ------------------------------------------------------------------ header
st.markdown(f'<div class="hero"><h1>OmniDoc Studio</h1><p>{tr("tag")}</p></div>',
            unsafe_allow_html=True)

# ------------------------------------------------------------------ sources
with st.expander(tr("sources"), expanded=st.session_state.rag is None):
    c1, c2 = st.columns(2)
    pdf_files = c1.file_uploader(tr("pdfs"), type=["pdf"], accept_multiple_files=True)
    img_files = c2.file_uploader(tr("imgs"), type=["png", "jpg", "jpeg", "webp"],
                                 accept_multiple_files=True)
    index_user_imgs = c2.checkbox(tr("index_imgs"), value=False)

    if st.button(tr("build"), type="primary"):
        if not pdf_files and not img_files:
            st.warning(tr("need"))
        else:
            llm, bar = get_llm(), st.progress(0.0, text="Extraction…")
            for f in pdf_files:                                  # conserve les nouvelles versions éditées
                st.session_state.docs.setdefault(f.name, f.getvalue())
            docs = st.session_state.docs
            steps = max(1, len(docs) + len(img_files))
            done, visual = 0, []
            for name, data in docs.items():
                bar.progress(done / steps, text=f"Texte + OCR : {name}")
                try:
                    st.session_state.pages[name] = extract_pages(data)
                except Exception as e:  # PDF chiffré, corrompu…
                    log.exception("Extraction impossible : %s", name)
                    st.error(f"« {name} » illisible : {e}")
                    done += 1
                    continue
                visual += caption_pdf_images(
                    llm, name, data,
                    on_error=lambda page, e: st.warning(f"Image p.{page} ignorée : {e}"))
                done += 1
            for f in img_files:
                bar.progress(done / steps, text=f"Vision : {f.name}")
                data = f.getvalue()
                try:
                    desc = describe_cached(llm, data, f.type)
                    st.session_state.image_descs[f.name] = desc
                    st.session_state.image_bytes[f.name] = data
                    if index_user_imgs:
                        visual.append({"kind": "visual", "source": f"image:{f.name}", "page": 1,
                                       "chunk": 1, "text": desc, "thumb": make_thumb(data)})
                except Exception as e:
                    log.exception("Légendage impossible : %s", f.name)
                    st.error(f"Gemini : {e}")
                done += 1
            bar.progress(0.95, text="Indexation hybride (FAISS + BM25)…")
            rag = MultiRAG(get_embedder())
            rag.set_text(build_text_chunks(st.session_state.pages))
            rag.set_visual(visual)
            st.session_state.rag = rag
            bar.empty()
            t, v = rag.sizes
            st.success(f"Index texte : {t} chunks · Index visuel : {v} images", icon=":material/check_circle:")

active_img = None
if st.session_state.image_descs:
    active_img = st.selectbox(":material/image: Image active (utilisée comme contexte des questions)",
                              ["—"] + list(st.session_state.image_descs))
    if active_img != "—":
        with st.expander("Compréhension de l'image"):
            st.image(st.session_state.image_bytes[active_img], width=320)
            st.write(st.session_state.image_descs[active_img])
    else:
        active_img = None

tab_chat, tab_edit, tab_ins = st.tabs([f":material/forum: {tr('chat')}", f":material/edit_document: {tr('edit')}",
                                  f":material/insights: {tr('insights')}"])


# ------------------------------------------------------------------ chat
def show_hits(hits):
    for h in hits:
        icon = ":material/description:" if h["kind"] == "text" else ":material/image:"
        label = f"{icon} {h['source']} · p.{h['page']}"
        with st.expander(f"{label}  —  rrf {h['rrf']}"):
            if h["kind"] == "visual" and h.get("thumb"):
                st.image(h["thumb"], width=300)
            st.caption(h["text"][:500])
            if h["kind"] == "text" and h["source"] in st.session_state.docs:
                st.image(cached_page(st.session_state.docs[h["source"]], h["page"], (h["text"],)))


with tab_chat:
    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar=USER_AVATAR if m["role"] == "user" else BOT_AVATAR):
            st.markdown(m["content"])
            meta = m.get("meta")
            if meta:
                st.markdown(f'<span class="badge">route : {meta["route"]}</span>'
                            f'<span class="badge">fidélité : {meta["verdict"]} {meta["score"] or ""}</span>',
                            unsafe_allow_html=True)
                show_hits(meta["hits"])

    question = st.chat_input(tr("ask"))
    if question:
        rag = st.session_state.rag
        desc = st.session_state.image_descs.get(active_img) if active_img else None
        if rag is None and not desc:
            st.warning(tr("need"))
        else:
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(question)
            with st.chat_message("assistant", avatar=BOT_AVATAR):
                with st.spinner("Routage → recherche hybride → génération…"):
                    try:
                        res = ask(question, rag, get_llm(), image_desc=desc,
                                  lang=st.session_state.lang, k=k_top, verify=do_verify)
                    except Exception as e:
                        log.exception("Échec de la réponse")
                        st.error(f"Échec de la génération : {e}")
                        st.stop()
                answer, route, hits, ver = res.text, res.route, res.hits, res.verification
                st.markdown(answer)
                meta = {"route": route, "verdict": ver.get("verdict", "n/a"),
                        "score": ver.get("score"), "hits": hits}
                st.markdown(f'<span class="badge">route : {route}</span>'
                            f'<span class="badge">fidélité : {meta["verdict"]} {meta["score"] or ""}</span>',
                            unsafe_allow_html=True)
                show_hits(hits)
            st.session_state.messages += [{"role": "user", "content": question},
                                          {"role": "assistant", "content": answer, "meta": meta}]
            if st.session_state.user_id:
                if st.session_state.conv_id is None:
                    st.session_state.conv_id = db.create_conversation(st.session_state.user_id, question)
                db.save_message(st.session_state.conv_id, "user", question)
                db.save_message(st.session_state.conv_id, "assistant", answer)

    if st.session_state.messages:
        txt = conversation_to_txt(st.session_state.messages, st.session_state.lang)
        st.download_button(tr("export"), txt.encode("utf-8-sig"), export_filename(),
                           mime="text/plain", icon=":material/download:")

# ------------------------------------------------------------------ éditeur
with tab_edit:
    docs = st.session_state.docs
    if not docs:
        st.info("Chargez un PDF puis cliquez sur « Construire » pour l'activer dans l'éditeur.")
    else:
        name = st.selectbox("Document", list(docs), key="edit_doc")
        current = st.session_state.edited.get(name, docs[name])
        n = page_count(current)
        st.caption(f"{n} page(s)")
        cmd = st.text_input("Commande en langage naturel",
                            placeholder="ex. supprime les pages 2 à 4, tourne la page 1 de 90°, "
                                        "caviarde « Dupont », ajoute le filigrane BROUILLON")
        a, b, c = st.columns(3)
        if a.button("Générer le plan", icon=":material/auto_awesome:") and cmd.strip():
            try:
                st.session_state.plan = get_llm().parse_edit(cmd, n)
                if not st.session_state.plan:
                    st.warning("Aucune action reconnue : reformulez la commande.")
            except Exception as e:
                st.error(f"Commande non comprise : {e}")
        if b.button("Caviarder les données personnelles", icon=":material/shield:"):
            st.session_state.plan = [{"op": "redact_pii"}]
        if c.button("Scanner les données personnelles", icon=":material/search:"):
            st.json(scan_pii(current))

        if st.session_state.plan is not None:
            plan_txt = st.text_area("Plan d'actions (modifiable avant exécution)",
                                    json.dumps(st.session_state.plan, ensure_ascii=False, indent=2),
                                    height=180)
            if st.button("Appliquer", type="primary", icon=":material/play_arrow:"):
                try:
                    new_pdf, log = apply_actions(current, json.loads(plan_txt))
                    st.session_state.edited[name] = new_pdf
                    st.session_state.plan = None
                    for line in log:
                        st.write(line)
                    current = new_pdf
                except Exception as e:
                    st.error(f"Échec : {e}")

        if name in st.session_state.edited:
            d1, d2 = st.columns(2)
            d1.download_button("Télécharger le PDF modifié", st.session_state.edited[name],
                               f"edited_{name}", mime="application/pdf", icon=":material/download:")
            if d2.button("Adopter cette version (puis reconstruire l'index)", icon=":material/check_circle:"):
                st.session_state.docs[name] = st.session_state.edited.pop(name)
                st.rerun()

        page_no = st.number_input("Aperçu — page", 1, page_count(current), 1)
        st.image(cached_page(current, int(page_no)))

        st.divider()
        picks = st.multiselect("Fusionner des PDF", list(docs))
        if len(picks) >= 2 and st.button("Fusionner", icon=":material/merge:"):
            st.session_state.docs["fusion.pdf"] = merge_pdfs(
                [st.session_state.edited.get(p, docs[p]) for p in picks])
            st.success("« fusion.pdf » ajouté. Reconstruisez l'index pour l'inclure.")

# ------------------------------------------------------------------ insights
with tab_ins:
    if not st.session_state.pages:
        st.info(tr("need"))
    else:
        doc_name = st.selectbox("Document", list(st.session_state.pages), key="ins_doc")
        pages = st.session_state.pages[doc_name]
        m1, m2 = st.columns(2)
        m1.metric("Pages", len(pages))
        m2.metric("Pages issues de l'OCR", sum(p["ocr"] for p in pages))
        if st.button("Résumé intelligent", icon=":material/summarize:"):
            full = "\n".join(p["text"] for p in pages)
            st.markdown(get_llm().summarize(full, st.session_state.lang))
        if desc_all := st.session_state.rag and st.session_state.rag.visual:
            st.subheader("Images détectées dans les PDF")
            cols = st.columns(3)
            for i, ch in enumerate(desc_all.chunks):
                if ch["source"] == doc_name:
                    cols[i % 3].image(ch["thumb"], caption=f"p.{ch['page']}")
