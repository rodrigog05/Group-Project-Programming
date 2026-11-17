"""The ferry crossing: the player rides the cacilheiro across the Tejo.

The fare is charged and the player moved by ferry.ride_ferry before the
animation starts, so skipping or closing the scene never loses the trip.
"""
import math
import random
import time
import tkinter as tk

from ferry import nearby_pier, other_pier, ride_ferry
from interiors import FONT, IS_MAC, INK, Painter

SCENE_W, SCENE_H = 640, 400
CROSSING_SECONDS = 4.5
FRAME_MS = 33
WATER_Y = 250
LEFT_PIER_X, RIGHT_PIER_X = 120, 520


def draw_backdrop(p):
    """Looking along the Tejo: Lisboa on the left bank, Almada and Cristo Rei on the right."""
    for band in range(12):
        top = band*WATER_Y/12
        shade = band/11
        color = "#%02x%02x%02x" % (round(140+100*shade), round(196+34*shade), round(216+12*shade))
        p.rect(0, top, SCENE_W, top+WATER_Y/12+1, color)
    p.oval(420, 40, 470, 90, "#ffe08a")
    for x, y in ((90, 50), (300, 30), (520, 70)):
        p.oval(x, y, x+70, y+20, "#fbf6ea")
        p.oval(x+22, y-10, x+60, y+16, "#fbf6ea")
    # Ponte 25 de Abril on the horizon, joining the two banks.
    deck_y = 168
    p.rect(150, deck_y, 490, deck_y+6, "#b8432f")
    for tower_x in (235, 405):
        p.rect(tower_x-4, 96, tower_x+4, WATER_Y, "#b8432f")
        p.rect(tower_x-7, 108, tower_x+7, 112, "#b8432f")
    points = []
    for step in range(41):
        x = 150+step*340/40
        if x <= 235:
            y = deck_y-(x-150)/85*70
        elif x >= 405:
            y = deck_y-(490-x)/85*70
        else:
            y = 160-((x-320)/85)**2*62  # The main cable sags towards the deck mid-span.
        points += [x, y]
    p.line(points, "#8e2d20", 2)
    for x in range(160, 485, 12):
        top = points[1+2*min(40, max(0, round((x-150)/8.5)))]
        p.line((x, top, x, deck_y), "#c6584a", 1)
    # Lisbon hills and houses on the left bank.
    p.poly((0, WATER_Y, 0, 150, 60, 130, 130, 160, 190, 200, 230, WATER_Y), "#d8cfa8", smooth=True)
    rng = random.Random(3)
    for column in range(7):
        x = 6+column*30
        for row in range(4):
            y = WATER_Y-14-row*22-max(0, column-3)*4
            if y < 150+column*8:
                continue
            p.rect(x, y-20, x+26, y, rng.choice(("#f2e3c6", "#e9c4b6", "#c9dbe0", "#f1d58e", "#e8b7a0")))
            p.poly((x-2, y-20, x+13, y-29, x+28, y-20), rng.choice(("#c8693f", "#b85a36")))
            p.rect(x+6, y-14, x+11, y-7, "#2f4b5a")
            p.rect(x+16, y-14, x+21, y-7, "#2f4b5a")
    p.text(60, 120, "LISBOA", 10, "#3c5d61", True)
    # Almada's cliff with Cristo Rei on the right bank.
    p.poly((SCENE_W, WATER_Y, SCENE_W, 140, 590, 150, 545, 190, 500, WATER_Y), "#b7c08a", smooth=True)
    p.poly((585, 150, 605, 150, 600, 112, 590, 112), "#e9e3d3")
    p.rect(593, 82, 597, 112, "#f1ece0")
    p.rect(583, 88, 607, 92, "#f1ece0")
    p.oval(591, 74, 599, 83, "#f1ece0")
    p.text(590, 210, "ALMADA", 10, "#4f6a3e", True)
    # The river, and the two piers.
    for band in range(6):
        top = WATER_Y+band*(SCENE_H-WATER_Y)/6
        color = ("#6fb3c2", "#62a7b8", "#579dae", "#4d92a4", "#45889a", "#3d7f91")[band]
        p.rect(0, top, SCENE_W, top+(SCENE_H-WATER_Y)/6+1, color)
    for x, side in ((LEFT_PIER_X, -1), (RIGHT_PIER_X, 1)):
        left, right = (0, x+30) if side < 0 else (x-30, SCENE_W)
        p.rect(left, WATER_Y+18, right, WATER_Y+28, "#9b7651")
        for post in range(int(left)+10, int(right), 26):
            p.rect(post, WATER_Y+28, post+5, WATER_Y+52, "#5e4630")
    p.text(LEFT_PIER_X-40, WATER_Y+40, "CAIS DO SODRÉ", 8, "#f6efe1", True)
    p.text(RIGHT_PIER_X+40, WATER_Y+40, "CACILHAS", 8, "#f6efe1", True)


