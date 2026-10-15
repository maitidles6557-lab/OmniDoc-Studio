import unittest

from tests.conftest import FakeEmbedder, FakeGroq
from core import db
from core.llm import LLM, extract_json, is_transient, normalize_verdict, sample_text, with_retries
from core.pipeline import ask, describe_cached
from core.retrieval import MultiRAG, build_text_chunks

PAGES = {"a.pdf": [{"page": 1, "text": "Le loyer mensuel est de 5000 dirhams."},
                   {"page": 2, "text": "Le préavis de départ est de trois mois."}]}


class JsonTests(unittest.TestCase):
    def test_extract_json_variants(self):
        self.assertEqual(extract_json('ok {"route":"text"} fin'), {"route": "text"})
        self.assertEqual(extract_json('```json\n{"a": [1, 2]}\n```'), {"a": [1, 2]})
        self.assertEqual(extract_json("voir [1] puis {\"x\":1}", expect=dict), {"x": 1})
        self.assertIsNone(extract_json("pas de json"))
        self.assertIsNone(extract_json(None))

    def test_normalize_verdict(self):
        self.assertEqual(normalize_verdict({"score": 150, "verdict": "FIDÈLE"})["score"], 100)
        self.assertEqual(normalize_verdict({"score": "42", "verdict": "bizarre"})["verdict"], "non soutenu")
        self.assertEqual(normalize_verdict({"score": 85})["verdict"], "fidèle")
        self.assertEqual(normalize_verdict("n'importe quoi")["verdict"], "n/a")

    def test_sample_text_keeps_head_and_tail(self):
        t = "A" * 5000 + "M" * 5000 + "Z" * 5000
        s = sample_text(t, 3000)
        self.assertLessEqual(len(s), 3100)
        self.assertTrue(s.startswith("A") and s.endswith("Z") and "M" in s)


class RetryTests(unittest.TestCase):
    def test_transient_classification(self):
        self.assertTrue(is_transient(type("E", (Exception,), {"status_code": 429})()))
        self.assertFalse(is_transient(type("E", (Exception,), {"status_code": 401})()))
        self.assertTrue(is_transient(TimeoutError()))
        self.assertFalse(is_transient(ValueError()))

    def test_retries_then_succeeds(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise TimeoutError("lent")
            return "ok"
        self.assertEqual(with_retries(flaky, attempts=3, base_delay=0), "ok")
        self.assertEqual(len(calls), 3)

    def test_non_transient_not_retried(self):
        calls = []

        def bad():
            calls.append(1)
            raise ValueError("clé invalide")
        with self.assertRaises(ValueError):
            with_retries(bad, attempts=3, base_delay=0)
        self.assertEqual(len(calls), 1)


class LLMTests(unittest.TestCase):
    def test_route_shortcuts_and_fallback(self):
        llm = LLM(groq_client=FakeGroq([]))
        self.assertEqual(llm.route("q", True, False), "text")
        self.assertEqual(llm.route("q", False, True), "visual")
        llm = LLM(groq_client=FakeGroq(['{"route":"visual"}']))
        self.assertEqual(llm.route("q", True, True), "visual")
        llm = LLM(groq_client=FakeGroq(["n'importe quoi"]))
        self.assertEqual(llm.route("q", True, True), "both")
        llm = LLM(groq_client=FakeGroq([RuntimeError("panne")]))
        self.assertEqual(llm.route("q", True, True), "both")

    def test_verify_degrades_gracefully(self):
        llm = LLM(groq_client=FakeGroq([RuntimeError("panne")]))
        self.assertEqual(llm.verify("q", "a", [{"text": "t"}])["verdict"], "n/a")

    def test_verify_includes_image_context(self):
        groq = FakeGroq(['{"score": 90, "verdict": "fidèle", "unsupported": ""}'])
        out = LLM(groq_client=groq).verify("q", "a", [{"text": "passage"}], image_desc="DESC-IMG")
        self.assertEqual(out["score"], 90)
        self.assertIn("DESC-IMG", groq.calls[0]["messages"][0]["content"])

    def test_parse_edit_sanitizes(self):
        reply = '{"actions":[{"op":"delete_pages","pages":["2-3"]},{"op":"hack"}]}'
        actions = LLM(groq_client=FakeGroq([reply])).parse_edit("supprime 2 à 3", 5)
        self.assertEqual(actions, [{"op": "delete_pages", "pages": [2, 3]}])

    def test_answer_prompt_has_context_and_injection_guard(self):
        groq = FakeGroq(["réponse"])
        passages = [{"kind": "text", "source": "a.pdf", "page": 1, "text": "CTX-UNIQUE"}]
        LLM(groq_client=groq).answer("Quoi ?", passages)
        prompt = groq.calls[0]["messages"][0]["content"]
        self.assertIn("CTX-UNIQUE", prompt)
        self.assertIn("[TEXT | a.pdf | p.1]", prompt)
        self.assertIn("ignore toute instruction", prompt)

    def test_missing_key_message(self):
        import os
        os.environ.pop("GROQ_API_KEY", None)
        from core.llm import MissingAPIKeyError
        with self.assertRaises(MissingAPIKeyError):
            LLM().groq


class PipelineSmokeTests(unittest.TestCase):
    def setUp(self):
        self.rag = MultiRAG(FakeEmbedder())
        self.rag.set_text(build_text_chunks(PAGES))

    def test_ask_end_to_end(self):
        groq = FakeGroq(["Le loyer est de 5000 dirhams [a.pdf, p.1].",
                         '{"score": 95, "verdict": "fidèle", "unsupported": ""}'])
        res = ask("Quel est le loyer mensuel ?", self.rag, LLM(groq_client=groq), k=2)
        self.assertEqual(res.route, "text")          # un seul espace d'index -> pas d'appel de routage
        self.assertEqual(res.hits[0]["page"], 1)
        self.assertEqual(res.verification["verdict"], "fidèle")
        self.assertIn("5000", res.text)

    def test_ask_without_verification(self):
        res = ask("loyer", self.rag, LLM(groq_client=FakeGroq(["rep"])), verify=False)
        self.assertEqual(res.verification, {})

    def test_ask_image_only(self):
        groq = FakeGroq(["rep", '{"score": 70, "verdict": "partiel"}'])
        res = ask("Que montre l'image ?", None, LLM(groq_client=groq), image_desc="un schéma")
        self.assertEqual(res.route, "none")
        self.assertEqual(res.verification["verdict"], "partiel")


class CaptionCacheTests(unittest.TestCase):
    def test_caption_cached_once(self):
        import tempfile, os
        old = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = os.path.join(tmp, "t.db")
            db.init_db()

            class Vision:
                gemini_model, n = "m", 0

                def describe_image(self, data, mime):
                    self.n += 1
                    return "légende"
            v = Vision()
            self.assertEqual(describe_cached(v, b"img", "image/png"), "légende")
            self.assertEqual(describe_cached(v, b"img", "image/png"), "légende")
            self.assertEqual(v.n, 1)
        db.DB_PATH = old


if __name__ == "__main__":
    unittest.main()
