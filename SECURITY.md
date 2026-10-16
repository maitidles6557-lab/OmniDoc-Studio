# Security policy

## Supported versions

Only the latest release on `main` receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private reporting instead:
**Security → Report a vulnerability** on this repository.

Include a description, steps to reproduce, and the potential impact. You can expect an acknowledgement
within a few days. Please allow reasonable time for a fix before any public disclosure.

## Scope and design notes

- API keys are read from environment variables or `st.secrets`. They are never stored in the database
  or written to logs by the application.
- User passwords are hashed with PBKDF2-HMAC-SHA256 and a per-user random salt.
- LLM output is treated as untrusted: edit plans are schema-validated before any PDF operation runs.
- PII redaction is regex-based and best-effort. It is **not** a compliance guarantee, so review output
  before sharing documents.

## If you accidentally commit a key

Revoke it at the provider immediately, then remove it from history. Deleting it in a later commit does
not make it safe.
