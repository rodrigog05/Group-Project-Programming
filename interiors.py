"""Illustrated interiors for trading buildings.

Pressing E at a supplier, factory, market or special workshop opens a scene in
the style of the Jerónimos visit: a vendor behind a counter, the goods of the
trade and a chalkboard with live prices. The same keys trade inside, and the
vendor answers with the result. All trading still goes through Town.interact.
"""
import math
import random
import sys
import time
import tkinter as tk

SCENE_W, SCENE_H = 640, 400
INTERIOR_ROLES = ("SUPPLIER", "FACTORY", "PUBLIC SHOP", "PASTELARIA", "SHIPYARD", "TIER2")
FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
IS_MAC = sys.platform == "darwin"
INK, PAPER, CHALK = "#1f2a30", "#fffaf0", "#eef3ea"
OPEN_GRACE_SECONDS = .4  # Ignore the E that opened the scene and its key repeats.


# ----- Text the vendors say -----

def vendor_greeting(town, site):
    from tycoon import EGG_COST, TRADES
    import businesses
    role = site.role
    if role == "SUPPLIER":
        trade = TRADES[site.trade]
        opener = ("Freshly mined", "Cut this morning", "Dug from the pit today", "Harvested at dawn")[site.trade]
        text = f"{opener}! {trade.supply} for ${town.costs[site.trade]} each."
        return text + f" Eggs are ${EGG_COST}." if site.trade == 3 else text
    if role == "PUBLIC SHOP":
        trade = TRADES[town.business_site(site).trade]
        if businesses.is_owned(town, site):
            return f"Welcome back, boss! Shall I put your {trade.product} on the shelves?"
        return f"I buy your {trade.product} for ${town.prices[town.business_site(site).trade]} each!"
    if role == "FACTORY":
        trade = TRADES[town.business_site(site).trade]
        return f"Bring me {trade.supply} and I'll turn it into {trade.product}."
    if role == "PASTELARIA":
        return "Pastéis de nata, fresh from the oven! 1 Wheat + 1 Egg makes one."
    if role == "SHIPYARD":
        return "This boat won't fix itself! Bring 2 Timber + 2 Iron ore and the job is yours."
    if role == "TIER2":
        return "Precision work only! 1 Tools + 1 Furniture makes one Precision Machinery."
    return "Bom dia!"


def scene_trade(town, site):
    """The trade a building currently works in (owned businesses can be retooled)."""
    if site.role in ("FACTORY", "PUBLIC SHOP"):
        return town.business_site(site).trade
    return site.trade


def actions_for(town, site):
    import businesses
    if site.role == "SUPPLIER":
        actions = [("Buy 1  ·  E", "e"), ("Buy 4  ·  Q", "q")]
        if site.trade == 3:
            actions += [("1 Egg  ·  F", "f"), ("4 Eggs  ·  R", "r")]
        return actions
    if site.role == "PUBLIC SHOP":
        return [("Stock shop  ·  E" if businesses.is_owned(town, site) else "Sell  ·  E", "e")]
    if site.role == "FACTORY":
        return [("Drop off / collect  ·  E", "e")]
    if site.role == "PASTELARIA":
        return [("Bake / collect / sell  ·  E", "e")]
    if site.role == "SHIPYARD":
        return [("Start / claim repair  ·  E", "e")]
    return [("Craft / collect / sell  ·  E", "e")]


# ----- Drawing helpers (all in a 640 x 400 scene) -----

class Painter:
    def __init__(self, canvas):
        self.c = canvas
        self.sizes = {}  # text item -> (font size, wrap width) before scaling

    def rect(self, x1, y1, x2, y2, color, **options):
        return self.c.create_rectangle(x1, y1, x2, y2, fill=color, width=options.pop("width", 0), **options)

    def oval(self, x1, y1, x2, y2, color, **options):
        return self.c.create_oval(x1, y1, x2, y2, fill=color, width=options.pop("width", 0), **options)

    def poly(self, points, color, **options):
        return self.c.create_polygon(*points, fill=color, **options)

    def line(self, points, color, width=1, **options):
        return self.c.create_line(*points, fill=color, width=width, **options)

    def text(self, x, y, value, size=10, color=INK, bold=False, anchor="center", wrap=0, **options):
        item = self.c.create_text(x, y, text=value, fill=color, anchor=anchor, width=wrap,
                                  font=(FONT, size, "bold" if bold else "normal"), justify="center", **options)
        self.sizes[item] = (size, wrap, bold)
        return item

    def person(self, x, y, scale, coat, skin, hair):
        """A small diner or shopper in the background crowd."""
        self.poly((x-8*scale, y-30*scale, x+8*scale, y-30*scale, x+11*scale, y, x-11*scale, y), coat)
        self.oval(x-7*scale, y-46*scale, x+7*scale, y-29*scale, skin)
        self.c.create_arc(x-7*scale, y-47*scale, x+7*scale, y-34*scale, start=0, extent=180, fill=hair, outline=hair)


