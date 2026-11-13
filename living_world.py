"""Scrollable world, retained ambient actors and a small navigation map."""
from dataclasses import dataclass
import math
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from types import SimpleNamespace

from lisbon_scene import LisbonScene, WORLD_WIDTH, WORLD_BOTTOM, RIVER_TOP, RIVER_BOTTOM, bridge_center, draw_character
from windows_canvas import world_canvas
from lisbon_landmarks import LANDMARKS
from wayfinding import STAGES, site_guide
from guidance import compass, next_step
from tram import TRAM_STOPS
from logistics_view import FleetView

WORLD_TOP = 104
STATUS_LABEL_RADIUS = 360


def status_label_visible(camera, player_x, player_y, site, guided_name=None):
    """Detailed trade figures follow nearby places; baked purpose signs stay visible."""
    x, y = site.x+88, site.y+100
    return camera.sees(x, y, 140) and (
        site.name == guided_name or (x-player_x)**2+(y-player_y)**2 <= STATUS_LABEL_RADIUS**2
    )


@dataclass
class Camera:
    width: int
    height: int
    zoom: float = 1.25
    x: float = 0
    y: float = WORLD_TOP

    @property
    def visible_width(self):
        return self.width/self.zoom

    @property
    def visible_height(self):
        return self.height/self.zoom

    def follow(self, x, y, dt=0, snap=False):
        target_x = min(max(0, x-self.visible_width/2), max(0, WORLD_WIDTH-self.visible_width))
        target_y = min(max(WORLD_TOP, y-self.visible_height/2), max(WORLD_TOP, WORLD_BOTTOM-self.visible_height))
        weight = 1 if snap else 1-math.exp(-max(0, dt)*10)
        self.x += (target_x-self.x)*weight
        self.y += (target_y-self.y)*weight
        self.x = min(max(0, self.x), max(0, WORLD_WIDTH-self.visible_width))
        self.y = min(max(WORLD_TOP, self.y), max(WORLD_TOP, WORLD_BOTTOM-self.visible_height))

    def sees(self, x, y, margin=70):
        return (self.x-margin <= x <= self.x+self.visible_width+margin
                and self.y-margin <= y <= self.y+self.visible_height+margin)

    def project(self, x, y):
        return (x-self.x)*self.zoom, (y-self.y)*self.zoom


@dataclass
class AmbientActor:
    tag: str
    start: tuple
    end: tuple
    speed: float
    offset: float
    kind: str
    drawn_x: float = 0
    drawn_y: float = 0
    visible: bool = True

    def position(self, elapsed):
        length = max(1, math.dist(self.start, self.end))
        progress = (elapsed*self.speed/length+self.offset) % 2
        progress = progress if progress <= 1 else 2-progress
        x = self.start[0]+(self.end[0]-self.start[0])*progress
        y = self.start[1]+(self.end[1]-self.start[1])*progress
        if self.kind == "pedestrian":
            y += math.sin(elapsed*8+self.offset)*.8
        elif self.kind == "boat":
            y += math.sin(elapsed*.7+self.offset)*1.5
        return x, y


