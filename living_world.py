"""Scrollable world, retained ambient actors and a small navigation map."""
from dataclasses import dataclass
import math
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from types import SimpleNamespace

from lisbon_scene import LisbonScene, WORLD_WIDTH, WORLD_BOTTOM, RIVER_TOP, RIVER_BOTTOM, draw_character

WORLD_TOP = 104


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
        self.canvas = tk.Canvas(game.canvas, bg="#284a56", highlightthickness=0, borderwidth=0)
        self.zoom = 1.25
        self.camera = Camera(1, 1, self.zoom)
        self.night = False
        self.actors_enabled = True
        self.labels = {}
        self.last_labels = 0
        self.last_time = time.monotonic()
        self.fps = 0.0
        self.fps_started = self.last_time
        self.fps_frames = 0
        self.last_scroll = None
        self.map_visible = True
        self.shown = True
        self.bounds = (1, 1, 0)
        self.font = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
        self.minimap = tk.Canvas(self.canvas, width=184, height=136, highlightthickness=1,
                                 highlightbackground="#9cae99", bg="#18343f")
        self.notification = tk.Label(self.canvas, bg="#18343f", fg="#f4d18c", font=(self.font, 10, "bold"),
                                      padx=14, pady=8, justify="center")
        self.notification_text = ""
        self.build_minimap()
        self.load_scene()

    def label(self, x, y, value, size=10, color="#f8f4df", bold=False, anchor="w", tag="city"):
        return self.canvas.create_text(x, y, text=value, fill=color, anchor=anchor,
                                       font=(self.font, max(7, round(size*self.zoom)), "bold" if bold else "normal"), tags=tag)

    def load_scene(self):
        c = self.canvas
        c.delete("all")
        directory = Path(__file__).parent/"assets"
        self.day_image = tk.PhotoImage(file=str(directory/f"world_{round(self.zoom*100)}_day.png"))
        self.night_image = tk.PhotoImage(file=str(directory/f"world_{round(self.zoom*100)}_night.png"))
        self.background = c.create_image(0, 0, image=self.day_image, anchor="nw")
        c.configure(scrollregion=(0, WORLD_TOP*self.zoom, WORLD_WIDTH*self.zoom, WORLD_BOTTOM*self.zoom))
        proxy = SimpleNamespace(canvas=c, scale_x=self.zoom, display_scale=self.zoom, label=self.label)
        self.scene = LisbonScene(proxy, self.sites, draw=False)
        self.scene.create_tram()
        c.scale("tram", 0, 0, self.zoom, self.zoom)
        self.actors = []
        self.light_items = []
        self.create_actors()
        self.labels = {}
        self.selection = c.create_rectangle(0, 0, 1, 1, outline="#f4cc79", width=2, state="hidden")
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
        for start, end, speed in (((400, 780), (900, 780), 32), ((1240, 802), (WORLD_WIDTH-220, 802), 62),
                                  ((1300, 860), (WORLD_WIDTH-150, 860), 38), ((430, 835), (870, 835), 20)):
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
        self.canvas.itemconfigure(self.background, image=self.night_image if enabled else self.day_image)
        self.scene.set_night(enabled)
        for item in self.light_items:
            self.canvas.itemconfigure(item, fill="#f5dca0" if enabled else "#aac5c8")
        self.last_labels = 0

    def resize(self, width, height, top):
        self.camera.width, self.camera.height = max(1, width), max(1, height)
        self.bounds = width, height, top
        if self.shown:
            self.canvas.place(x=0, y=top, width=width, height=height)
        self.notification.configure(wraplength=max(260, width-430))
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
        c.create_rectangle(8, 24, 176, 128, fill="#9aa994", width=0)
        def point(x, y):
            return 8+x/WORLD_WIDTH*168, 24+(y-WORLD_TOP)/(WORLD_BOTTOM-WORLD_TOP)*104
        self.map_point = point
        c.create_rectangle(*point(0, RIVER_TOP), *point(WORLD_WIDTH, RIVER_BOTTOM), fill="#608f9a", width=0)
        for site in self.sites:
            x, y = point(site.x+88, site.y+52)
            c.create_rectangle(x-1, y-1, x+2, y+2, fill="#e2cf9a", width=0)
        self.map_view = c.create_rectangle(0, 0, 1, 1, outline="#f8eee0", width=1)
        self.map_player = c.create_oval(0, 0, 1, 1, fill="#f2c15f", outline="#263f4a", width=1)

    def update_labels(self, elapsed):
        color = "#f3e3bb" if self.night else "#385360"
        for site in self.sites:
            visible = self.camera.sees(site.x+88, site.y+100, 140)
            text = self.game.town.site_status(site)
            item = self.labels.get(site.name)
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
        now = time.monotonic()
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
            c.xview_moveto(self.camera.x/WORLD_WIDTH)
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
                c.move(actor.tag, (x-actor.drawn_x)*zoom, (y-actor.drawn_y)*zoom)
                actor.drawn_x, actor.drawn_y = x, y
        self.scene.animate(town.elapsed)
        near = town.nearby()
        if near:
            x1, y1, x2, y2 = near.bounds
            c.coords(self.selection, (x1-2)*zoom, (y1-2)*zoom, (x2+2)*zoom, (y2+2)*zoom)
            c.itemconfigure(self.selection, state="normal")
        else:
            c.itemconfigure(self.selection, state="hidden")
        if now-self.last_labels >= .12:
            self.update_labels(town.elapsed)
            order = town.industry_orders["SHIPYARD"]
            active = order is not None and town.elapsed < order.ready_at and int(town.elapsed*8) % 2 == 0
            c.itemconfigure(self.spark, state="normal" if active else "hidden")
            self.last_labels = now
        c.delete("player")
        x, y = town.x, town.y
        if town.vehicle:
            c.create_oval(x-24, y-7, x+25, y+13, fill="#7f887d", outline="", tags="player")
            c.create_polygon(x-24, y-7, x-16, y-16, x+17, y-16, x+25, y-7, x+25, y+8, x-24, y+8,
                             smooth=True, fill="#87a8b1" if town.vehicle == "car" else "#ad6a5c", tags="player")
        moving = bool(self.game.keys.intersection({"w", "a", "s", "d", "up", "down", "left", "right"}))
        draw_character(c, town.profile, body_colors, hair_colors, costumes, x, y, town.elapsed, moving, town.facing, tag="player")
        c.scale("player", 0, 0, zoom, zoom)
        if town.power_up is not None:
            name, symbol, color, px, py = self.game.power_up_definitions[town.power_up]
            c.delete("power")
            c.create_oval((px-15)*zoom, (py-15)*zoom, (px+15)*zoom, (py+15)*zoom,
                          fill="#18343f", outline=color, width=2, tags="power")
            c.create_text(px*zoom, py*zoom, text=symbol, fill=color, font=(self.font, 15, "bold"), tags="power")
        else:
            c.delete("power")
        if self.map_visible:
            x1, y1 = self.map_point(self.camera.x, self.camera.y)
            x2, y2 = self.map_point(self.camera.x+self.camera.visible_width, self.camera.y+self.camera.visible_height)
            self.minimap.coords(self.map_view, x1, y1, min(176, x2), min(128, y2))
            mx, my = self.map_point(x, y)
            self.minimap.coords(self.map_player, mx-3, my-3, mx+3, my+3)