SKINS = ("#e6b98f", "#c78d64", "#8e5f43", "#f0c9a5")
HAIRS = ("#3b2f2a", "#6b4a32", "#c9b9a0", "#1f1b1a", "#a8642f")
COATS = ("#657b80", "#866653", "#6d6380", "#74794f", "#a35a4f", "#4f6a8a")


def vendor(p, x, counter_y, look):
    """A vendor standing behind the counter: upper body, smiling, arms on the counter."""
    skin, hair, shirt = look["skin"], look["hair"], look["shirt"]
    top = counter_y-118
    p.poly((x-36, top+58, x+36, top+58, x+46, counter_y, x-46, counter_y), shirt, outline="#2a2a2a", width=2)
    if look.get("apron"):
        p.poly((x-22, top+66, x+22, top+66, x+28, counter_y, x-28, counter_y), look["apron"])
        p.line((x-22, top+66, x-30, top+56), look["apron"], 3)
        p.line((x+22, top+66, x+30, top+56), look["apron"], 3)
    if look.get("plaid"):
        for offset in range(-36, 40, 12):
            p.line((x+offset, top+60, x+offset*1.25, counter_y), "#2a2020", 2)
        for row in range(top+70, counter_y, 12):
            p.line((x-40, row, x+40, row), "#2a2020", 1)
    p.oval(x-24, top+2, x+24, top+56, skin, outline="#2a2a2a", width=2)
    hat = look.get("hat")
    if hat != "chef" and hat != "helmet" and hat != "straw" and hat != "cap":
        p.c.create_arc(x-25, top-2, x+25, top+38, start=0, extent=180, fill=hair, outline=hair)
    if look.get("beard"):
        p.c.create_arc(x-22, top+22, x+22, top+62, start=180, extent=180, fill=hair, outline=hair)
    p.line((x-10, top+26, x-6, top+26), "#2a2a2a", 3)
    p.line((x+6, top+26, x+10, top+26), "#2a2a2a", 3)
    p.c.create_arc(x-10, top+30, x+10, top+44, start=200, extent=140, style="arc", outline="#8d4a3c", width=3)
    if hat == "chef":
        p.rect(x-20, top-6, x+20, top+8, PAPER)
        p.oval(x-26, top-30, x+26, top+2, PAPER)
    elif hat == "helmet":
        p.c.create_arc(x-28, top-10, x+28, top+34, start=0, extent=180, fill="#f2c230", outline="#b8901f", width=2)
        p.rect(x-32, top+10, x+32, top+15, "#f2c230")
        p.oval(x-6, top-4, x+6, top+8, "#fff3b0")
    elif hat == "straw":
        p.oval(x-46, top+4, x+46, top+18, "#e8cf7a")
        p.c.create_arc(x-24, top-16, x+24, top+24, start=0, extent=180, fill="#e8cf7a", outline="#c9a94e")
        p.rect(x-24, top+2, x+24, top+6, "#b4442f")
    elif hat == "cap":
        p.c.create_arc(x-25, top-6, x+25, top+30, start=0, extent=180, fill=look.get("cap", "#2f4b5a"), outline="#1f2a30")
        p.rect(x, top+8, x+34, top+13, look.get("cap", "#2f4b5a"))
    if look.get("goggles"):
        p.oval(x-20, top+18, x-2, top+32, "#9fd0d4", outline="#3a3a3a", width=3)
        p.oval(x+2, top+18, x+20, top+32, "#9fd0d4", outline="#3a3a3a", width=3)
    # Arms resting on the counter.
    for side in (-1, 1):
        p.line((x+side*36, top+66, x+side*52, counter_y-6, x+side*24, counter_y-4), shirt, 14)
        p.oval(x+side*24-8, counter_y-12, x+side*24+8, counter_y+2, skin)


def counter(p, left, top, right, colors=("#e0b97a", "#c99b5c", "#9aa3a6")):
    surface, front, edge = colors
    p.rect(left, top, right, SCENE_H, front)
    p.rect(left, top, right, top+12, surface)
    p.rect(left, top-3, right, top+1, edge)
    for x in range(left+30, right, 60):
        p.line((x, top+16, x, SCENE_H), "#b48a50", 2)


def chalkboard(p, x, y, title):
    p.rect(x-4, y-4, x+168, y+70, "#7a5a3b")
    p.rect(x, y, x+164, y+66, "#2f3b35")
    p.text(x+82, y+14, title, 9, "#f6e7b4", True)
    return p.text(x+82, y+42, "", 8, CHALK, wrap=150)


def bubble(p, left, top, right, bottom, tail_x, tail_y):
    radius = 18
    points = (left+radius, top, right-radius, top, right, top, right, top+radius, right, bottom-radius, right, bottom,
              right-radius, bottom, tail_x+22, bottom, tail_x, tail_y, tail_x-6, bottom, left+radius, bottom,
              left, bottom, left, bottom-radius, left, top+radius, left, top)
    p.poly(points, PAPER, outline="#3a3a3a", width=2, smooth=True)
    return p.text((left+right)/2, (top+bottom)/2, "", 12, INK, True, wrap=right-left-28)


