"""Authentification (PBKDF2) et historique des conversations (SQLite)."""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from .config import DB_PATH

PBKDF2_ITERATIONS = 310_000


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    """Connexion avec commit/rollback automatique, *fermée* à la sortie (le `with` natif ne ferme pas)."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db() -> None:
    """Crée les tables au premier lancement (aucun compte n'est embarqué)."""
    with _db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id));
        CREATE TABLE IF NOT EXISTS captions (
            key TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id);
        """)


def _hash(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return h.hex(), salt.hex()


def create_user(username: str, password: str) -> int | None:
    """Crée un compte ; renvoie son id, ou None si le nom est déjà pris."""
    h, s = _hash(password)
    try:
        with _db() as db:
            cur = db.execute(
                "INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
                (username, h, s, datetime.now().isoformat()))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def authenticate(username: str, password: str) -> int | None:
    """Renvoie l'id utilisateur si les identifiants sont valides, sinon None."""
    with _db() as db:
        u = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not u:
        return None
    h, _ = _hash(password, bytes.fromhex(u["salt"]))
    return u["id"] if hmac.compare_digest(h, u["password_hash"]) else None


def create_conversation(user_id: int, title: str) -> int:
    now = datetime.now().isoformat()
    with _db() as db:
        return db.execute(
            "INSERT INTO conversations (user_id,title,created_at,updated_at) VALUES (?,?,?,?)",
            (user_id, title[:60], now, now)).lastrowid


def save_message(conv_id: int, role: str, content: str) -> None:
    now = datetime.now().isoformat()
    with _db() as db:
        db.execute("INSERT INTO messages (conversation_id,role,content,created_at) VALUES (?,?,?,?)",
                   (conv_id, role, content, now))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))


def list_conversations(user_id: int) -> list[sqlite3.Row]:
    with _db() as db:
        return db.execute("SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
                          (user_id,)).fetchall()


def get_messages(conv_id: int) -> list[dict]:
    with _db() as db:
        rows = db.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id",
                          (conv_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_history(user_id: int) -> None:
    with _db() as db:
        db.execute("DELETE FROM messages WHERE conversation_id IN "
                   "(SELECT id FROM conversations WHERE user_id=?)", (user_id,))
        db.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))


# ---------- cache des légendes d'images (évite de repayer Gemini pour la même image) ----------
def get_caption(key: str) -> str | None:
    with _db() as db:
        row = db.execute("SELECT text FROM captions WHERE key=?", (key,)).fetchone()
    return row["text"] if row else None


def set_caption(key: str, text: str) -> None:
    with _db() as db:
        db.execute("INSERT OR REPLACE INTO captions (key,text,created_at) VALUES (?,?,?)",
                   (key, text, datetime.now().isoformat()))
