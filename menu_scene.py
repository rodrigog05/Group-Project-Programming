"""Animated Lisbon backdrop for the start menu.

The view looks west along the Tejo towards the 25 de Abril bridge: Almada and
Cristo Rei on the left, Alcântara and Alfama's hills on the right. Traffic
crosses the bridge, boats sail the river, and a slow day/night cycle lights
up windows and bridge lamps in the game's flat, pastel style.
"""
import math
import random
import time

FRAME_MS = 33
CYCLE_SECONDS = 60
START_POSITION = .30  # Open in daylight, a few seconds before sunset.

SKY = {"day": ("#8cc4d8", "#f4e6c4"), "dusk": ("#5a6aa0", "#f3a577"), "night": ("#0f1830", "#2e3d60")}
WATER = {"day": ("#78b9c6", "#3b8197"), "dusk": ("#8d93ad", "#3f5a7c"), "night": ("#22385a", "#0e1b31")}
# Cycle position, palette and darkness. Dawn reuses the dusk palette.
KEYFRAMES = ((0.0, "day", 0.0), (0.42, "day", 0.0), (0.52, "dusk", .35), (0.62, "night", 1.0),
             (0.88, "night", 1.0), (0.95, "dusk", .35), (1.0, "day", 0.0))
NIGHT_TINT = "#17223f"
INK, GOLD, MINT, WHITE = "#101f28", "#ffc66c", "#6de0b3", "#f2f7f6"
BRIDGE_RED, BRIDGE_DARK = "#c4442f", "#8e2d20"
WALLS = ("#f2e3c6", "#e9c4b6", "#c9dbe0", "#f1d58e", "#e8b7a0", "#d9e2c4", "#f5efe2")
ROOFS = ("#c8693f", "#b85a36", "#d47a4e")
CAR_COLORS = ("#d65655", "#86caff", "#ffc66c", "#80dab9", "#bea0ec", "#e6e9df", "#9b584e")


def hex_rgb(color):
    return tuple(int(color[index:index+2], 16) for index in (1, 3, 5))


def mix(first, second, amount):
    amount = min(1, max(0, amount))
    return "#" + "".join(f"{round(a+(b-a)*amount):02x}" for a, b in zip(hex_rgb(first), hex_rgb(second)))


def sky_state(position):
    """Sky top, sky bottom, water top, water bottom and darkness at a cycle position."""
    position %= 1
    for (start, first, dark_start), (end, second, dark_end) in zip(KEYFRAMES, KEYFRAMES[1:]):
        if start <= position <= end:
            amount = (position-start)/(end-start) if end > start else 0
            sky = [mix(a, b, amount) for a, b in zip(SKY[first], SKY[second])]
            water = [mix(a, b, amount) for a, b in zip(WATER[first], WATER[second])]
            return (*sky, *water, dark_start+(dark_end-dark_start)*amount)
    return (*SKY["day"], *WATER["day"], 0.0)


def smooth_profile(points, x):
    """Height of a hill outline at x, eased between its control points."""
    if x <= points[0][0]:
        return points[0][1]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 <= x <= x2:
            amount = (x-x1)/(x2-x1)
            amount = amount*amount*(3-2*amount)
            return y1+(y2-y1)*amount
    return points[-1][1]