# ----- Products on display -----

def product(p, kind, x, y, scale=1.0):
    s = scale
    if kind == "Iron ore":
        p.poly((x-14*s, y, x-10*s, y-12*s, x+2*s, y-16*s, x+14*s, y-8*s, x+12*s, y), "#6f6a66")
        p.oval(x-4*s, y-10*s, x+1*s, y-6*s, "#c9ccd0")
        p.oval(x+5*s, y-7*s, x+9*s, y-4*s, "#b9673f")
    elif kind == "Timber":
        p.rect(x-18*s, y-12*s, x+14*s, y, "#9b6a43")
        p.oval(x+8*s, y-12*s, x+20*s, y, "#d8b07a", outline="#8a5c38")
        p.oval(x+11*s, y-9*s, x+17*s, y-3*s, "#b8885a")
    elif kind == "Clay":
        p.rect(x-14*s, y-12*s, x+14*s, y, "#c56b47")
        p.rect(x-14*s, y-12*s, x+14*s, y-9*s, "#d98a64")
    elif kind == "Wheat":
        p.poly((x-8*s, y, x+8*s, y, x+4*s, y-18*s, x-4*s, y-18*s), "#d9b04f")
        for dx in (-6, -2, 2, 6):
            p.oval(x+dx*s-3*s, y-28*s, x+dx*s+3*s, y-16*s, "#efc65a")
        p.rect(x-8*s, y-10*s, x+8*s, y-7*s, "#a1572f")
    elif kind == "Eggs":
        p.oval(x-16*s, y-8*s, x+16*s, y+4*s, "#9b6a43")
        for dx in (-9, 0, 9):
            p.oval(x+dx*s-5*s, y-14*s, x+dx*s+5*s, y-1*s, "#f6efe1", outline="#d8ccb6")
    elif kind == "Tools":
        p.rect(x-2*s, y-26*s, x+2*s, y, "#9b6a43")
        p.rect(x-9*s, y-28*s, x+9*s, y-21*s, "#7d8a8c")
        p.line((x+10*s, y, x+18*s, y-22*s), "#9aa3a6", max(1, round(4*s)))
        p.oval(x+14*s, y-28*s, x+22*s, y-20*s, "#9aa3a6")
    elif kind == "Furniture":
        p.rect(x-12*s, y-14*s, x+12*s, y-10*s, "#a36d3f")
        p.rect(x+8*s, y-34*s, x+12*s, y-10*s, "#8a5a34")
        p.rect(x-12*s, y-10*s, x-9*s, y, "#8a5a34")
        p.rect(x+9*s, y-10*s, x+12*s, y, "#8a5a34")
    elif kind == "Pottery":
        p.poly((x-6*s, y-30*s, x+6*s, y-30*s, x+5*s, y-24*s, x+13*s, y-12*s, x+8*s, y, x-8*s, y,
                x-13*s, y-12*s, x-5*s, y-24*s), "#c8693f", smooth=True)
        p.line((x-11*s, y-13*s, x+11*s, y-13*s), "#2f5f8a", max(1, round(3*s)))
    elif kind == "Bread":
        p.oval(x-16*s, y-12*s, x+16*s, y, "#c98a4b")
        for dx in (-7, 0, 7):
            p.line((x+dx*s-3*s, y-9*s, x+dx*s+3*s, y-3*s), "#f3d39a", max(1, round(2*s)))
    elif kind == "Pastéis":
        p.oval(x-12*s, y-8*s, x+12*s, y+2*s, "#c98a4b")
        p.oval(x-9*s, y-7*s, x+9*s, y-1*s, "#f2c94c")
        p.oval(x-3*s, y-6*s, x+1*s, y-3*s, "#8a4b22")
    elif kind == "Machinery":
        for tooth in range(8):
            angle = tooth*math.tau/8
            p.rect(x+math.cos(angle)*14*s-3*s, y-14*s+math.sin(angle)*14*s-3*s,
                   x+math.cos(angle)*14*s+3*s, y-14*s+math.sin(angle)*14*s+3*s, "#5f7d82")
        p.oval(x-12*s, y-26*s, x+12*s, y-2*s, "#7d9aa0")
        p.oval(x-4*s, y-18*s, x+4*s, y-10*s, "#2f4b5a")


def display(p, kind, left, right, y, scale=1.3):
    step = (right-left)/5
    for index in range(5):
        product(p, kind, left+step*(index+.5), y, scale)


# ----- Backdrops -----

