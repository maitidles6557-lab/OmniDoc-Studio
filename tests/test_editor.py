"""Tests de l'éditeur PDF : nécessitent PyMuPDF (ignorés s'il est absent)."""
import unittest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None


def make_pdf(pages):
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@unittest.skipUnless(pymupdf, "PyMuPDF non installé")
class EditorTests(unittest.TestCase):
    def setUp(self):
        from tests import conftest  # noqa: F401
        from core import editor
        self.editor = editor
        self.pdf = make_pdf([f"Page {i} contact jean@example.com" for i in range(1, 6)])

    def test_delete_keep_reorder(self):
        e = self.editor
        out, _ = e.apply_actions(self.pdf, [{"op": "delete_pages", "pages": [2, 3]}])
        self.assertEqual(e.page_count(out), 3)
        out, _ = e.apply_actions(self.pdf, [{"op": "keep_pages", "pages": [1, 5]}])
        self.assertEqual(e.page_count(out), 2)
        out, log = e.apply_actions(self.pdf, [{"op": "reorder", "order": [5, 4, 3, 2, 1]}])
        with pymupdf.open(stream=out, filetype="pdf") as d:
            self.assertIn("Page 5", d[0].get_text())

    def test_refuses_to_empty_document(self):
        out, log = self.editor.apply_actions(self.pdf, [{"op": "delete_pages", "pages": [1, 2, 3, 4, 5]}])
        self.assertEqual(self.editor.page_count(out), 5)
        self.assertTrue(any("viderait" in line for line in log))

    def test_redaction_removes_underlying_text(self):
        out, _ = self.editor.apply_actions(self.pdf, [{"op": "redact_pii"}])
        with pymupdf.open(stream=out, filetype="pdf") as d:
            self.assertNotIn("jean@example.com", "".join(p.get_text() for p in d))
        self.assertEqual(self.editor.scan_pii(out)["email"], 0)
        self.assertEqual(self.editor.scan_pii(self.pdf)["email"], 5)

    def test_malformed_plan_does_not_crash(self):
        out, log = self.editor.apply_actions(self.pdf, [{"op": "delete_pages", "pages": ["x"]}, "bad"])
        self.assertEqual(self.editor.page_count(out), 5)

    def test_merge_and_render(self):
        merged = self.editor.merge_pdfs([self.pdf, self.pdf])
        self.assertEqual(self.editor.page_count(merged), 10)
        png = self.editor.render_page(merged, 99, ["Page 1 contact"])   # page hors bornes -> clamp
        self.assertTrue(png.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