class LivingWorld:
    def __init__(self, game, sites):
        self.game, self.sites = game, sites
        self.canvas = world_canvas(game.canvas, bg="#284a56", highlightthickness=0, borderwidth=0)
        self.zoom = 1.25
        self.camera = Camera(1, 1, self.zoom)
        self.night = False
        self.actors_enabled = True
        self.labels = {}
        self.last_labels = 0
        self.last_time = time.perf_counter()
        self.fps = 0.0
        self.fps_started = self.last_time
        self.fps_frames = 0
        self.last_scroll = None
        self.map_visible = True
        self.shown = True
        self.bounds = (1, 1, 0)
        self.destination = None
        self.navigation_text = ""
        self.last_navigation_update = 0
        self.font = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
        self.minimap = tk.Canvas(self.canvas, width=248, height=214, highlightthickness=1,
                                 highlightbackground="#9cae99", bg="#18343f")
        self.notification = tk.Label(self.canvas, bg="#18343f", fg="#f4d18c", font=(self.font, 10, "bold"),
                                      padx=14, pady=8, justify="center")
        self.notification_text = ""
        self.navigation = tk.Label(self.canvas, bg="#18343f", fg="#ffe0a1", font=(self.font, 10, "bold"),
                                   padx=14, pady=8, justify="center")
        self.build_minimap()
        self.load_scene()

    def label(self, x, y, value, size=10, color="#f8f4df", bold=False, anchor="w", tag="city"):
        return self.canvas.create_text(x, y, text=value, fill=color, anchor=anchor,
                                       font=(self.font, max(7, round(size*self.zoom)), "bold" if bold else "normal"), tags=tag)

    def load_scene(self):
        c = self.canvas
        c.delete("all")
        directory = Path(__file__).parent/"assets"
        self.background_tiles = []
        paths = [directory/f"world_{round(self.zoom*100)}_{phase}.png" for phase in ("day", "night")]
        if getattr(c, "native_world", False):
            self.day_image, self.night_image = c.load_world(*paths)
        else:
            self.day_image, self.night_image = (tk.PhotoImage(master=c, file=str(path)) for path in paths)
            item = c.create_image(0, 0, image=self.day_image, anchor="nw")
            self.background_tiles.append((item, self.day_image, self.night_image))
        c.configure(scrollregion=(0, WORLD_TOP*self.zoom, WORLD_WIDTH*self.zoom, WORLD_BOTTOM*self.zoom))
        proxy = SimpleNamespace(canvas=c, scale_x=self.zoom, display_scale=self.zoom, label=self.label)
        self.scene = LisbonScene(proxy, self.sites, draw=False)
        self.scene.create_tram()
        c.scale("tram", 0, 0, self.zoom, self.zoom)
        self.actors = []
        self.light_items = []
        self.create_actors()
        self.fleet = FleetView(c, self.sites, self.zoom)
        self.labels = {}
        self.selection_site = None
        self.player_style = None
        self.player_stride = None
        self.player_position = (0, 0)
        self.last_power = None
        self.last_map_update = 0
        self.selection = c.create_rectangle(0, 0, 1, 1, outline="#f4cc79", width=2, state="hidden")
        self.destination_marker = c.create_oval(0, 0, 1, 1, fill="", outline="#ffd177", width=3, state="hidden")
        self.update_destination_markers()
        self.spark = c.create_line(479*self.zoom, 864*self.zoom, 488*self.zoom, 854*self.zoom,
                                   492*self.zoom, 869*self.zoom, fill="#fff0b1", width=2, state="hidden")
        self.night = None
        self.set_night(self.game.town.market_elapsed % 300 >= 180)
        self.last_scroll = None
        self.camera.zoom = self.zoom
        self.camera.follow(self.game.town.x, self.game.town.y, snap=True)
        self.last_labels = 0
        self.game.scene = self.scene
        self.game.background_image = self.day_image
        self.game.night_image = self.night_image

    def create_actors(self):
        rng = random.Random(2815)
        routes = (((32, 280), (1160, 280)), ((40, 465), (1160, 465)),
                  ((50, 647), (1150, 647)), ((1260, 280), (WORLD_WIDTH-70, 280)),
                  ((1260, 465), (WORLD_WIDTH-90, 465)), ((1270, 645), (WORLD_WIDTH-80, 645)),
                  ((90, 1090), (WORLD_WIDTH-120, 1090)), ((85, 1395), (WORLD_WIDTH-130, 1395)),
                  ((65, WORLD_BOTTOM-55), (WORLD_WIDTH-110, WORLD_BOTTOM-55)))
        for index in range(30):
            start, end = routes[index % len(routes)]
            self.actor("pedestrian", start, end, rng.uniform(20, 34), rng.random()*2,
                       rng.choice(("#b37262", "#547d8b", "#81926f", "#ba9d61", "#8a7195")))
        for index, y in enumerate((291, 308, 476, 493, 650, 666, 1101, 1119, 1362, 1378,
                                   WORLD_BOTTOM-38, WORLD_BOTTOM-22)):
            self.actor("car", (15, y), (WORLD_WIDTH-20, y), rng.uniform(75, 125), rng.random()*2,
                       rng.choice(("#9b584e", "#c6c5b5", "#759ca5", "#b89b62")))
        for start, end, speed in (((400, 780), (900, 780), 32),
                                  ((1240, 802), (bridge_center(802, True)-80, 802), 62),
                                  ((bridge_center(860, True)+90, 860), (WORLD_WIDTH-65, 860), 38),
                                  ((430, 835), (870, 835), 20)):
            self.actor("boat", start, end, speed, rng.random()*2, "#f2e4c9")
        for index in range(14):
            x = 360+index*(WORLD_WIDTH-500)/13
            self.actor("ripple", (x, 750+index % 4*32),
                       (x+60, 750+index % 4*32), 4, rng.random()*2, "#b3d5d5")

    def actor(self, kind, start, end, speed, offset, color):
        c = self.canvas
        tag = f"ambient_{len(self.actors)}"
        if kind == "pedestrian":
            c.create_oval(-5, 3, 6, 8, fill="#8c947d", width=0, tags=tag)
            c.create_oval(-4, -7, 4, 5, fill=color, width=0, tags=tag)
            c.create_oval(-3, -13, 3, -6, fill="#dfbb93", width=0, tags=tag)
        elif kind == "car":
            c.create_polygon(-15, -6, -11, -9, 11, -9, 15, -5, 15, 5, 10, 8, -10, 8, -15, 4,
                              smooth=True, fill=color, outline="#435c5c", tags=tag)
            item = c.create_rectangle(-7, -5, 7, 4, fill="#aac5c8", outline="", tags=tag)
            self.light_items.append(item)
        elif kind == "boat":
            c.create_line(-33, 3, -21, 0, -32, -3, fill="#abd0ce", width=1, tags=tag)
            c.create_polygon(-24, -8, 21, -8, 31, 0, 21, 8, -24, 8, smooth=True,
                              fill=color, outline="#879d9a", tags=tag)
            c.create_rectangle(-10, -5, 12, 5, fill="#c8d4ca", outline="", tags=tag)
            item = c.create_rectangle(-6, -3, 8, 3, fill="#688b98", outline="", tags=tag)
            self.light_items.append(item)
        else:
            c.create_line(-10, 0, 10, 0, fill=color, width=1, tags=tag)
        c.scale(tag, 0, 0, self.zoom, self.zoom)
        self.actors.append(AmbientActor(tag, start, end, speed, offset, kind))

    def set_night(self, enabled):
        if self.night == enabled:
            return
        self.night = enabled
        if getattr(self.canvas, "native_world", False):
            self.canvas.night = enabled
        for item, day, night in self.background_tiles:
            self.canvas.itemconfigure(item, image=night if enabled else day)
        self.scene.set_night(enabled)
        for item in self.light_items:
            self.canvas.itemconfigure(item, fill="#f5dca0" if enabled else "#aac5c8")
        self.fleet.set_night(enabled)
        self.last_labels = 0

    def resize(self, width, height, top):
        self.camera.width, self.camera.height = max(1, width), max(1, height)
        self.bounds = width, height, top
        if self.shown:
            self.canvas.place(x=0, y=top, width=width, height=height)
        self.notification.configure(wraplength=max(260, width-570))
        self.navigation.configure(wraplength=max(260, width-40))
        self.last_scroll = None
        if self.map_visible:
            self.minimap.place(relx=1, x=-14, y=14, anchor="ne")

    def set_visible(self, enabled):
        if self.shown == enabled:
            return
        self.shown = enabled
        if enabled:
            width, height, top = self.bounds
            self.resize(width, height, top)
        else:
            self.canvas.place_forget()

    def set_zoom(self, zoom):
        if zoom not in (1.0, 1.25, 1.5) or zoom == self.zoom:
            return
        self.zoom = zoom
        self.load_scene()

    def toggle_map(self):
        self.map_visible = not self.map_visible
        if self.map_visible:
            self.minimap.place(relx=1, x=-14, y=14, anchor="ne")
        else:
            self.minimap.place_forget()

    def build_minimap(self):
        c = self.minimap
        self.map_title = c.create_text(10, 11, text="LISBOA · M", fill="#f2d69a", anchor="w", font=(self.font, 8, "bold"))
        c.create_rectangle(8, 26, 240, 170, fill="#9aa994", width=0)
        def point(x, y):
            return 8+x/WORLD_WIDTH*232, 26+(y-WORLD_TOP)/(WORLD_BOTTOM-WORLD_TOP)*144
        self.map_point = point
        c.create_rectangle(*point(0, RIVER_TOP), *point(WORLD_WIDTH, RIVER_BOTTOM), fill="#608f9a", width=0)
        for eastern in (False, True):
            c.create_line(*point(bridge_center(RIVER_TOP, eastern), RIVER_TOP),
                          *point(bridge_center(RIVER_BOTTOM, eastern), RIVER_BOTTOM),
                          fill="#e9dfba", width=2)
        for site in self.sites:
            x, y = point(site.x+88, site.y+52)
            guide = site_guide(site)
            radius = 9 if len(guide.marker) > 1 else 6
            c.create_oval(x-radius, y-6, x+radius, y+6, fill=guide.color, outline="#f0eadc", width=.6)
            c.create_text(x, y, text=guide.marker, fill="#ffffff", font=(self.font, 6 if radius == 9 else 7, "bold"))
        for landmark in LANDMARKS:
            x, y = point(*landmark.map_point)
            c.create_polygon(x, y-5, x+4, y, x, y+5, x-4, y,
                              fill="#ffe0a1", outline="#6a5224", width=1)
        for stop in TRAM_STOPS:
            x, y = point(stop.x, stop.y)
            c.create_rectangle(x-4, y-4, x+4, y+4, fill="#ffe0a1", outline="#6a5224", width=1)
            c.create_text(x, y, text="T", fill="#354f57", font=(self.font, 6, "bold"))
        for stage, x in zip(STAGES[:3], (12, 91, 177)):
            c.create_text(x, 187, text=f"{stage.marker} {stage.key.upper()}", anchor="w",
                          fill={"buy": "#ffd177", "make": "#94d1ff", "sell": "#8de5bc"}[stage.key],
                          font=(self.font, 8, "bold"))
        c.create_text(12, 204, text="◆ Sights · T Tram · P Places", anchor="w", fill="#efe0bd", font=(self.font, 8))
        self.map_view = c.create_rectangle(0, 0, 1, 1, outline="#f8eee0", width=1)
        self.map_player = c.create_oval(0, 0, 1, 1, fill="#f2c15f", outline="#263f4a", width=1)
        self.map_destination = c.create_oval(0, 0, 1, 1, outline="#fff0a8", width=2, state="hidden")

    def set_destination(self, name, x=None, y=None):
        self.destination = None if name is None else (name, float(x), float(y))
        self.navigation_text = ""
        self.update_destination_markers()
        self.update_navigation()

    def update_destination_markers(self):
        if self.destination is None:
            self.canvas.itemconfigure(self.destination_marker, state="hidden")
            self.minimap.itemconfigure(self.map_destination, state="hidden")
            self.navigation.place_forget()
            return
        _, x, y = self.destination
        self.canvas.coords(self.destination_marker, (x-19)*self.zoom, (y-19)*self.zoom,
                           (x+19)*self.zoom, (y+19)*self.zoom)
        self.canvas.itemconfigure(self.destination_marker, state="normal")
        mx, my = self.map_point(x, y)
        self.minimap.coords(self.map_destination, mx-8, my-8, mx+8, my+8)
        self.minimap.itemconfigure(self.map_destination, state="normal")

    def update_navigation(self):
        if self.destination is None:
            return
        name, x, y = self.destination
        town = self.game.town
        distance = math.hypot(x-town.x, y-town.y)
        if distance <= 30:
            action = "Explore the landmark" if any(sight.name == name for sight in LANDMARKS) else "E to interact"
            value = f"Arrived: {name} · {action} · P for Places"
        else:
            (wx, wy), crossing = next_step(town.x, town.y, x, y)
            value = f"{name} · {round(distance)} m · {compass(wx-town.x, wy-town.y)}"
            if crossing:
                value += f" · {crossing}"
            value += " · P for Places"
        if value != self.navigation_text:
            self.navigation.configure(text=value)
            self.navigation.place(relx=.5, rely=1, y=-12, anchor="s")
            self.navigation_text = value

    def update_labels(self, elapsed):
        color = "#f3e3bb" if self.night else "#385360"
        town = self.game.town
        guided_name = self.destination[0] if self.destination else None
        for site in self.sites:
            visible = status_label_visible(self.camera, town.x, town.y, site, guided_name)
            item = self.labels.get(site.name)
            if not visible:
                if item is not None and item[3]:
                    item_id, old_text, old_color, old_visible = item
                    self.canvas.itemconfigure(item_id, state="hidden")
                    self.labels[site.name] = (item_id, old_text, old_color, False)
                continue
            text = town.site_status(site)
            if item is None and visible:
                item_id = self.canvas.create_text((site.x+8)*self.zoom, (site.y+123)*self.zoom,
                                                  text=text, fill=color, anchor="w",
                                                  font=(self.font, -max(10, round(10*self.zoom))))
                self.labels[site.name] = (item_id, text, color, True)
            elif item is not None:
                item_id, old_text, old_color, old_visible = item
                if (old_text, old_color, old_visible) != (text, color, visible):
                    self.canvas.itemconfigure(item_id, text=text, fill=color, state="normal" if visible else "hidden")
                    self.labels[site.name] = (item_id, text, color, visible)

    def render(self, body_colors, hair_colors, costumes):
        now = time.perf_counter()
        dt, self.last_time = min(.15, now-self.last_time), now
        self.fps_frames += 1
        if now-self.fps_started >= 1:
            self.fps = self.fps_frames/(now-self.fps_started)
            self.fps_started, self.fps_frames = now, 0
            self.minimap.itemconfigure(self.map_title, text=f"LISBOA · M · {self.fps:.0f} FPS")
        town, c, zoom = self.game.town, self.canvas, self.zoom
        notice = town.notice if town.elapsed < town.notice_until else (
            f"{town.market_event[0]}\n{town.market_event[1]}" if town.market_event else ""
        )
        if notice != self.notification_text:
            self.notification_text = notice
            self.notification.configure(text=notice)
            if notice:
                self.notification.place(relx=.5, y=10, anchor="n")
            else:
                self.notification.place_forget()
        self.camera.follow(town.x, town.y, dt)
        scroll = round(self.camera.x*zoom), round(self.camera.y*zoom)
        if scroll != self.last_scroll:
            if self.last_scroll is None or scroll[0] != self.last_scroll[0]:
                c.xview_moveto(self.camera.x/WORLD_WIDTH)
            if self.last_scroll is None or scroll[1] != self.last_scroll[1]:
                c.yview_moveto((self.camera.y-WORLD_TOP)/(WORLD_BOTTOM-WORLD_TOP))
            self.last_scroll = scroll
        for actor in self.actors:
            x, y = actor.position(town.elapsed)
            enabled = self.game.traffic_enabled if actor.kind == "car" else self.actors_enabled
            visible = enabled and self.camera.sees(x, y)
            if actor.visible != visible:
                c.itemconfigure(actor.tag, state="normal" if visible else "hidden")
                actor.visible = visible
            if visible:
                px, py = round(x*zoom)/zoom, round(y*zoom)/zoom
                if (px, py) != (actor.drawn_x, actor.drawn_y):
                    c.move(actor.tag, (px-actor.drawn_x)*zoom, (py-actor.drawn_y)*zoom)
                    actor.drawn_x, actor.drawn_y = px, py
        self.fleet.paint(getattr(town, "logistics", None), self.camera)
        self.scene.animate(town.elapsed)
        near = town.nearby()
        selection_site = near.name if near else None
        if selection_site != self.selection_site:
            if near:
                x1, y1, x2, y2 = near.bounds
                c.coords(self.selection, (x1-2)*zoom, (y1-2)*zoom, (x2+2)*zoom, (y2+2)*zoom)
            c.itemconfigure(self.selection, state="normal" if near else "hidden")
            self.selection_site = selection_site
        if now-self.last_labels >= .12:
            self.update_labels(town.elapsed)
            order = town.industry_orders["SHIPYARD"]
            active = order is not None and town.elapsed < order.ready_at and int(town.elapsed*8) % 2 == 0
            c.itemconfigure(self.spark, state="normal" if active else "hidden")
            self.last_labels = now
        x, y = town.x, town.y
        moving = bool(self.game.keys.intersection({"w", "a", "s", "d", "up", "down", "left", "right"}))
        self.update_player(body_colors, hair_colors, costumes, moving)
        if town.power_up != self.last_power:
            c.delete("power")
            if town.power_up is not None:
                name, symbol, color, px, py = self.game.power_up_definitions[town.power_up]
                c.create_oval((px-15)*zoom, (py-15)*zoom, (px+15)*zoom, (py+15)*zoom,
                              fill="#18343f", outline=color, width=2, tags="power")
                c.create_text(px*zoom, py*zoom, text=symbol, fill=color, font=(self.font, 15, "bold"), tags="power")
            self.last_power = town.power_up
        if self.map_visible and now-self.last_map_update >= .1:
            x1, y1 = self.map_point(self.camera.x, self.camera.y)
            x2, y2 = self.map_point(self.camera.x+self.camera.visible_width, self.camera.y+self.camera.visible_height)
            self.minimap.coords(self.map_view, x1, y1, min(240, x2), min(170, y2))
            mx, my = self.map_point(x, y)
            self.minimap.coords(self.map_player, mx-3, my-3, mx+3, my+3)
            self.last_map_update = now
        if now-self.last_navigation_update >= .1:
            self.update_navigation()
            self.last_navigation_update = now
        if getattr(c, "native_world", False):
            c.present()

    def update_player(self, body_colors, hair_colors, costumes, moving):
        town, c, zoom = self.game.town, self.canvas, self.zoom
        style = (tuple(town.profile.items()), town.vehicle, town.facing)
        if style != self.player_style:
            c.delete("player")
            if town.vehicle:
                if town.vehicle == "van":
                    c.create_oval(-31, -10, 33, 16, fill="#7f887d", outline="", tags="player")
                    c.create_polygon(-30, -18, 20, -18, 31, -8, 31, 11, -30, 11,
                                     fill="#b8c9b5", outline="#56746c", width=1, tags="player")
                    c.create_rectangle(-27, -14, -7, 8, fill="#e7e5cb", outline="#90a48f", tags="player")
                    c.create_rectangle(12, -13, 22, -5, fill="#94c1d0", outline="", tags="player")
                    c.create_text(-18, 1, text="FT", fill="#48675d", font=(self.font, 6, "bold"), tags="player")
                    for wx in (-22, 22):
                        c.create_oval(wx-4, 7, wx+4, 15, fill="#354a4d", outline="", tags="player")
                else:
                    c.create_oval(-24, -7, 25, 13, fill="#7f887d", outline="", tags="player")
                    c.create_polygon(-24, -7, -16, -16, 17, -16, 25, -7, 25, 8, -24, 8,
                                     smooth=True, fill="#87a8b1" if town.vehicle == "car" else "#ad6a5c", tags="player")
            vehicle_items = len(c.find_withtag("player"))
            draw_character(c, town.profile, body_colors, hair_colors, costumes, 0, 0,
                           facing=town.facing, tag="player")
            self.player_parts = c.find_withtag("player")[vehicle_items:]
            c.scale("player", 0, 0, zoom, zoom)
            self.player_style = style
            self.player_position = (0, 0)
            self.player_stride = None
        x, y = round(town.x*zoom), round(town.y*zoom)
        old_x, old_y = self.player_position
        if (x, y) != (old_x, old_y):
            c.move("player", x-old_x, y-old_y)
            self.player_position = (x, y)
        stride = round(math.sin(town.elapsed*13)*3*zoom, 1) if moving else 0
        if stride != self.player_stride:
            for side, leg, foot in ((-1, 1, 2), (1, 3, 4)):
                foot_y = y+10*zoom+side*stride
                c.coords(self.player_parts[leg], x+side*4*zoom, y+2*zoom, x+side*5*zoom, foot_y)
                c.coords(self.player_parts[foot], x+(side*5-3)*zoom, foot_y-zoom,
                         x+(side*5+4)*zoom, foot_y+3*zoom)
            c.coords(self.player_parts[6], x-10*zoom, y-4*zoom, x-13*zoom, y+3*zoom-stride*.4)
            c.coords(self.player_parts[7], x+10*zoom, y-4*zoom, x+13*zoom, y+3*zoom+stride*.4)
            self.player_stride = stride