def market_hall(p, product_name):
    """A busy covered food market: steel trusses, hanging lamps and long shared tables."""
    p.rect(0, 0, SCENE_W, 175, "#3f4447")
    p.poly((240, 0, 400, 0, 380, 70, 260, 70), "#5f7fb2")
    for x in range(-160, SCENE_W+160, 44):
        p.line((x, 0, x+110, 175), "#6c7377", 1)
        p.line((x+110, 0, x, 175), "#6c7377", 1)
    for y in (38, 92, 150):
        p.line((0, y, SCENE_W, y), "#858d91", 3)
    p.rect(0, 160, SCENE_W, 240, "#202428")
    for index, name in enumerate(("PEIXE", "QUEIJOS", "VINHOS", "PETISCOS", "FLORES", "DOCES", "CAFÉ")):
        x = 8+index*90
        p.rect(x, 166, x+80, 182, "#0f1113")
        p.text(x+40, 174, name, 6, "#f2efe6", True)
        p.rect(x+4, 186, x+76, 234, "#e8c27a")
        p.rect(x+4, 214, x+76, 234, "#8a6a45")
        for shopper in range(3):
            p.person(x+16+shopper*24, 236, .45, COATS[(index+shopper) % 6], SKINS[shopper % 4], HAIRS[index % 5])
    # The hall's big round sign hangs on the left, clear of the vendor's speech bubble.
    p.line((130, 0, 130, 50), "#1a1d1f", 2)
    p.oval(64, 46, 196, 156, "#121416", outline="#2a2e31", width=3)
    p.text(130, 90, "MERCADO", 15, "#f5f1e6", True)
    p.text(130, 116, "L I S B O A", 7, "#c9c3b4", True)
    p.rect(0, 240, SCENE_W, SCENE_H, "#cdbfa4")
    rng = random.Random(7)
    for y, scale in ((262, .55), (284, .7), (310, .85)):
        for left in (20, 230, 450):
            width = 150*scale+40
            p.rect(left, y-12*scale, left+width, y-4*scale, "#dcb37a")
            for seat in range(int(width//22)):
                person_x = left+10+seat*22
                p.person(person_x, y-6*scale, scale*.8, rng.choice(COATS), rng.choice(SKINS), rng.choice(HAIRS))
            p.rect(left, y-6*scale, left+width, y, "#c79b5e")
    for x, y in ((235, 140), (490, 110)):
        p.line((x, 0, x, y-22), "#1a1d1f", 1)
        p.poly((x-8, y-24, x+8, y-24, x+20, y, x-20, y), "#1e2326")
        p.oval(x-14, y-4, x+14, y+6, "#f6e3a8")


def mine(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#4b4440")
    rng = random.Random(3)
    for _ in range(40):
        x, y, size = rng.uniform(0, SCENE_W), rng.uniform(0, 280), rng.uniform(20, 60)
        p.poly((x, y, x+size, y+size*.2, x+size*.8, y+size*.9, x-size*.2, y+size*.7),
               rng.choice(("#5a524c", "#625a53", "#544c47", "#6b625a")))
    p.poly((150, 290, 210, 70, 430, 70, 490, 290), "#1b1714")
    for x in (176, 446):
        p.rect(x-10, 70, x+10, 290, "#7a5434")
    p.rect(150, 62, 490, 82, "#8a6240")
    p.text(320, 72, "MINA DO MONTE DE FERRO", 7, "#f2d79c", True)
    for x in (230, 410):
        p.line((x, 82, x, 110), "#3a2f26", 2)
        p.oval(x-8, 108, x+8, 124, "#ffd27a")
    for offset in (-40, 40):
        p.line((320+offset*.4, 150, 320+offset*2.6, 300), "#8f9497", 3)
    for y in range(160, 300, 14):
        spread = (y-150)/150
        p.line((320-18-60*spread, y, 320+18+60*spread, y), "#5c4430", 4)
    p.rect(0, 290, SCENE_W, SCENE_H, "#3a3330")
    p.poly((40, 300, 150, 300, 140, 250, 50, 250), "#6c7377")
    for dx in (60, 85, 110):
        product(p, "Iron ore", dx, 252, 1.4)
    p.oval(55, 296, 75, 316, "#2b2b2b")
    p.oval(115, 296, 135, 316, "#2b2b2b")


def sawmill(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#b98a5a")
    for x in range(0, SCENE_W, 26):
        p.line((x, 0, x, 280), "#a47647", 2)
    p.rect(30, 40, 230, 170, "#8fb7c6")
    for x, y, size in ((60, 160, 30), (110, 150, 40), (170, 165, 28), (210, 155, 36)):
        p.poly((x, y-size*2.6, x-size, y, x+size, y), "#4f7a55")
    p.rect(30, 100, 230, 106, "#7a5434")
    p.rect(126, 40, 132, 170, "#7a5434")
    p.rect(0, 270, SCENE_W, SCENE_H, "#9a7046")
    for row, y in enumerate((250, 222, 194)):
        for index in range(5-row):
            x = 30+row*20+index*40
            p.rect(x, y, x+40, y+28, "#8b5a34")
            p.oval(x+24, y, x+52, y+28, "#e0b884", outline="#8a5c38")
            p.oval(x+33, y+9, x+43, y+19, "#c79a63")
    p.oval(250, 150, 330, 230, "#b9c0c3", outline="#7d8589", width=3)
    for tooth in range(16):
        angle = tooth*math.tau/16
        p.line((290+math.cos(angle)*40, 190+math.sin(angle)*40, 290+math.cos(angle)*46, 190+math.sin(angle)*46),
               "#7d8589", 3)
    p.oval(282, 182, 298, 198, "#5c6366")
    rng = random.Random(5)  # Fixed, so the sawdust stays put when the window resizes.
    for _ in range(18):
        x, y = rng.uniform(240, 340), rng.uniform(238, 268)
        p.oval(x, y, x+4, y+4, "#f0d9a8")


def clay_pit(p):
    p.rect(0, 0, SCENE_W, 120, "#f1d8b4")
    p.oval(500, 20, 560, 80, "#ffe08a")
    for index, color in enumerate(("#d9946c", "#c97f5a", "#b56a4b", "#9f5a40", "#8a4b36")):
        top = 110+index*34
        p.poly((0, top, SCENE_W, top-20, SCENE_W, SCENE_H, 0, SCENE_H), color)
        p.line((0, top, SCENE_W, top-20), "#e6a983", 2)
    p.poly((60, 260, 120, 240, 200, 255, 140, 285), "#7a7a70")
    p.oval(70, 270, 92, 292, "#2b2b2b")
    p.line((140, 270, 210, 230), "#7a5434", 4)
    for row in range(3):
        for index in range(4-row):
            product(p, "Clay", 236+index*30+row*15, 300-row*13, 1.0)


def farm(p):
    p.rect(0, 0, SCENE_W, 190, "#a9d4e3")
    p.oval(70, 30, 130, 90, "#ffe08a")
    for x, y in ((180, 60), (420, 40)):
        p.oval(x, y, x+80, y+26, "#fbf6ea")
        p.oval(x+30, y-12, x+80, y+20, "#fbf6ea")
    p.poly((0, 190, 200, 160, 420, 175, SCENE_W, 150, SCENE_W, SCENE_H, 0, SCENE_H), "#a7b86c")
    for row in range(8):
        y = 190+row*12
        p.line((0, y, SCENE_W, y-20), "#d9b45a", 5)
    p.rect(440, 110, 600, 230, "#b4442f")
    p.poly((430, 112, 520, 60, 610, 112), "#7a2f22")
    p.rect(495, 160, 545, 230, "#f5efe2")
    p.line((495, 160, 545, 230), "#b4442f", 3)
    p.line((545, 160, 495, 230), "#b4442f", 3)
    for x, y in ((90, 278), (150, 290), (200, 272)):
        p.oval(x-14, y-12, x+14, y+8, "#f5efe2")
        p.oval(x+8, y-20, x+20, y-8, "#f5efe2")
        p.poly((x+19, y-15, x+26, y-13, x+19, y-11), "#e3a43a")
        p.oval(x+12, y-24, x+17, y-19, "#d33a35")
    for x in (30, 250):
        product(p, "Wheat", x, 300, 1.8)


def forge(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#3d3532")
    for row in range(0, 280, 20):
        for col in range(0 if row % 40 else 15, SCENE_W, 30):
            p.rect(col, row, col+28, row+18, "#4a3f3a")
    p.poly((40, 280, 60, 120, 200, 120, 220, 280), "#5a4b44")
    p.oval(80, 170, 180, 260, "#ff9a3c")
    p.oval(100, 190, 160, 250, "#ffd27a")
    p.rect(60, 100, 200, 124, "#2a2420")
    p.rect(110, 0, 150, 100, "#2a2420")
    p.poly((250, 240, 330, 240, 320, 255, 300, 255, 300, 280, 280, 280, 280, 255, 260, 255), "#2f3335")
    rng = random.Random(9)
    for _ in range(14):
        x, y = rng.uniform(80, 200), rng.uniform(130, 200)
        p.line((x, y, x+rng.uniform(-8, 8), y-rng.uniform(4, 12)), "#ffd27a", 2)
    p.rect(0, 280, SCENE_W, SCENE_H, "#2a2420")
    for x in range(260, 600, 50):
        product(p, "Tools", x, 120, 1.3)
    p.rect(250, 125, 600, 130, "#6b5a4c")


def workshop(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#d8c09a")
    for x in range(0, SCENE_W, 34):
        p.line((x, 0, x, 280), "#c8ad84", 2)
    p.rect(40, 60, 300, 70, "#8a5a34")
    for x in range(60, 300, 40):
        product(p, "Tools", x, 58, 1.0)
    p.rect(40, 200, 260, 214, "#a36d3f")
    p.rect(50, 214, 60, 280, "#8a5a34")
    p.rect(240, 214, 250, 280, "#8a5a34")
    p.rect(70, 186, 200, 200, "#d8b07a")
    p.rect(0, 280, SCENE_W, SCENE_H, "#b08a5c")
    for x in (110, 170, 230):
        product(p, "Furniture", x, 300, 1.6)
    for y in range(110, 190, 14):
        p.rect(300, y, 470, y+10, "#c79a63")


def kiln(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#c98a64")
    for row in range(0, 280, 18):
        for col in range(0 if row % 36 else 14, SCENE_W, 28):
            p.rect(col, row, col+26, row+16, "#bf7c58")
    p.poly((40, 280, 40, 140, 120, 80, 200, 140, 200, 280), "#8a4b36")
    p.oval(80, 170, 160, 260, "#ff9a3c")
    p.oval(96, 190, 144, 250, "#ffd27a")
    p.rect(110, 0, 130, 90, "#6b3a2a")
    for y in (90, 150, 210):
        p.rect(250, y, 600, y+6, "#7a5434")
        for x in range(275, 600, 45):
            product(p, "Pottery", x, y, 1.0)
    p.rect(0, 280, SCENE_W, SCENE_H, "#9a5a40")
    p.oval(60, 300, 140, 320, "#5f6366")
    product(p, "Clay", 100, 300, 1.4)


def bakery(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#f1e2c3")
    for col in range(0, SCENE_W, 20):
        for row in range(170, 280, 20):
            p.rect(col+1, row+1, col+19, row+19, "#f7efdc" if (col+row) % 40 else "#3f6f9f")
    p.poly((40, 280, 40, 120, 140, 70, 240, 120, 240, 280), "#b8a48a")
    p.c.create_arc(80, 150, 200, 280, start=0, extent=180, fill="#3a2a20", outline="#3a2a20")
    p.oval(105, 205, 175, 260, "#ff9a3c")
    p.oval(120, 220, 160, 255, "#ffd27a")
    for y in (60, 110):
        p.rect(280, y, 600, y+6, "#8a5a34")
        for x in range(300, 600, 40):
            product(p, "Bread", x, y, .9)
    p.rect(0, 280, SCENE_W, SCENE_H, "#d6c3a0")
    for x in (40, 90):
        p.poly((x-18, 330, x+18, 330, x+14, 280, x-14, 280), "#efe7d4", outline="#c8bba1")
        p.text(x, 306, "FARINHA", 5, "#7a5434", True)


def pastelaria(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#f7efdc")
    for col in range(0, SCENE_W, 32):
        for row in range(0, 260, 32):
            p.rect(col+2, row+2, col+30, row+30, "#f5f2ea")
            p.oval(col+8, row+8, col+24, row+24, "#2f5f9f", width=0)
            p.oval(col+12, row+12, col+20, row+20, "#f5f2ea")
    p.rect(0, 250, SCENE_W, 270, "#2f5f9f")
    p.rect(40, 40, 230, 130, "#8a5a34")
    p.text(135, 72, "PASTÉIS", 14, "#f6e7b4", True)
    p.text(135, 100, "DE BELÉM", 9, "#f6e7b4", True)
    p.rect(60, 160, 210, 250, "#9aa3a6")
    p.rect(70, 170, 200, 210, "#3a3a3a")
    p.oval(120, 214, 150, 236, "#f5efe2")
    p.rect(0, 270, SCENE_W, SCENE_H, "#e9dcc0")


def shipyard(p):
    p.rect(0, 0, SCENE_W, 180, "#a9d4e3")
    p.rect(0, 180, SCENE_W, SCENE_H, "#4f8fa3")
    for y in range(195, 300, 16):
        p.line((0, y, SCENE_W, y), "#6fb0c0", 1)
    p.poly((60, 220, 420, 220, 380, 280, 100, 280), "#d6563f")
    p.rect(60, 210, 420, 222, "#f5efe2")
    p.rect(180, 150, 300, 210, "#f5efe2")
    for x in range(195, 290, 25):
        p.rect(x, 165, x+15, 180, "#2f4b5a")
    p.rect(230, 110, 246, 150, "#2f3d45")
    p.line((470, 280, 470, 40, 300, 40), "#f2c230", 8)
    p.line((330, 40, 330, 120), "#3a3a3a", 2)
    p.rect(320, 120, 340, 132, "#3a3a3a")
    p.rect(0, 280, SCENE_W, SCENE_H, "#8a7a62")
    for x in range(0, SCENE_W, 40):
        p.line((x, 280, x, SCENE_H), "#6f6250", 2)
    product(p, "Timber", 70, 320, 1.6)
    product(p, "Iron ore", 130, 320, 1.6)


def precision_works(p):
    p.rect(0, 0, SCENE_W, SCENE_H, "#cfd8da")
    for x in range(0, SCENE_W, 60):
        p.rect(x, 0, x+4, 280, "#b9c4c7")
    p.rect(30, 50, 280, 200, "#2f4b5a")
    p.rect(40, 60, 270, 150, "#7fa8b0")
    for index in range(4):
        product(p, "Machinery", 70+index*55, 140, 1.2)
    p.rect(40, 160, 270, 190, "#5f7d82")
    for x in range(330, 600, 70):
        p.oval(x, 60, x+50, 110, "#7d9aa0", outline="#4a6166", width=3)
        p.oval(x+18, 78, x+32, 92, "#2f4b5a")
    p.rect(0, 280, SCENE_W, SCENE_H, "#9aa6a8")
    p.line((0, 300, SCENE_W, 300), "#f2c230", 4)


SUPPLIER_SCENES = (mine, sawmill, clay_pit, farm)
FACTORY_SCENES = (forge, workshop, kiln, bakery)
SUPPLIES = ("Iron ore", "Timber", "Clay", "Wheat")
PRODUCTS = ("Tools", "Furniture", "Pottery", "Bread")
LOOKS = {
    "mine": {"skin": "#c78d64", "hair": "#3b2f2a", "shirt": "#4f6a8a", "hat": "helmet", "beard": True},
    "sawmill": {"skin": "#f0c9a5", "hair": "#a8642f", "shirt": "#b4442f", "plaid": True, "beard": True},
    "clay": {"skin": "#8e5f43", "hair": "#1f1b1a", "shirt": "#74794f", "apron": "#c56b47", "hat": "cap", "cap": "#c56b47"},
    "farm": {"skin": "#e6b98f", "hair": "#6b4a32", "shirt": "#5d8a4a", "hat": "straw"},
    "forge": {"skin": "#c78d64", "hair": "#1f1b1a", "shirt": "#5a5f63", "apron": "#6b4a32"},
    "workshop": {"skin": "#f0c9a5", "hair": "#c9b9a0", "shirt": "#4f6a8a", "apron": "#a36d3f", "beard": True},
    "kiln": {"skin": "#e6b98f", "hair": "#3b2f2a", "shirt": "#866653", "apron": "#2f5f8a"},
    "bakery": {"skin": "#f0c9a5", "hair": "#6b4a32", "shirt": PAPER, "apron": "#e9e3d3", "hat": "chef"},
    "market": {"skin": "#c78d64", "hair": "#3b2f2a", "shirt": "#2f3d45", "apron": "#1a1d1f"},
    "pastelaria": {"skin": "#f0c9a5", "hair": "#3b2f2a", "shirt": PAPER, "apron": "#2f5f9f", "hat": "chef"},
    "shipyard": {"skin": "#8e5f43", "hair": "#1f1b1a", "shirt": "#2f4b5a", "hat": "cap", "cap": "#f2c230", "beard": True},
    "precision": {"skin": "#e6b98f", "hair": "#a8642f", "shirt": "#5f7d82", "goggles": True},
}


def draw_scene(p, town, site):
    """Draw a building's backdrop, vendor, counter and goods. Returns (bubble, board) text items."""
    role, trade = site.role, scene_trade(town, site)
    vendor_x, counter_top = 470, 300
    if role == "SUPPLIER":
        SUPPLIER_SCENES[trade](p)
        look = LOOKS[("mine", "sawmill", "clay", "farm")[trade]]
        goods = [SUPPLIES[trade]] + (["Eggs"] if trade == 3 else [])
        title = "TODAY'S PRICE"
    elif role == "FACTORY":
        FACTORY_SCENES[trade](p)
        look = LOOKS[("forge", "workshop", "kiln", "bakery")[trade]]
        goods = [PRODUCTS[trade]]
        title = "WORKSHOP"
    elif role == "PUBLIC SHOP":
        market_hall(p, PRODUCTS[trade])
        look = LOOKS["market"]
        goods = [PRODUCTS[trade]]
        title = "BUYING TODAY"
        # The stall's name hangs to the right of the vendor and the speech bubble's tail.
        p.line((535, 0, 535, 138), "#1a1d1f", 1)
        p.line((615, 0, 615, 138), "#1a1d1f", 1)
        p.rect(520, 138, 630, 168, "#121416", outline="#2a2e31", width=2)
        p.text(575, 153, PRODUCTS[trade].upper(), 9, "#f5f1e6", True)
    elif role == "PASTELARIA":
        pastelaria(p)
        look, goods, title = LOOKS["pastelaria"], ["Pastéis"], "TODAY"
    elif role == "SHIPYARD":
        shipyard(p)
        look, goods, title = LOOKS["shipyard"], ["Timber", "Iron ore"], "REPAIR JOBS"
    else:
        precision_works(p)
        look, goods, title = LOOKS["precision"], ["Machinery"], "PRECISION WORKS"
    vendor(p, vendor_x, counter_top, look)
    counter(p, 330, counter_top, SCENE_W)
    width = (SCENE_W-340)/len(goods)
    for index, kind in enumerate(goods):
        display(p, kind, 340+index*width, 340+(index+1)*width, counter_top+4, 1.25 if len(goods) == 1 else 1.0)
    board = chalkboard(p, 336, 318, title)
    speech = bubble(p, 250, 20, 470, 130, 420, 168)
    return speech, board


def draw_player(p, profile, x, floor_y, scale=3.4):
    from lisbon_scene import draw_character
    from tycoon import BODY_COLORS, COSTUMES, HAIR_COLORS
    draw_character(p.c, profile, BODY_COLORS, HAIR_COLORS, COSTUMES, 0, 0, tag="player")
    p.c.scale("player", 0, 0, scale, scale)
    bbox = p.c.bbox("player")
    if bbox:
        p.c.move("player", x-(bbox[0]+bbox[2])/2, floor_y-bbox[3])
    p.rect(x-62, floor_y+8, x+62, floor_y+32, "#1f2a30")
    p.text(x, floor_y+20, profile.get("name", "Player"), 11, "#fff2d5", True)


# ----- The panel -----

def open_interior(game, site):
    """Show the building's interior. Trading keys work inside; Esc returns to the street."""
    if game.profile_window is not None:
        return
    town = game.town
    game.keys.clear()
    game.interior_open = True
    panel = game.profile_window = tk.Frame(game.root, bg=INK)
    panel.place(x=0, y=0, relwidth=1, relheight=1)
    panel.lift()
    canvas = tk.Canvas(panel, highlightthickness=0, bg=INK)
    canvas.pack(fill="both", expand=True)
    footer = tk.Frame(panel, bg="#252c31", padx=18, pady=10)
    footer.pack(fill="x")
    info = tk.Frame(footer, bg="#252c31")
    info.pack(side="left")
    tk.Label(info, text=site.name, bg="#252c31", fg="#f6e7b4", font=(FONT, 13, "bold")).pack(anchor="w")
    wallet = tk.Label(info, text="", bg="#252c31", fg="#d4e6dd", font=(FONT, 10))
    wallet.pack(anchor="w")
    state = {"speech": None, "board": None, "reply": vendor_greeting(town, site), "opened": time.monotonic(),
             "held": {"e"}, "scale": 1, "timer": None}

    def close():
        if state["timer"] is not None:
            panel.after_cancel(state["timer"])
        game.keys.clear()
        game.interior_open = False
        game.profile_window = None
        panel.destroy()
        game.root.focus_set()

    def button(parent, text, command, primary=False):
        options = dict(text=text, command=command, font=(FONT, 11, "bold"), padx=14, pady=6)
        if not IS_MAC:
            options.update(bg="#f2c230" if primary else "#d4c6a9", fg="#252c31", relief="flat",
                           activebackground="#ffd68f" if primary else "#e5d9bd", cursor="hand2")
        widget = tk.Button(parent, highlightbackground="#252c31", **options)
        widget.pack(side="right", padx=(8, 0))
        return widget

    def refresh():
        """Live prices, timers and the player's cash and bag."""
        wallet.configure(text=f"Cash ${town.cash:,}   ·   Bag {town.cargo}/{town.carry_capacity}")
        if state["board"] is not None and canvas.winfo_exists():
            canvas.itemconfigure(state["board"], text=town.site_status(site))
        state["timer"] = panel.after(400, refresh)

    def act(key):
        if key in ("e", "q"):
            town.interact(bulk=(key == "q"))
        elif key in ("f", "r") and site.role == "SUPPLIER" and site.trade == 3:
            town.buy_eggs(bulk=(key == "r"))
        else:
            return
        state["reply"] = town.message
        if state["speech"] is not None:
            canvas.itemconfigure(state["speech"], text=state["reply"])

    def key_down(event):
        key = event.keysym.lower()
        if key == "escape":
            close()
            return
        # The E that opened the door may still be held or repeating.
        if key in state["held"] or time.monotonic()-state["opened"] < OPEN_GRACE_SECONDS:
            state["held"].add(key)
            return
        state["held"].add(key)
        act(key)

    def key_up(event):
        state["held"].discard(event.keysym.lower())

    button(footer, "Leave  ·  Esc", close)
    for label, key in reversed(actions_for(town, site)):
        button(footer, label, lambda key=key: act(key), primary=True)

    def render(event):
        canvas.delete("all")
        painter = Painter(canvas)
        state["speech"], state["board"] = draw_scene(painter, town, site)
        draw_player(painter, town.profile, 150, 352)
        canvas.itemconfigure(state["speech"], text=state["reply"])
        canvas.itemconfigure(state["board"], text=town.site_status(site))
        scale = min(event.width/SCENE_W, event.height/SCENE_H)
        canvas.scale("all", 0, 0, scale, scale)
        canvas.move("all", (event.width-SCENE_W*scale)/2, (event.height-SCENE_H*scale)/2)
        for item, (size, wrap, bold) in painter.sizes.items():
            canvas.itemconfigure(item, font=(FONT, max(6, round(size*scale)), "bold" if bold else "normal"),
                                 width=wrap*scale)

    canvas.bind("<Configure>", render)
    panel.bind("<KeyPress>", key_down)
    panel.bind("<KeyRelease>", key_up)
    panel.focus_set()
    refresh()
    return panel