def draw_moving(canvas, profile, progress, elapsed, heading):
    """The ferry with the player aboard, its wake, waves and gulls, in scene coordinates."""
    from lisbon_scene import draw_character
    from tycoon import BODY_COLORS, COSTUMES, HAIR_COLORS
    p = Painter(canvas)
    tag = {"tags": "moving"}
    eased = progress*progress*(3-2*progress)
    start, end = (LEFT_PIER_X, RIGHT_PIER_X) if heading > 0 else (RIGHT_PIER_X, LEFT_PIER_X)
    x = start+(end-start)*eased
    y = WATER_Y+34+math.sin(elapsed*2.4)*2
    for index in range(26):
        wave_x = (index*61+elapsed*18*(1 if index % 2 else -1)) % (SCENE_W+60)-30
        wave_y = WATER_Y+30+(index*37) % (SCENE_H-WATER_Y-40)
        p.line((wave_x, wave_y, wave_x+18+index % 3*8, wave_y), "#cfe8ea", 1, **tag)
    # Wake behind the ferry while it moves.
    if 0 < progress < 1:
        for trail in range(1, 5):
            trail_x = x-heading*(48+trail*16)
            p.line((trail_x, y+10+trail*2, trail_x-heading*18, y+12+trail*3), "#eaf6f4", 2, **tag)
    # The orange-and-white cacilheiro, bow pointing where it is going.
    bow = heading
    p.poly((x-58, y-4, x+58, y-4, x+58+bow*12, y-14, x+46, y+16, x-46, y+16, x-58-(-bow)*0, y-4), "#e07a2e", **tag)
    p.rect(x-56, y-8, x+56, y-4, "#f5efe2", **tag)
    p.rect(x-38, y-34, x+30, y-8, "#f5efe2", **tag)
    for window in range(5):
        left = x-32+window*12
        p.rect(left, y-28, left+8, y-20, "#2f4b5a", **tag)
    p.rect(x-6, y-50, x+6, y-34, "#2f3d45", **tag)
    p.rect(x-6, y-50, x+6, y-45, "#d33a35", **tag)
    p.text(x-4, y+6, "CACILHEIRO", 6, "#fff5e2", True, **tag)
    # The player stands on the open deck at the bow.
    draw_character(canvas, profile, BODY_COLORS, HAIR_COLORS, COSTUMES, 0, 0, facing=bow, tag="deckplayer")
    canvas.scale("deckplayer", 0, 0, 1.4, 1.4)
    bbox = canvas.bbox("deckplayer")
    if bbox:
        canvas.move("deckplayer", x+bow*42-(bbox[0]+bbox[2])/2, y-8-bbox[3])
    canvas.addtag_withtag("moving", "deckplayer")
    canvas.dtag("deckplayer", "deckplayer")
    for index in range(4):
        gull_x = (index*170+elapsed*40) % (SCENE_W+40)-20
        gull_y = 60+index*22+math.sin(elapsed*1.3+index)*6
        flap = 4*math.sin(elapsed*9+index)
        p.line((gull_x-8, gull_y, gull_x-3, gull_y-flap, gull_x, gull_y, gull_x+3, gull_y-flap, gull_x+8, gull_y),
               "#2f3d45", 2, **tag)
    return p.sizes


def open_ferry(game):
    """Charge the fare, then animate the crossing. Esc skips to the arrival."""
    town = game.town
    if game.profile_window is not None:
        return
    origin = nearby_pier(town.x, town.y)
    trip = ride_ferry(town)
    if trip is None:
        return  # town.message explains why (no cash, not at a pier)
    origin, destination = trip
    heading = 1 if origin.north else -1  # Lisboa is on the left of the scene.
    game.keys.clear()
    # Keep production timers running during the short crossing, as inside buildings.
    game.interior_open = True
    panel = game.profile_window = tk.Frame(game.root, bg=INK)
    panel.place(x=0, y=0, relwidth=1, relheight=1)
    panel.lift()
    canvas = tk.Canvas(panel, highlightthickness=0, bg=INK)
    canvas.pack(fill="both", expand=True)
    footer = tk.Frame(panel, bg="#252c31", padx=18, pady=10)
    footer.pack(fill="x")
    tk.Label(footer, text=f"Ferry  ·  {origin.name}  →  {destination.name}", bg="#252c31", fg="#f6e7b4",
             font=(FONT, 13, "bold")).pack(side="left")
    state = {"started": time.monotonic(), "timer": None, "scale": 1, "offset": (0, 0), "closed": False}

    def close():
        if state["closed"]:
            return
        state["closed"] = True
        if state["timer"] is not None:
            panel.after_cancel(state["timer"])
        game.keys.clear()
        game.interior_open = False
        game.profile_window = None
        panel.destroy()
        view = getattr(game, "world_view", None)
        if view is not None:
            view.camera.follow(town.x, town.y, snap=True)
        game.root.focus_set()

    options = dict(text="Skip  ·  Esc", command=close, font=(FONT, 11, "bold"), padx=14, pady=6)
    if not IS_MAC:
        options.update(bg="#d4c6a9", fg="#252c31", relief="flat", activebackground="#e5d9bd", cursor="hand2")
    tk.Button(footer, highlightbackground="#252c31", **options).pack(side="right")

    def place(tag, sizes):
        scale, (offset_x, offset_y) = state["scale"], state["offset"]
        canvas.scale(tag, 0, 0, scale, scale)
        canvas.move(tag, offset_x, offset_y)
        for item, (size, wrap, bold) in sizes.items():
            canvas.itemconfigure(item, font=(FONT, max(6, round(size*scale)), "bold" if bold else "normal"))

    def render(event):
        canvas.delete("all")
        state["scale"] = scale = min(event.width/SCENE_W, event.height/SCENE_H)
        state["offset"] = ((event.width-SCENE_W*scale)/2, (event.height-SCENE_H*scale)/2)
        painter = Painter(canvas)
        draw_backdrop(painter)
        canvas.addtag_all("backdrop")
        place("backdrop", painter.sizes)

    def frame():
        elapsed = time.monotonic()-state["started"]
        progress = min(1, elapsed/CROSSING_SECONDS)
        canvas.delete("moving")
        place("moving", draw_moving(canvas, town.profile, progress, elapsed, heading))
        if progress >= 1 and elapsed > CROSSING_SECONDS+.6:
            close()
            return
        state["timer"] = panel.after(FRAME_MS, frame)

    canvas.bind("<Configure>", render)
    panel.bind("<Escape>", lambda event: close())
    panel.focus_set()
    frame()
    return panel
