"""Retained delivery vehicles, with no simulation or per-frame sprite rebuilding."""
from dataclasses import dataclass

from logistics import route_position


MAX_VISIBLE_ROUTES = 8


@dataclass
class FleetSprite:
    tag: str
    kind: str
    cargo_item: int
    light_items: tuple
    position: tuple = (0, 0)
    visible: bool = False
    loaded: bool = False


class FleetView:
    """Move cached sprite groups from the model's saved route progress only."""

    def __init__(self, canvas, sites, zoom=1.25, position_fn=route_position):
        self.canvas, self.sites, self.zoom = canvas, sites, zoom
        self.position_fn = position_fn
        self.sprites = {}
        self.night = False

    def _create(self, route):
        c = self.canvas
        tag, kind = f"delivery_{route['id']}", route["kind"]
        lights = []
        if kind == "drone":
            c.create_oval(-11, 8, 12, 14, fill="#8d9e96", outline="", tags=tag)
            c.create_line(-10, -8, 10, 8, fill="#3f626a", width=3, tags=tag)
            c.create_line(-10, 8, 10, -8, fill="#3f626a", width=3, tags=tag)
            for x, y in ((-11, -9), (11, -9), (-11, 9), (11, 9)):
                c.create_oval(x-5, y-4, x+5, y+4, fill="#bbd3ce", outline="#31565f", width=1, tags=tag)
                c.create_line(x-4, y, x+4, y, fill="#416975", width=1, tags=tag)
            c.create_rectangle(-5, -6, 5, 6, fill="#e2eee1", outline="#466c73", tags=tag)
            cargo = c.create_rectangle(-4, 2, 4, 9, fill="#caa76a", outline="#6b7b71", tags=tag)
            for x in (-4, 4):
                lights.append(c.create_oval(x-1, -6, x+1, -3, fill="#709fa8", outline="", tags=tag))
        else:
            c.create_oval(-19, 1, 20, 12, fill="#8b9a8e", outline="", tags=tag)
            c.create_polygon(-18, -9, 9, -9, 18, -3, 18, 8, -18, 8,
                             fill="#94c4b6", outline="#3d6866", width=1, tags=tag)
            c.create_rectangle(-15, -6, 1, 5, fill="#477c91", outline="#d4e4d5", tags=tag)
            cargo = c.create_rectangle(-12, -3, -4, 3, fill="#e3c180", outline="#b0c5b8", tags=tag)
            c.create_rectangle(7, -6, 13, 2, fill="#b4d8dc", outline="", tags=tag)
            for x in (-11, 11):
                c.create_oval(x-3, 6, x+3, 11, fill="#344f53", outline="", tags=tag)
            for y in (-5, 4):
                lights.append(c.create_rectangle(16, y, 19, y+2, fill="#b4d8dc", outline="", tags=tag))
        c.scale(tag, 0, 0, self.zoom, self.zoom)
        c.itemconfigure(tag, state="hidden")
        sprite = FleetSprite(tag, kind, cargo, tuple(lights))
        self.sprites[route["id"]] = sprite
        if self.night:
            for item in lights:
                c.itemconfigure(item, fill="#fff0ad")
        return sprite

    def paint(self, ledger, camera):
        """Cull offscreen routes and move visible groups only at changed pixels."""
        routes = ledger.get("routes", ()) if isinstance(ledger, dict) else ()
        if not routes and not self.sprites:
            return
        routes = routes[:MAX_VISIBLE_ROUTES]
        ids = {route["id"] for route in routes}
        for route_id in tuple(self.sprites):
            if route_id not in ids:
                self.canvas.delete(self.sprites.pop(route_id).tag)
        for route in routes:
            x, y = self.position_fn(route, self.sites)
            visible = camera.sees(x, y, margin=35)
            sprite = self.sprites.get(route["id"])
            if sprite is not None and sprite.kind != route["kind"]:
                self.canvas.delete(sprite.tag)
                del self.sprites[route["id"]]
                sprite = None
            if sprite is None:
                if not visible:
                    continue
                sprite = self._create(route)
            loaded = route["load"] > 0
            if sprite.visible != visible:
                self.canvas.itemconfigure(sprite.tag, state="normal" if visible else "hidden")
            if sprite.visible != visible or sprite.loaded != loaded:
                self.canvas.itemconfigure(sprite.cargo_item, state="normal" if visible and loaded else "hidden")
                sprite.loaded = loaded
            sprite.visible = visible
            if visible:
                position = round(x*self.zoom), round(y*self.zoom)
                if position != sprite.position:
                    self.canvas.move(sprite.tag, position[0]-sprite.position[0], position[1]-sprite.position[1])
                    sprite.position = position

    def set_night(self, enabled):
        if self.night == enabled:
            return
        self.night = enabled
        for sprite in self.sprites.values():
            for item in sprite.light_items:
                self.canvas.itemconfigure(item, fill="#fff0ad" if enabled else "#b4d8dc")

    def set_zoom(self, zoom):
        """Rebuild on zoom changes, never during ordinary vehicle movement."""
        if zoom != self.zoom:
            for sprite in self.sprites.values():
                self.canvas.delete(sprite.tag)
            self.sprites.clear()
            self.zoom = zoom
