import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from save_api import Handler
from saves import RemoteSaves, SaveConflict, SaveDatabase
from tycoon import Order, Town, pack_save, unpack_save


class DesktopSaveTest(unittest.TestCase):
    def test_resume_isolated_player_and_reject_stale_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.sqlite3"
            with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
                server.database = SaveDatabase(path)
                url = f"http://127.0.0.1:{server.server_port}"
                player = RemoteSaves(url, server.database.add_player())
                friend = RemoteSaves(url, server.database.add_player())
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    town = Town()
                    town.cash = 15
                    town.orders[0] = Order(9, 45)
                    snapshot = pack_save(town, 1000)
                    self.assertEqual(player.load(None), (0, None))
                    self.assertEqual(player.save(None, 0, snapshot), 1)
                    with self.assertRaises(SaveConflict):
                        player.save(None, 0, pack_save(Town(), 2000))
                    server.database = SaveDatabase(path)
                    revision, data = player.load(None)
                    restored, start = unpack_save(data)
                    self.assertEqual((revision, start, restored.cash, restored.orders[0]),
                                     (1, 1000, 15, Order(9, 45)))
                    self.assertEqual(friend.load(None), (0, None))
                    with self.assertRaises(HTTPError) as rejected:
                        RemoteSaves(url, "unknown").load(None)
                    self.assertEqual(rejected.exception.code, 401)
                finally:
                    server.shutdown()
                    thread.join()
