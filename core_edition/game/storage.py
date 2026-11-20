"""Use browser-local storage when available; a malformed save is never overwritten."""

import sys

from economy import Town

import saves


class Storage:
    def __init__(self, backend=None):
        self.backend = backend
        self.notice = ""
        self.blocked = False

    @classmethod
    def for_browser(cls):
        result = cls()
        if sys.platform == "emscripten":
            import platform

            try:
                return cls(platform.window.localStorage)
            except Exception:  # noqa: BLE001 - browser bridge exceptions vary by engine
                result.notice = "Browser storage is blocked. Progress lasts for this session."
                return result
        result.notice = "Storage unavailable. Progress lasts for this session."
        return result

    def restore(self):
        if self.backend is not None:
            try:
                raw = self.backend.getItem(saves.KEY)
                if raw is not None:
                    return saves.load(str(raw))
            except Exception:  # noqa: BLE001 - handle browser storage errors at the boundary
                self.blocked = True
                self.notice = "Could not read the save. Playing without overwriting it."
        return Town()

    def write(self, town):
        if self.backend is not None and not self.blocked:
            try:
                self.backend.setItem(saves.KEY, saves.dump(town))
                self.notice = ""
            except Exception:  # noqa: BLE001 - handle browser storage errors at the boundary
                self.notice = "Could not save. Check browser storage permissions."
