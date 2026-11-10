"""Player saves for the desktop game and its optional shared Python API."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from contextlib import closing
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SaveConflict(ValueError):
    pass


def database_path():
    return Path.home() / ".foundry-town" / "saves.sqlite3"


class SaveDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0, save TEXT)""")

    def connect(self):
        return sqlite3.connect(self.path)

    def add_player(self):
        token = secrets.token_urlsafe(32)
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO players(id) VALUES (?)", (player_id(token),))
        return token

    def local_player(self):
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO players(id) VALUES ('local')")
        return "local"

    def load(self, player):
        with closing(self.connect()) as db:
            row = db.execute("SELECT revision, save FROM players WHERE id=?", (player,)).fetchone()
        if row is None:
            raise PermissionError("Invalid player key")
        return row[0], json.loads(row[1]) if row[1] else None

    def save(self, player, revision, data):
        encoded = json.dumps(data, allow_nan=False)
        with closing(self.connect()) as db, db:
            result = db.execute("UPDATE players SET revision=revision+1, save=? WHERE id=? AND revision=?",
                                (encoded, player, revision))
            if result.rowcount != 1:
                raise SaveConflict("A newer save exists. Reopen the game to load it.")
        return revision + 1


def player_id(token):
    return hashlib.sha256(token.encode()).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class RemoteSaves:
    def __init__(self, url, token):
        parts = urlsplit(url)
        if not token or not parts.hostname:
            raise ValueError("Set FOUNDRY_SAVE_URL and FOUNDRY_PLAYER_KEY together.")
        if parts.scheme != "https" and not (
            parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Use HTTPS for a remote save server.")
        self.url = url.rstrip("/") + "/api/save"
        self.headers = {"Authorization": "Bearer " + token}
        self.opener = build_opener(NoRedirect())

    def request(self, data=None, revision=None):
        headers = dict(self.headers)
        body = None
        if data is not None:
            headers.update({"Content-Type": "application/json", "If-Match": str(revision)})
            body = json.dumps(data, allow_nan=False).encode()
        request = Request(self.url, data=body, headers=headers, method="GET" if body is None else "PUT")
        try:
            with self.opener.open(request, timeout=5) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 409:
                raise SaveConflict("A newer save exists. Reopen the game to load it.") from exc
            raise

    def load(self, player):
        result = self.request()
        return result["revision"], result["save"]

    def save(self, player, revision, data):
        return self.request(data, revision)["revision"]


def desktop_storage():
    url = os.environ.get("FOUNDRY_SAVE_URL", "")
    token = os.environ.get("FOUNDRY_PLAYER_KEY", "")
    if url or token:
        return RemoteSaves(url, token), None
    db = SaveDatabase(database_path())
    return db, db.local_player()
