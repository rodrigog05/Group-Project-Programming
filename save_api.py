"""Run a Foundry Town save API or issue a private player key."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3

from saves import SaveConflict, SaveDatabase, database_path, player_id


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def handle_save(self, writing):
        if self.path != "/api/save":
            return self.reply(404, {"error": "Unknown endpoint"})
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self.reply(401, {"error": "Player key required"})
        player = player_id(auth[7:])
        db = self.server.database
        try:
            revision, save = db.load(player)
            if not writing:
                return self.reply(200, {"revision": revision, "save": save})
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768:
                return self.reply(413, {"error": "Invalid save size"})
            if "If-Match" not in self.headers:
                return self.reply(428, {"error": "Revision required"})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("state"), dict) or not isinstance(data.get("marketStart"), (int, float)):
                raise ValueError("Invalid save format")
            new_revision = db.save(player, int(self.headers["If-Match"]), data)
            return self.reply(200, {"revision": new_revision})
        except PermissionError:
            self.reply(401, {"error": "Invalid player key"})
        except SaveConflict as exc:
            self.reply(409, {"error": str(exc)})
        except (ValueError, RecursionError):
            self.reply(400, {"error": "Invalid save or revision"})
        except sqlite3.Error:
            self.reply(503, {"error": "Storage unavailable"})

    def do_GET(self):
        self.handle_save(False)

    def do_PUT(self):
        self.handle_save(True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "add-player"])
    parser.add_argument("--database", default=database_path())
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    database = SaveDatabase(args.database)
    if args.command == "add-player":
        print(database.add_player())
    else:
        with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
            server.database = database
            print(f"Listening on http://127.0.0.1:{args.port}", flush=True)
            server.serve_forever()
