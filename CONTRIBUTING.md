# Contributing

Thanks for your interest in OmniDoc Studio! Bug reports, ideas and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/maitidles6557-lab/omnidoc-studio.git
cd omnidoc-studio
python -m venv .venv && source .venv/bin/activate
make install
pre-commit install        # optional: lint + private-key scan on every commit
```

You do **not** need API keys to run the test suite. It uses a fake LLM and a fake embedder.

## Workflow

1. Open an issue first for anything non-trivial, so the approach can be agreed before you invest time.
2. Branch from `main`: `feat/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
3. Keep changes focused. One logical change per pull request.
4. Add or update tests. New behaviour without a test will be asked for one.
5. Run `make test` and `make lint` before pushing.
6. Open a pull request using the template. CI must be green.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(retrieval): add cross-encoder reranking
fix(editor): refuse to delete every page
docs: clarify OCR setup
test(plan): cover malformed rotation angles
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Code guidelines

- **Keep `core/` UI-independent.** Nothing in `core/` may import Streamlit.
- **Treat LLM output as untrusted.** Validate it (see `core/plan.py`) before acting on it.
- **Degrade gracefully.** External calls (LLM, OCR, cache) should fail soft where the user can still make progress.
- **Add type hints and docstrings** to public functions; use `logging`, never `print`.
- **Put prompts in `core/prompts.py`** and settings in `core/config.py`, not inline.
- **Never commit secrets.** `.env` and `.streamlit/secrets.toml` are git-ignored; a test enforces this.

## Reporting bugs

Use the bug report template and include your environment and logs (`LOG_LEVEL=DEBUG`).
**Remove API keys before pasting anything.** For security issues, see [SECURITY.md](SECURITY.md).
