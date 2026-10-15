import os
import tempfile
import unittest

from core import db


class DBTests(unittest.TestCase):
    def setUp(self):
        self._old, self._tmp = db.DB_PATH, tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self._tmp.name, "t.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._old
        self._tmp.cleanup()

    def test_auth_flow(self):
        uid = db.create_user("alice", "motdepasse1")
        self.assertIsNotNone(uid)
        self.assertIsNone(db.create_user("alice", "autre-mdp-12"))     # doublon
        self.assertEqual(db.authenticate("alice", "motdepasse1"), uid)
        self.assertIsNone(db.authenticate("alice", "faux-mdp"))
        self.assertIsNone(db.authenticate("inconnu", "x"))

    def test_history_roundtrip_and_delete(self):
        uid = db.create_user("bob", "motdepasse1")
        cid = db.create_conversation(uid, "T" * 100)
        db.save_message(cid, "user", "salut")
        db.save_message(cid, "assistant", "bonjour")
        self.assertEqual([m["role"] for m in db.get_messages(cid)], ["user", "assistant"])
        self.assertEqual(len(db.list_conversations(uid)[0]["title"]), 60)
        db.delete_history(uid)
        self.assertEqual(db.list_conversations(uid), [])
        self.assertEqual(db.get_messages(cid), [])

    def test_init_is_idempotent(self):
        db.init_db()
        db.init_db()


if __name__ == "__main__":
    unittest.main()
