# Améliorations apportées

Version de référence : le code de `core/` et `app.py` fourni dans l'archive, avec le `core/config.py` le plus récent
(modèle Gemini par défaut `gemini-3.6-flash`). Le comportement fonctionnel est conservé.

## Structure
- `app.py` ne contient plus la logique métier : la chaîne question → route → recherche → réponse → vérification est dans
  `core/pipeline.py` (`ask()`), testable sans Streamlit ; le légendage d'images (avec cache) aussi.
- Nouveaux modules : `prompts.py` (tous les prompts), `i18n.py` (textes UI), `plan.py` (validation du plan d'édition),
  `pii.py` (regex RGPD), `pipeline.py`.
- Imports lourds différés (Streamlit, Groq, google-genai, FAISS, PyMuPDF dans `pipeline`) : le moteur est importable et testable sans eux.

## Qualité du code
- Type hints et docstrings sur les fonctions publiques ; `logging` (`setup_logging`) à la place des `except: continue` silencieux.
- Connexions SQLite **réellement fermées** (le `with sqlite3.connect()` d'origine ne ferme pas), `foreign_keys` activé, index ajoutés.
- Timeouts + retries : Groq (`timeout`, `max_retries`), Gemini (backoff exponentiel sur 429/5xx/timeout uniquement), Tesseract (`OCR_TIMEOUT_S`).
- Clé API absente : `MissingAPIKeyError` explicite au lieu d'une erreur obscure au démarrage ; chaque client est créé à la demande.
- PDF protégé par mot de passe : message clair, sans faire planter la construction de l'index.
- Configuration étendue (`.env.example`) : modèle d'embedding, tailles de chunks, seuil dense, RRF k, timeouts, niveau de log, chemin de la base.

## IA / RAG
- **Plan d'édition validé** (`plan.sanitize_actions`) avant exécution : types normalisés (`"2-4"`, `"3"`, listes sales), ops inconnues
  écartées avec avertissement, termes < 2 caractères refusés (évitait de caviarder chaque « a »), filigrane borné. Auparavant une valeur
  mal typée renvoyée par le LLM faisait échouer tout le plan.
- **Extraction JSON robuste** (`extract_json`) : tolère le texte autour, les blocs ```json et un `[1]` parasite ; l'ancienne regex gloutonne `{.*}` échouait dès qu'il y avait deux objets.
- **Vérification de fidélité plus juste** : elle voit désormais les passages **complets** (avant : tronqués à 600 caractères alors que la réponse
  s'appuyait sur 900) et la description de l'image active ; score borné 0-100 et verdict normalisé (`normalize_verdict`).
- **Garde anti-injection** dans le prompt de réponse (le contexte extrait des documents est traité comme donnée non fiable).
- **BM25** : index inversé (ne parcourt que les documents contenant les termes) et normalisation des accents/diacritiques (« electricite » trouve « électricité »).
- **Dense** : repli NumPy exact si FAISS est absent ; seuil `MIN_DENSE_SCORE` et `RRF_K` configurables.
- **Résumé** : échantillonnage début/milieu/fin au lieu des 9000 premiers caractères seulement.
- **Coût API** : cache SQLite des légendes d'images (clé = SHA-256 + modèle) ; plus de re-légendage à chaque reconstruction de l'index.
- **Performance UI** : rendu des pages citées mis en cache (`st.cache_data`) ; il était recalculé pour chaque citation à chaque interaction.
- Métrique « pages issues de l'OCR » corrigée : une page n'est comptée que si l'OCR a réellement produit du texte.

## Tests et DX
- `tests/` : 40 tests hors-ligne (faux LLM, faux embedder) : chunking, BM25, RRF, index hybride, routage, vérification, plan d'édition, PII,
  retries, base SQLite, cache de légendes, pipeline de bout en bout, éditeur PDF.
- `README.md` (architecture + diagrammes), `.env.example`, `.gitignore` complété, `Dockerfile`, `Makefile`, CI GitHub Actions, `pyproject.toml`
  (ruff), dépendances bornées (`requirements.txt`) + `requirements-dev.txt`.
- Trois workflows lisibles (RAG, image + LLM, projet complet) dans `docs/workflows/`, générés par `tools/render_workflows.py`.

## Secrets
- Aucune clé en dur trouvée. `omnidoc.db` envoyé séparément est vide (0 compte) et reste exclu (`*.db` dans `.gitignore`) ; les `.pyc` fournis sont ignorés.

## Changements pouvant casser
- `core.editor.PII_PATTERNS` est conservé (ré-exporté depuis `core.pii`). `scan_pii()` renvoie les mêmes clés qu'avant.
- `LLM.verify()` gagne un paramètre optionnel `image_desc` (rétro-compatible). `LLM.parse_edit()` renvoie désormais des actions déjà nettoyées.
- `redact` / `highlight` ignorent les termes d'un seul caractère.
- `LLM.__init__` n'ouvre plus les clients à la construction (erreur de clé reportée au premier appel).
- Nouvelle table SQLite `captions` créée automatiquement (les bases existantes restent compatibles).

## Non vérifié
- **Non exécuté ici** (pas de réseau, ni Streamlit, PyMuPDF, FAISS, sentence-transformers, Tesseract) : l'interface Streamlit, l'éditeur PDF
  réel (les 5 tests `test_editor.py` sont écrits mais ignorés faute de PyMuPDF), l'OCR, les appels Groq/Gemini et BGE-M3.
  `python -m compileall` passe sur tout le code ; les 35 autres tests passent.
- Les versions minimales de `requirements.txt` n'ont pas été testées ; les noms de modèles par défaut (`openai/gpt-oss-20b`, `gemini-3.6-flash`) sont repris tels quels.
- Non fait (hors périmètre « sans casser ») : persistance de l'index sur disque, reranker, historique de conversation injecté dans le prompt,
  limitation de tentatives de connexion.

## Interface (v3)
- Trois thèmes (sombre, clair, soft) : `core/theme.py`, choix conservé dans l'URL.
- « Nouvelle conversation » accessible à tous (avant : réservé aux comptes connectés).
- Export de la conversation en `.txt` (`core/export.py`), au lieu de `.md`.
- Icônes Material et avatar du chat à la place des emojis.
- Correction : la déconnexion réécrivait `st.session_state.lang` après le rendu du sélecteur de langue (exception Streamlit) ; langue et thème sont désormais conservés.
- Tests : `tests/test_export_theme.py` (export, palettes, contraste, clés i18n).
