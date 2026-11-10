"""Serve a local browser preview using the same Python game and drawing code."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import time

from tycoon import BODY_COLORS, COSTUMES, HAIR_COLORS, HEIGHT, WIDTH, Game, Town, market_start


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Foundry Town</title>
<style>
body { margin: 0; display: grid; place-items: center; min-height: 100vh; background: #101f28; }
.game { position: relative; width: min(100vw, GAME_WIDTHpx, calc(100vh * GAME_WIDTH / GAME_HEIGHT)); }
svg { display: block; width: 100%; height: auto; outline: none; }
svg:focus-visible { outline: 2px solid #ffc66c; }
#profile-button { position: absolute; top: calc(1900% / GAME_HEIGHT); left: 91.67%;
    width: 5.83%; height: calc(5800% / GAME_HEIGHT);
    background: transparent; border: 0; cursor: pointer; }
#profile-button:hover, #profile-button:focus-visible { outline: 2px solid #ffc66c; }
dialog { width: min(320px, 82vw); padding: 24px; background: #253842; color: #f2f7f6;
    border: 1px solid #586768; border-radius: 12px; font: 16px "Segoe UI", sans-serif; }
dialog::backdrop { background: #101f28b8; }
form { display: grid; gap: 12px; }
h2 { margin: 0 0 4px; }
label { display: grid; gap: 4px; }
input, select, button { font: inherit; }
input, select { padding: 7px; background: #101f28; color: #f2f7f6; border: 1px solid #80999a; border-radius: 4px; }
.actions { display: flex; justify-content: end; gap: 8px; margin-top: 6px; }
.actions button { padding: 6px 10px; border: 0; border-radius: 4px; cursor: pointer; }
.actions button[type=submit] { background: #ffc66c; color: #101f28; }
#save-error { color: #ffc66c; margin: 0; }
</style>
<div class="game">
<svg tabindex="0" aria-label="Foundry Town. Click to play with WASD, E and Q."
     viewBox="0 0 GAME_WIDTH GAME_HEIGHT"><g id="city">STATIC_CITY</g><g id="live">LIVE_FRAME</g></svg>
<button id="profile-button" type="button" aria-label="Customize player profile" title="Player profile"></button>
</div>
<dialog aria-labelledby="profile-title">
  <form>
    <h2 id="profile-title">Player profile</h2>
    <label>Name <input name="name" maxlength="24" autofocus></label>
    <label>Character color <select name="body">BODY_OPTIONS</select></label>
    <label>Hair color <select name="hair">HAIR_OPTIONS</select></label>
    <label>Costume <select name="costume">COSTUME_OPTIONS</select></label>
    <p id="save-error" role="status" hidden>Could not save. Try again.</p>
    <div class="actions"><button id="cancel" type="button">Cancel</button><button type="submit">Save profile</button></div>
  </form>
</dialog>
<script>
const board = document.querySelector('svg');
const live = document.getElementById('live');
const dialog = document.querySelector('dialog');
const form = dialog.querySelector('form');
const saveError = document.getElementById('save-error');
let profile = JSON.parse(document.getElementById('profile-button').dataset.profile);
document.getElementById('profile-button').addEventListener('click', () => {
    for (const [key, value] of Object.entries(profile)) form.elements.namedItem(key).value = value;
    saveError.hidden = true;
    dialog.showModal();
});
document.getElementById('cancel').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => board.focus());
form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    try {
        const response = await fetch(location.pathname, {
            method: 'POST',
            body: JSON.stringify({profile: Object.fromEntries(new FormData(form))})
        });
        if (!response.ok) throw new Error('Profile update failed');
        profile = await response.json();
        dialog.close();
    } catch {
        saveError.hidden = false;
    } finally {
        button.disabled = false;
    }
});
const held = new Set();
const actions = [];
const controls = ['w', 'a', 's', 'd', 'arrowup', 'arrowleft', 'arrowdown', 'arrowright', 'e', 'q'];
board.addEventListener('pointerdown', () => board.focus());
board.addEventListener('keydown', event => {
    const key = event.key.toLowerCase();
    if (!controls.includes(key)) return;
    event.preventDefault();
    if ((key === 'e' || key === 'q') && !event.repeat) actions.push(key);
    held.add(key);
});
board.addEventListener('keyup', event => held.delete(event.key.toLowerCase()));
board.addEventListener('blur', () => { held.clear(); actions.length = 0; });
window.addEventListener('blur', () => held.clear());
async function update() {
    if (!document.hidden && document.hasFocus() && document.activeElement === board) {
        try {
            const response = await fetch(location.pathname, {
                method: 'POST',
                body: JSON.stringify({keys: [...held], actions: actions.splice(0)})
            });
            if (response.ok) live.innerHTML = await response.text();
        } catch {
            held.clear();
        }
    }
    setTimeout(update, 32);
}
update();
</script>
""".replace("GAME_WIDTH", str(WIDTH)).replace("GAME_HEIGHT", str(HEIGHT))


