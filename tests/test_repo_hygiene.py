"""Repository hygiene: no committed secrets, and example files stay blank."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Provider-style key shapes (Groq, Google "AIza…" and "AQ.…", OpenAI-style). Placeholders like "gsk_..." don't match.
KEY_PATTERN = re.compile(r"(?:gsk_|AIza|sk-)[A-Za-z0-9_\-]{20,}|\bAQ\.[A-Za-z0-9_\-]{30,}")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".example", ".cfg", ".ini", ""}
LOCAL_ONLY = {".env", ".streamlit/secrets.toml"}   # git-ignored, legitimately hold real keys locally


def _tracked_files() -> list[Path]:
    """Files git tracks; falls back to a filesystem walk when git is unavailable (e.g. a zip)."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True, timeout=15).stdout.splitlines()
        return [ROOT / p for p in out if (ROOT / p).is_file()]
    except (OSError, subprocess.SubprocessError):
        skip = {".git", ".venv", "venv", "__pycache__", "node_modules"}
        return [p for p in ROOT.rglob("*") if p.is_file() and not skip & set(p.relative_to(ROOT).parts)]


class HygieneTests(unittest.TestCase):
    def test_detector_recognises_known_key_shapes(self):
        """Guards the guard: synthetic keys in each supported shape must be flagged, placeholders must not."""
        fakes = ["gsk_" + "a1B2c3D4" * 5, "AIza" + "x9Y8z7W6" * 5, "AQ." + "Ab8RN6Kc" * 5, "sk-" + "q1w2e3r4" * 4]
        for fake in fakes:
            self.assertTrue(KEY_PATTERN.search(f'KEY = "{fake}"'), f"missed shape: {fake[:4]}…")
        for placeholder in ('GROQ_API_KEY = "gsk_..."', 'GEMINI_API_KEY = "..."', "GROQ_API_KEY="):
            self.assertIsNone(KEY_PATTERN.search(placeholder))

    def test_no_key_like_strings_in_source(self):
        leaks = []
        for path in _tracked_files():
            rel = path.relative_to(ROOT).as_posix()
            if rel in LOCAL_ONLY or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if KEY_PATTERN.search(text):
                leaks.append(rel)
        self.assertEqual(leaks, [], f"Possible API key committed in: {leaks}")

    def test_env_example_has_no_values(self):
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            if line.startswith(("GROQ_API_KEY=", "GEMINI_API_KEY=")):
                self.assertEqual(line.split("=", 1)[1].strip(), "", f"{line.split('=')[0]} must be blank")

    def test_secrets_files_are_gitignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for pattern in (".env", ".streamlit/secrets.toml"):
            self.assertIn(pattern, ignore)


if __name__ == "__main__":
    unittest.main()
