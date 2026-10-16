# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- English README (French version kept as `README.fr.md`) and `docs/ARCHITECTURE.md` with Mermaid diagrams.
- Repository hygiene test that fails if a key-like string is committed.
- `SECURITY.md`, `CONTRIBUTING.md`, issue and pull-request templates, Dependabot, pre-commit config.
- CI: separate lint job, Python 3.10 and 3.12 test matrix, coverage report, least-privilege permissions,
  concurrency cancellation.
- `make help`, `make coverage` and `make clean` targets.

### Changed
- Docker image now runs as a non-root user.
- Moved internal engineering notes to `docs/ENGINEERING_NOTES.fr.md`.

## [3.0.0] - 2026-10-15

### Added
- Three UI themes (dark, light, soft), persisted in the URL.
- "New conversation" button that keeps sources and the index.
- Plain-text `.txt` conversation export including sources and faithfulness score.
- Three workflow diagrams and the script that renders them.

### Earlier
- MultiRAG with TEXT and VISUAL indexes, hybrid dense + BM25 retrieval fused by RRF, query router,
  faithfulness verification, citations highlighted on PDF pages, natural-language PDF editor,
  GDPR redaction, accounts and history on SQLite.
