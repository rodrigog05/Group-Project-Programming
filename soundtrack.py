"""Non-blocking playback for the bundled original guitar soundtrack."""
from pathlib import Path
import shutil
import subprocess
import sys
import threading


class BackgroundMusic:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).parent / "assets" / "saudade_do_tejo.wav"
        self.enabled = True
        self.available = self.path.is_file()
        self._stop = threading.Event()
        self._process = None
        self._thread = None

    def play(self):
        if not self.enabled or not self.available:
            return
        if sys.platform == "win32":
            import winsound
            try:
                winsound.PlaySound(str(self.path), winsound.SND_FILENAME | winsound.SND_ASYNC |
                                  winsound.SND_LOOP | winsound.SND_NODEFAULT)
            except RuntimeError:
                self.available = False
            return
        command = ["afplay"] if sys.platform == "darwin" else next(
            ([player] for player in ("paplay", "aplay") if shutil.which(player)), None
        )
        if command is None or not shutil.which(command[0]):
            self.available = False
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self._process = subprocess.Popen(command + [str(self.path)],
                                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    code = self._process.wait()
                    if code and not self._stop.is_set():
                        self.available = False
                        break
                except OSError:
                    self.available = False
                    break
            self._process = None

        self._thread = threading.Thread(target=loop, daemon=True, name="foundry-music")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(None, 0)
        elif self._process is not None and self._process.poll() is None:
            self._process.terminate()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.25)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.play() if self.enabled else self.stop()


def music_for(root):
    if not hasattr(root, "foundry_music"):
        root.foundry_music = BackgroundMusic()
        root.foundry_music.play()
    return root.foundry_music
