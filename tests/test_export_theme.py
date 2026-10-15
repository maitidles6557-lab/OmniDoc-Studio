"""Export .txt de la conversation et thèmes de l'interface."""
import unittest
from datetime import datetime

from core.export import conversation_to_txt, export_filename, strip_markdown
from core.i18n import T
from core.theme import DEFAULT_THEME, PALETTES, THEMES, normalize_theme, theme_css

NOW = datetime(2026, 10, 16, 9, 30)
MSGS = [
    {"role": "user", "content": "Quel est le **total** ?"},
    {"role": "assistant", "content": "## Résultat\nLe total est `42` [facture.pdf, p.2].",
     "meta": {"route": "text", "verdict": "fidèle", "score": 95,
              "hits": [{"source": "facture.pdf", "page": 2}, {"source": "facture.pdf", "page": 2}]}},
]


class ExportTests(unittest.TestCase):
    def test_extension_is_txt(self):
        self.assertTrue(export_filename(NOW).endswith(".txt"))
        self.assertEqual(export_filename(NOW), "conversation_20261016_0930.txt")

    def test_plain_text_without_markdown(self):
        out = conversation_to_txt(MSGS, "fr", NOW)
        self.assertNotIn("**", out)
        self.assertNotIn("`", out)
        self.assertNotIn("##", out)
        self.assertIn("[Vous]", out)
        self.assertIn("[OmniDoc]", out)
        self.assertIn("Le total est 42", out)

    def test_sources_deduplicated_and_fidelity(self):
        out = conversation_to_txt(MSGS, "fr", NOW)
        self.assertEqual(out.count("Sources : facture.pdf p.2"), 1)
        self.assertIn("Fidélité : fidèle 95", out)

    def test_other_languages_and_encoding(self):
        out = conversation_to_txt(MSGS, "ar", NOW)
        self.assertIn("[أنت]", out)
        self.assertEqual(out.encode("utf-8-sig").decode("utf-8-sig"), out)

    def test_empty_conversation(self):
        self.assertIn("OmniDoc", conversation_to_txt([], "en", NOW))

    def test_strip_markdown_links_and_bullets(self):
        self.assertEqual(strip_markdown("* a\n* [lien](http://x.y)"), "- a\n- lien (http://x.y)")


class ThemeTests(unittest.TestCase):
    def test_three_themes_with_complete_palettes(self):
        self.assertEqual(set(THEMES), {"dark", "light", "soft"})
        keys = set(PALETTES["dark"])
        for name in THEMES:
            self.assertEqual(set(PALETTES[name]), keys, name)
            css = theme_css(name)
            self.assertIn(PALETTES[name]["bg"], css)
            self.assertNotRegex(css, r"%\(")          # aucun champ non résolu

    def test_themes_are_visually_distinct(self):
        self.assertEqual(len({PALETTES[t]["bg"] for t in THEMES}), 3)

    def test_unknown_theme_falls_back(self):
        self.assertEqual(normalize_theme("neon"), DEFAULT_THEME)
        self.assertEqual(normalize_theme(None), DEFAULT_THEME)
        self.assertEqual(normalize_theme("soft"), "soft")
        self.assertEqual(theme_css("neon"), theme_css(DEFAULT_THEME))

    def test_text_contrast_is_readable(self):
        def lum(hex_):
            rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

        for name in THEMES:
            p = PALETTES[name]
            for bg in ("bg", "surface"):
                hi, lo = sorted((lum(p["text"]), lum(p[bg])), reverse=True)
                self.assertGreaterEqual((hi + .05) / (lo + .05), 7, f"{name}/{bg}")

    def test_i18n_has_theme_keys_in_all_languages(self):
        for lang in T:
            for key in ("theme", "t_dark", "t_light", "t_soft", "export", "new", "new_hint", "new_done", "lang"):
                self.assertIn(key, T[lang], f"{lang}.{key}")
        self.assertEqual(set(T["fr"]), set(T["en"]))
        self.assertEqual(set(T["fr"]), set(T["ar"]))


if __name__ == "__main__":
    unittest.main()
