import unittest

from tests.conftest import FakeEmbedder
from core.retrieval import (BM25, HybridIndex, MultiRAG, build_text_chunks, rrf,
                            split_text, tokenize)

PAGES = {"a.pdf": [
    {"page": 1, "text": "La facture d'électricité du mois de mars s'élève à 120 euros."},
    {"page": 2, "text": "Le contrat de maintenance couvre les ascenseurs et le chauffage."},
    {"page": 3, "text": "Réunion du conseil d'administration prévue en septembre."},
]}


class TextTests(unittest.TestCase):
    def test_tokenize_folds_accents(self):
        self.assertEqual(tokenize("Électricité ÉTÉ"), ["electricite", "ete"])

    def test_split_text_overlap_and_bounds(self):
        text = " ".join(f"mot{i}" for i in range(400))
        parts = split_text(text, size=200, overlap=40)
        self.assertGreater(len(parts), 3)
        self.assertTrue(all(len(p) <= 200 for p in parts))
        self.assertTrue(parts[0].split()[-1] in parts[1])   # recouvrement

    def test_split_short_and_empty(self):
        self.assertEqual(split_text("court"), ["court"])
        self.assertEqual(split_text(""), [])

    def test_build_chunks_metadata(self):
        chunks = build_text_chunks(PAGES)
        self.assertEqual(len(chunks), 3)
        self.assertEqual({c["kind"] for c in chunks}, {"text"})
        self.assertEqual(chunks[1]["page"], 2)


class BM25Tests(unittest.TestCase):
    def test_ranking_and_accent_insensitivity(self):
        bm = BM25([c["text"] for c in build_text_chunks(PAGES)])
        scores = bm.scores("electricite facture")
        self.assertEqual(int(scores.argmax()), 0)
        self.assertEqual(float(bm.scores("zzz inconnu").sum()), 0.0)

    def test_empty_corpus(self):
        self.assertEqual(len(BM25([]).scores("x")), 0)


class RRFTests(unittest.TestCase):
    def test_consensus_wins(self):
        fused = rrf([[1, 2, 3], [2, 1, 4]])
        self.assertEqual({i for i, _ in fused.most_common(2)}, {1, 2})
        self.assertGreater(fused[2], fused[3])


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.idx = HybridIndex(build_text_chunks(PAGES), FakeEmbedder(), min_dense=0.1)

    def test_hybrid_search_finds_relevant_page(self):
        hits = self.idx.search("facture électricité mars", k=2)
        self.assertEqual(hits[0]["page"], 1)
        self.assertIn("rrf", hits[0])

    def test_empty_index_returns_nothing(self):
        self.assertEqual(HybridIndex([], FakeEmbedder()).search("x"), [])

    def test_multirag_routes(self):
        visual = [{"kind": "visual", "source": "a.pdf", "page": 2, "chunk": 1,
                   "text": "graphique des ventes trimestrielles en barres"}]
        rag = MultiRAG(FakeEmbedder())
        rag.set_text(build_text_chunks(PAGES))
        rag.set_visual(visual)
        self.assertEqual(rag.sizes, (3, 1))
        kinds = lambda route: {h["kind"] for h in rag.search("graphique des ventes", route)}
        self.assertEqual(kinds("visual"), {"visual"})
        self.assertNotIn("visual", kinds("text"))
        self.assertIn("visual", kinds("both"))


if __name__ == "__main__":
    unittest.main()