class LisbonMenuScene:
    def __init__(self, canvas, font, on_layout=None):
        self.canvas = canvas
        self.font = font
        self.on_layout = on_layout
        self.timer = None
        self.size = None
        self.started = time.perf_counter()
        self.movers = []

    # ----- Lifecycle -----

    def start(self):
        self.canvas.bind("<Configure>", self.resize)
        self.tick()

    def stop(self):
        if self.timer is not None:
            self.canvas.after_cancel(self.timer)
            self.timer = None
        if self.canvas.winfo_exists():
            self.canvas.unbind("<Configure>")

    def resize(self, event):
        if event.width > 50 and event.height > 50 and (event.width, event.height) != self.size:
            self.build(event.width, event.height)

    def tick(self):
        if self.size is not None:
            self.animate(time.perf_counter()-self.started)
        self.timer = self.canvas.after(FRAME_MS, self.tick)

    # ----- Drawing helpers -----

    def shape(self, kind, coords, color, tint=True, tags=(), **options):
        """Create a scene item. Tinted items darken towards blue at night."""
        if kind != "line":
            options.setdefault("outline", "")
        item = getattr(self.canvas, f"create_{kind}")(*coords, fill=color, tags=("scene", *tags), **options)
        if tint:
            self.tinted.append((item, color))
        return item

    def rect(self, x1, y1, x2, y2, color, **options):
        return self.shape("rectangle", (x1, y1, x2, y2), color, **options)

    def oval(self, x1, y1, x2, y2, color, **options):
        return self.shape("oval", (x1, y1, x2, y2), color, **options)

    def poly(self, points, color, **options):
        return self.shape("polygon", points, color, **options)

    def line(self, points, color, **options):
        return self.shape("line", points, color, **options)

    def light(self, x, y, radius, color="#ffe4a0", tags=()):
        """A lamp that only shows at night."""
        item = self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=color, width=0,
                                       state="hidden", tags=("scene", *tags))
        self.lights.append(item)
        return item

    # ----- Scene -----

    def card_top(self, card_height):
        """Where the menu card goes: on the river, below the bridge."""
        width, height = self.size
        return max(self.water_y+height*.03, min(height*.60, height-card_height-height*.03))

    def build(self, width, height):
        c = self.canvas
        c.delete("scene")
        self.size = (width, height)
        self.tinted, self.windows, self.lights, self.stars, self.movers = [], [], [], [], []
        self.offsets = {}  # Current (x, y) shift of every moving tag
        self.last_dark = None
        rng = random.Random(1974)
        w, h = width, height
        self.water_y = water_y = h*.56
        self.deck_y = deck_y = h*.395
        self.tower_top = h*.15
        self.span = (w*.05, w*.25, w*.67, w*.88)  # anchorage, towers, anchorage

        # Sky, stars, sun and moon
        self.sky_bands = [c.create_rectangle(0, water_y*i/24, w, water_y*(i+1)/24+1, width=0, tags="scene")
                          for i in range(24)]
        for _ in range(70):
            x, y, size = rng.uniform(0, w), rng.uniform(0, water_y*.75), rng.choice((1, 1, 1.5, 2))
            self.stars.append(c.create_oval(x-size, y-size, x+size, y+size, fill="#f4f1dc", width=0,
                                            state="hidden", tags="scene"))
        sun = h*.045
        self.sun_glow = c.create_oval(-sun*1.8, -sun*1.8, sun*1.8, sun*1.8, width=0, tags="scene")
        self.sun = c.create_oval(-sun, -sun, sun, sun, width=0, tags="scene")
        moon = h*.03
        self.moon = c.create_oval(-moon, -moon, moon, moon, fill="#f3efe0", width=0, state="hidden", tags="scene")
        self.moon_shadow = c.create_oval(-moon*.3, -moon*.5, moon*.15, -moon*.05, fill="#dcd6c2", width=0,
                                         state="hidden", tags="scene")
        # The river covers the sun as it sinks below the horizon.
        self.water_bands = [c.create_rectangle(0, water_y+(h-water_y)*i/12, w, water_y+(h-water_y)*(i+1)/12+1,
                                               width=0, tags="scene") for i in range(12)]

        # Clouds and distant hills
        for index in range(6):
            x, y, size = rng.uniform(0, w), rng.uniform(h*.12, h*.34), rng.uniform(.7, 1.3)*h*.03
            tag = f"cloud{index}"
            for dx, dy, radius in ((0, 0, 1), (1.1, .25, .8), (-1.1, .3, .75), (.5, -.35, .7)):
                self.oval(x+dx*size-radius*size, y+dy*size-radius*size*.7, x+dx*size+radius*size,
                          y+dy*size+radius*size*.7, "#fbf6ea", tags=(tag,))
            self.oval(x-size*1.9, y-size*.05, x+size*1.9, y+size*.6, "#fbf6ea", tags=(tag,))
            self.movers.append(("cloud", tag, x, rng.uniform(4, 10)*w/1000, size*4))
        # Distant rolling hills, smoothed so they read as Monsanto's slopes rather than a plateau.
        ridge = [(0, water_y)] + [(w*i/24, water_y-h*(.045+.02*math.sin(i*.9+1)+.012*math.sin(i*2.3)))
                                  for i in range(25)] + [(w, water_y)]
        self.poly([value for point in ridge for value in point], "#a7c2b6", smooth=True)

        self.draw_bridge(w, h, rng)
        self.draw_almada(w, h, rng)
        self.draw_lisbon(w, h, rng)
        self.draw_river(w, h, rng)
        self.draw_boats(w, h, rng)

        # Gulls
        for index in range(5):
            tag = f"gull{index}"
            x, y = rng.uniform(0, w), rng.uniform(h*.18, h*.36)
            self.line((x-8, y, x-3, y-4, x, y, x+3, y-4, x+8, y), "#2f3d45", tags=(tag,), width=2)
            self.movers.append(("gull", tag, x, rng.uniform(25, 45)*w/1000, y))

        self.draw_title(w, h)
        self.animate(time.perf_counter()-self.started, force=True)
        if self.on_layout is not None:
            self.on_layout(w, h)

    def draw_bridge(self, w, h, rng):
        anchor_left, tower_left, tower_right, anchor_right = self.span
        deck_y, top, water_y = self.deck_y, self.tower_top, self.water_y
        sag_y = deck_y-h*.012

        def cable_y(x):
            if x <= tower_left:
                amount = (x-anchor_left)/(tower_left-anchor_left)
                return deck_y+(top-deck_y)*amount-h*.025*math.sin(math.pi*amount)
            if x >= tower_right:
                amount = (anchor_right-x)/(anchor_right-tower_right)
                return deck_y+(top-deck_y)*amount-h*.025*math.sin(math.pi*amount)
            middle = (tower_left+tower_right)/2
            amount = ((x-middle)/((tower_right-tower_left)/2))**2
            return sag_y+(top-sag_y)*amount

        # Hangers, then the main cable over them
        step = w/110
        x = anchor_left+step
        while x < anchor_right:
            if abs(x-tower_left) > step/2 and abs(x-tower_right) > step/2:
                self.line((x, cable_y(x), x, deck_y), "#b9483a", width=1)
            x += step
        points = []
        x = anchor_left
        while x <= anchor_right:
            points += [x, cable_y(x)]
            x += w/200
        self.line(points, BRIDGE_DARK, width=3, smooth=True)

        # Deck: road on top, the red truss with the railway below
        truss_bottom = deck_y+h*.05
        self.rect(anchor_left, deck_y-h*.004, anchor_right, deck_y+h*.006, "#5e6b70")
        self.rect(anchor_left, deck_y+h*.006, anchor_right, truss_bottom, BRIDGE_RED)
        self.rect(anchor_left, deck_y+h*.026, anchor_right, deck_y+h*.03, BRIDGE_DARK)
        panel = h*.022
        x = anchor_left
        while x < anchor_right:
            self.line((x, deck_y+h*.006, x+panel/2, deck_y+h*.026, x+panel, deck_y+h*.006), BRIDGE_DARK, width=1)
            self.line((x, truss_bottom, x+panel/2, deck_y+h*.03, x+panel, truss_bottom), BRIDGE_DARK, width=1)
            x += panel
        self.train_y = (deck_y+h*.033, truss_bottom-h*.003)

        # Towers: two legs joined by cross beams, standing on concrete piers
        for x in (tower_left, tower_right):
            leg, gap = w*.0065, w*.011
            for left in (x-gap/2-leg, x+gap/2):
                self.poly((left, top, left+leg, top, left+leg*1.2, water_y, left-leg*.2, water_y), BRIDGE_RED)
            for y in (top+h*.01, top+h*.07, top+h*.13, deck_y-h*.03, truss_bottom+h*.01):
                self.rect(x-gap/2, y, x+gap/2, y+h*.008, BRIDGE_RED)
            self.rect(x-gap/2-leg*1.6, water_y-h*.008, x+gap/2+leg*1.6, water_y+h*.012, "#bdb5a2")
            self.light(x, top-h*.006, 3, "#ff6a5a")

        # Bridge lamps and the cars on the deck
        x = anchor_left+w*.02
        while x < anchor_right:
            self.light(x, deck_y-h*.012, 2)
            x += w*.03
        car_w, car_h = w*.014, h*.012
        for index in range(12):
            tag = f"car{index}"
            direction = 1 if index % 2 == 0 else -1
            color = CAR_COLORS[index % len(CAR_COLORS)]
            self.poly((0, car_h*.45, car_w*.18, 0, car_w*.82, 0, car_w, car_h*.45, car_w, car_h, 0, car_h),
                      color, tags=(tag,))
            self.rect(car_w*.25, car_h*.12, car_w*.75, car_h*.45, "#aac5c8", tags=(tag,))
            lamp_x = car_w if direction > 0 else 0
            self.light(lamp_x, car_h*.6, 2, tags=(tag,))
            self.canvas.move(tag, 0, deck_y-h*.004-car_h)
            offset = index/12
            self.movers.append(("car", tag, 0, direction, offset, rng.uniform(.045, .07)))

        # A commuter train crosses on the lower deck now and then
        self.train_cars = []
        top_y, bottom_y = self.train_y
        for index in range(4):
            tag = f"train{index}"
            self.rect(0, top_y, w*.03, bottom_y, "#d9dfe2", tags=(tag, "train"))
            self.rect(w*.003, top_y+(bottom_y-top_y)*.2, w*.027, top_y+(bottom_y-top_y)*.55, "#2f4b5a",
                      tags=(tag, "train"))
            self.train_cars.append(tag)

    def draw_almada(self, w, h, rng):
        water_y = self.water_y
        hill = ((0, h*.30), (w*.04, h*.285), (w*.09, h*.30), (w*.14, h*.36), (w*.19, h*.46),
                (w*.23, h*.53), (w*.27, water_y))
        self.poly([value for point in ((0, water_y),) + hill for value in point], "#b7c08a")
        self.poly([0, h*.36, w*.05, h*.34, w*.12, h*.40, w*.2, h*.50, w*.24, water_y, 0, water_y], "#a3b07a")
        for index in range(14):
            x = rng.uniform(w*.01, w*.22)
            y = max(smooth_profile(hill, x)+h*.02, rng.uniform(h*.40, water_y-h*.01))
            radius = h*.011
            self.oval(x-radius, y-radius, x+radius, y+radius, "#6f9f7a")
        for x in (w*.15, w*.18, w*.205):
            y = smooth_profile(hill, x)+h*.03
            self.house(x, y, w*.018, h*.03, rng)

        # Cristo Rei on its pedestal above the river
        x, base = w*.06, smooth_profile(hill, w*.06)
        stone, statue = "#e9e3d3", "#f1ece0"
        self.poly((x-w*.018, base, x+w*.018, base, x+w*.011, base-h*.1, x-w*.011, base-h*.1), stone)
        self.rect(x-w*.004, base-h*.075, x+w*.004, base, "#8f8a7c")
        self.rect(x-w*.014, base-h*.104, x+w*.014, base-h*.098, stone)
        self.rect(x-w*.0035, base-h*.155, x+w*.0035, base-h*.104, statue)
        self.rect(x-w*.016, base-h*.148, x+w*.016, base-h*.141, statue)
        self.oval(x-w*.003, base-h*.168, x+w*.003, base-h*.155, statue)
        self.light(x, base-h*.10, 3, "#fff0c4")

    def draw_lisbon(self, w, h, rng):
        water_y = self.water_y
        # The city starts just east of the bridge's north tower, which stands in the river.
        outline = ((w*.70, water_y), (w*.74, h*.50), (w*.79, h*.45), (w*.84, h*.41), (w*.88, h*.385),
                   (w*.93, h*.30), (w*.97, h*.32), (w*1.01, h*.35))
        self.poly([value for point in outline + ((w, water_y),) for value in point], "#d8cfa8")

        # Castelo de São Jorge on the highest hill
        x, base = w*.93, h*.31
        stone, shade = "#d9c9a0", "#bfae86"
        self.rect(x-w*.045, base-h*.035, x+w*.045, base+h*.01, stone)
        for offset in range(-44, 45, 8):
            self.rect(x+w*offset/1000, base-h*.043, x+w*(offset+4)/1000, base-h*.035, stone)
        for offset, tall in ((-.04, .06), (0, .075), (.038, .055)):
            left = x+w*offset-w*.008
            self.rect(left, base-h*tall, left+w*.016, base, shade)
            for notch in range(3):
                self.rect(left+notch*w*.006, base-h*tall-h*.007, left+notch*w*.006+w*.004, base-h*tall, shade)
        self.line((x+w*.0, base-h*.082, x, base-h*.11), "#5b4b3a", width=2)
        self.rect(x, base-h*.11, x+w*.006, base-h*.098, "#2e8b57")
        self.rect(x+w*.006, base-h*.11, x+w*.014, base-h*.098, "#d33a35")

        # Houses climbing the hills, farthest first
        houses = []
        x = w*.705
        while x < w:
            house_w = rng.uniform(.02, .028)*w
            top = smooth_profile(outline, x+house_w/2)+h*.012
            y = water_y-h*.014
            while y-h*.03 > top:
                house_h = rng.uniform(.03, .042)*h
                houses.append((y, x, house_w, house_h))
                y -= house_h*.82
            x += house_w*.92
        for y, x, house_w, house_h in sorted(houses):
            self.house(x+house_w/2, y, house_w, house_h, rng)

        # Waterfront promenade with trees and the yellow tram
        self.rect(w*.70, water_y-h*.014, w, water_y, "#e8dcc0")
        self.line((w*.70, water_y-h*.004, w, water_y-h*.004), "#9c9483", width=1)
        for index in range(7):
            tx = w*.72+index*w*.045
            self.oval(tx-h*.01, water_y-h*.032, tx+h*.01, water_y-h*.012, "#6f9f7a")
            self.light(tx+w*.012, water_y-h*.02, 2)
        tram_w, tram_h = w*.035, h*.022
        top = water_y-h*.006-tram_h
        self.rect(0, top, tram_w, top+tram_h, "#f2c230", tags=("tram",))
        self.rect(0, top+tram_h*.78, tram_w, top+tram_h, "#c9472f", tags=("tram",))
        self.rect(tram_w*.08, top-tram_h*.12, tram_w*.92, top, "#f5efe2", tags=("tram",))
        for index in range(4):
            left = tram_w*(.1+index*.21)
            window = self.rect(left, top+tram_h*.18, left+tram_w*.15, top+tram_h*.55, "#2f4b5a", tint=False,
                               tags=("tram",))
            self.windows.append((window, True))
        self.line((tram_w*.5, top-tram_h*.12, tram_w*.62, top-tram_h*.6), "#3a3a3a", width=1, tags=("tram",))
        self.movers.append(("tram", "tram", 0, w*.70, w-tram_w, w*.04))

    def house(self, center_x, bottom, width, height, rng):
        left, right, top = center_x-width/2, center_x+width/2, bottom-height
        self.rect(left, top, right, bottom, rng.choice(WALLS))
        roof = rng.choice(ROOFS)
        self.poly((left-width*.06, top, center_x, top-height*.32, right+width*.06, top), roof)
        for column in (.22, .58) if width > 20 else (.4,):
            window = self.rect(left+width*column, top+height*.22, left+width*(column+.2), top+height*.52,
                               "#2f4b5a", tint=False)
            self.windows.append((window, rng.random() < .65))

    def draw_river(self, w, h, rng):
        water_y = self.water_y
        # Light on the water drifts slowly with the current
        for index in range(46):
            depth = rng.random()
            y = water_y+h*.008+(h-water_y)*depth**1.4
            length = w*(.01+.03*depth)
            x = rng.uniform(0, w)
            tag = f"shimmer{index}"
            self.line((x, y, x+length, y), "#d6ecef", tags=(tag,), width=1 if depth < .5 else 2)
            self.movers.append(("shimmer", tag, x, rng.uniform(4, 14)*w/1000*(1 if index % 3 else -1), length))

    def draw_boats(self, w, h, rng):
        water_y = self.water_y
        boats = (("sail", .03, 1), ("ferry", .09, -1), ("sail", .16, -1), ("ferry", .27, 1), ("sail", .36, 1))
        for index, (kind, depth, direction) in enumerate(boats):
            y = water_y+(h-water_y)*depth
            scale = h*(.0007+depth*.004)
            tag = f"boat{index}"
            if kind == "sail":
                self.poly((-14*scale, 0, 14*scale, 0, 10*scale, 5*scale, -10*scale, 5*scale), "#f5efe2",
                          tags=(tag,))
                self.line((0, 0, 0, -26*scale), "#5b4b3a", tags=(tag,), width=1)
                self.poly((1*scale, -25*scale, 1*scale, -2*scale, 13*scale*direction, -2*scale), "#fbf6ea",
                          tags=(tag,))
                self.light(0, -27*scale, 2, "#ff6a5a", tags=(tag,))
            else:
                self.poly((-22*scale, -2*scale, 22*scale, -2*scale, 18*scale, 6*scale, -18*scale, 6*scale),
                          "#e07a2e", tags=(tag,))
                self.rect(-15*scale, -9*scale, 13*scale, -2*scale, "#f5efe2", tags=(tag,))
                for window in range(5):
                    item = self.rect((-13+window*5.4)*scale, -7*scale, (-10+window*5.4)*scale, -4*scale,
                                     "#2f4b5a", tint=False, tags=(tag,))
                    self.windows.append((item, True))
                self.rect(2*scale, -15*scale, 6*scale, -9*scale, "#2f3d45", tags=(tag,))
            x = rng.uniform(0, w)
            self.canvas.move(tag, x, y)
            self.offsets[tag] = (x, y)
            speed = (8+depth*60)*w/1000*direction
            self.movers.append(("boat", tag, x, speed, 30*scale, y))

    def draw_title(self, w, h):
        plaque_w, plaque_h = max(w*.32, 380), h*.115
        left, top = w/2-plaque_w/2, h*.02
        self.canvas.create_rectangle(left+4, top+4, left+plaque_w+4, top+plaque_h+4, fill="#0a141b", width=0,
                                     tags="scene")
        self.canvas.create_rectangle(left, top, left+plaque_w, top+plaque_h, fill=INK, outline=GOLD, width=2,
                                     tags="scene")
        size = max(22, round(h*.042))
        self.canvas.create_text(w/2, top+plaque_h*.42, text="FOUNDRY TOWN", fill=GOLD,
                                font=(self.font, -size, "bold"), tags="scene")
        self.canvas.create_text(w/2, top+plaque_h*.78, text="LISBOA  ·  Build your fortune along the Tejo",
                                fill=MINT, font=(self.font, -max(12, round(h*.016)), "bold"), tags="scene")

    # ----- Animation -----

    def animate(self, elapsed, force=False):
        c = self.canvas
        w, h = self.size
        position = (START_POSITION+elapsed/CYCLE_SECONDS) % 1
        sky_top, sky_bottom, water_top, water_bottom, dark = sky_state(position)
        for index, band in enumerate(self.sky_bands):
            c.itemconfigure(band, fill=mix(sky_top, sky_bottom, index/(len(self.sky_bands)-1)))
        for index, band in enumerate(self.water_bands):
            c.itemconfigure(band, fill=mix(water_top, water_bottom, index/(len(self.water_bands)-1)))

        # The sun sets behind the bridge; the moon rises over Alfama.
        sun_progress = min(1, position/.56)
        sun_x, sun_y = w*.46, h*.17+(self.water_y-h*.15)*sun_progress**2
        radius = h*.045
        sun_color = mix("#ffe08a", "#ff8f52", sun_progress)
        c.coords(self.sun, sun_x-radius, sun_y-radius, sun_x+radius, sun_y+radius)
        c.coords(self.sun_glow, sun_x-radius*1.8, sun_y-radius*1.8, sun_x+radius*1.8, sun_y+radius*1.8)
        c.itemconfigure(self.sun, fill=sun_color, state="normal" if position < .6 else "hidden")
        c.itemconfigure(self.sun_glow, fill=mix(sky_bottom, sun_color, .35), state="normal" if position < .6 else "hidden")
        moon_progress = (position-.58)/.36
        night_sky = 0 < moon_progress < 1
        moon_x, moon_y = w*.78, self.water_y-(self.water_y-h*.2)*math.sin(math.pi*min(1, max(0, moon_progress)))
        radius = h*.03
        c.coords(self.moon, moon_x-radius, moon_y-radius, moon_x+radius, moon_y+radius)
        c.coords(self.moon_shadow, moon_x-radius*.3, moon_y-radius*.5, moon_x+radius*.15, moon_y-radius*.05)
        for item in (self.moon, self.moon_shadow):
            c.itemconfigure(item, state="normal" if night_sky else "hidden")
        for item in self.stars:
            c.itemconfigure(item, state="normal" if dark > .6 else "hidden")

        if force or self.last_dark is None or abs(dark-self.last_dark) > .03:
            self.last_dark = dark
            for item, color in self.tinted:
                c.itemconfigure(item, fill=mix(color, NIGHT_TINT, dark*.6))
            for item, lit in self.windows:
                c.itemconfigure(item, fill="#ffd682" if lit and dark > .5 else mix("#2f4b5a", NIGHT_TINT, dark*.6))
            for item in self.lights:
                c.itemconfigure(item, state="normal" if dark > .5 else "hidden")

        self.move_actors(elapsed)

    def place(self, tag, x, y=None):
        """Move a tagged group so its own origin sits at (x, y)."""
        old_x, old_y = self.offsets.get(tag, (0, 0))
        y = old_y if y is None else y
        if x != old_x or y != old_y:
            self.canvas.move(tag, x-old_x, y-old_y)
            self.offsets[tag] = (x, y)

    def move_actors(self, elapsed):
        c = self.canvas
        w, h = self.size
        anchor_left, _, _, anchor_right = self.span
        span = anchor_right-anchor_left
        for index, mover in enumerate(self.movers):
            kind, tag = mover[0], mover[1]
            if kind in ("cloud", "shimmer"):
                _, _, x, speed, length = mover
                # Shapes were drawn at x, so their shift is measured from there.
                self.place(tag, (x+elapsed*speed) % (w+length*2)-length-x)
            elif kind == "gull":
                _, _, x, speed, y = mover
                target = (x+elapsed*speed) % (w+40)-20
                flap = 4*math.sin(elapsed*9+index)
                bob = 6*math.sin(elapsed*.8+index)
                c.coords(tag, target-8, y+bob, target-3, y+bob-flap, target, y+bob,
                         target+3, y+bob-flap, target+8, y+bob)
            elif kind == "car":
                _, _, _, direction, offset, speed = mover
                progress = (offset+elapsed*speed) % 1
                self.place(tag, anchor_left+span*(progress if direction > 0 else 1-progress))
            elif kind == "boat":
                _, _, x, speed, half, y = mover
                target = (x+elapsed*speed) % (w+half*4)-half*2
                self.place(tag, target, y+math.sin(elapsed*1.6+index)*h*.002)
            elif kind == "tram":
                _, _, _, start, end, speed = mover
                distance = (elapsed*speed) % ((end-start)*2)
                self.place(tag, start+(distance if distance <= end-start else (end-start)*2-distance))
        # Train: crosses the lower deck, then waits out of sight.
        cycle = (elapsed % 16)/16
        lead = anchor_left-w*.13+(span+w*.26)*min(1, cycle/.7)
        for index, tag in enumerate(self.train_cars):
            x = lead-index*w*.032
            self.place(tag, x)
            visible = anchor_left <= x and x+w*.03 <= anchor_right
            c.itemconfigure(tag, state="normal" if visible else "hidden")