class SvgCanvas:
    def __init__(self):
        self.layers = {"city": [], "live": []}

    def delete(self, tag):
        self.layers[tag].clear()

    def create_rectangle(self, x1, y1, x2, y2, *, tags="city", **style):
        self.layers[tags].append(
            f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" {self.style(style)}/>'
        )

    def create_oval(self, x1, y1, x2, y2, *, tags="city", **style):
        self.layers[tags].append(
            f'<ellipse cx="{(x1+x2)/2}" cy="{(y1+y2)/2}" '
            f'rx="{(x2-x1)/2}" ry="{(y2-y1)/2}" {self.style(style)}/>'
        )

    def create_polygon(self, *coordinates, tags="city", **style):
        points = " ".join(str(value) for value in coordinates)
        self.layers[tags].append(f'<polygon points="{points}" {self.style(style)}/>')

    def create_text(self, x, y, *, text, fill, anchor, font, tags):
        family, size, weight = font
        alignment = {"w": "start", "e": "end", "center": "middle"}[anchor]
        self.layers[tags].append(
            f'<text x="{x}" y="{y}" text-anchor="{alignment}" dominant-baseline="central" '
            f'fill="{fill}" font-family="{family}, sans-serif" font-size="{size * 4 / 3}" '
            f'font-weight="{weight}">{escape(text)}</text>'
        )

    @staticmethod
    def style(style):
        return (f'fill="{style.get("fill", "none")}" '
                f'stroke="{style.get("outline", "none")}" stroke-width="{style.get("width", 0)}"')


class BrowserGame(Game):
    def __init__(self):
        self.canvas = SvgCanvas()
        self.town = Town()
        self.market_started_at = market_start()
        self.last_tick = time.monotonic()
        self.draw_city()
        self.draw_live()

    def update(self, keys, actions):
        now = time.monotonic()
        dt = min(now - self.last_tick, 0.05)
        self.last_tick = now
        self.town.sync_market(time.time() - self.market_started_at)
        self.town.advance(dt)
        dx = int("d" in keys or "arrowright" in keys) - int("a" in keys or "arrowleft" in keys)
        dy = int("s" in keys or "arrowdown" in keys) - int("w" in keys or "arrowup" in keys)
        self.town.move(dx, dy, dt)
        for action in actions:
            site = self.town.nearby()
            if action == "e" or (action == "q" and site and site.role == "SUPPLIER"):
                self.town.interact(bulk=(action == "q"))
        self.draw_live()
        return "".join(self.canvas.layers["live"])


def main():
    game = BrowserGame()
    path = "/" + secrets.token_urlsafe(16)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, content, mime):
            payload = content.encode()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path != path:
                self.send_error(404)
                return
            game.town.sync_market(time.time() - game.market_started_at)
            game.draw_live()
            page = PAGE.replace("STATIC_CITY", "".join(game.canvas.layers["city"]))
            page = page.replace(
                'id="profile-button"',
                f'id="profile-button" data-profile="{escape(json.dumps(game.town.profile), quote=True)}"',
            )
            for marker, choices in (("BODY_OPTIONS", BODY_COLORS), ("HAIR_OPTIONS", HAIR_COLORS), ("COSTUME_OPTIONS", COSTUMES)):
                page = page.replace(marker, "".join(f"<option>{escape(choice)}</option>" for choice in choices))
            self.reply(page.replace("LIVE_FRAME", "".join(game.canvas.layers["live"])), "text/html")

        def do_POST(self):
            if self.path != path:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    raise ValueError
                data = json.loads(self.rfile.read(length))
                if isinstance(data, dict) and isinstance(data.get("profile"), dict):
                    game.town.set_profile(data["profile"])
                    game.draw_live()
                    self.reply(json.dumps(game.town.profile), "application/json")
                    return
                keys, actions = data["keys"], data["actions"]
                if not isinstance(keys, list) or not isinstance(actions, list):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                self.send_error(400)
                return
            self.reply(game.update(keys, actions), "image/svg+xml")

        def log_message(self, format, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        print(f"http://127.0.0.1:{server.server_port}{path}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()

