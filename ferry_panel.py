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


LEFT_QUAY_X, RIGHT_QUAY_X = 215, 505  # Where each bank's quay wall meets the river
LISBON_RIDGE = ((-20, 132), (40, 140), (90, 160), (140, 188), (180, 214), (205, 232), (LEFT_QUAY_X, 236))
ALMADA_RIDGE = ((RIGHT_QUAY_X, 236), (520, 228), (545, 202), (572, 168), (600, 148), (630, 138), (660, 134))
DECK_Y = 172


def ridge_y(ridge, x):
    """Height of a bank's skyline at x, by straight segments between its points."""
    for (x1, y1), (x2, y2) in zip(ridge, ridge[1:]):
        if x1 <= x <= x2:
            return y1+(y2-y1)*(x-x1)/(x2-x1)
    return ridge[0][1] if x < ridge[0][0] else ridge[-1][1]


def draw_bank(p, ridge, left, right, fill):
    """A landmass running off the screen edge, standing on a stone quay wall at the river."""
    points = [value for point in ridge for value in point]
    p.poly(points+[right, WATER_Y+12, left, WATER_Y+12], fill)
    p.rect(left, 236, right, WATER_Y+12, "#b9b2a0")
    for y in range(240, WATER_Y+12, 8):
        p.line((left, y, right, y), "#a39c8a")
    for row, y in enumerate(range(240, WATER_Y+12, 8)):
        for x in range(int(left)+(0 if row % 2 else 9), int(right), 18):
            p.line((x, y, x, y+8), "#a39c8a")
    p.rect(left, 233, right, 237, "#e8dcc0")


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
    # Distant hills where the river bends out of sight, between the two banks.
    far = [(-10, WATER_Y)]+[(x, 222+8*math.sin(x/37)+5*math.sin(x/13)) for x in range(-10, 660, 20)]+[(660, WATER_Y)]
    p.poly([value for point in far for value in point], "#a9c2b6")
    # Ponte 25 de Abril runs from the Lisbon hillside to the Almada cliff; the banks cover its ends.
    left_end, right_end, towers, top = 10, 630, (232, 408), 92
    for tower_x in towers:
        p.rect(tower_x-9, WATER_Y-6, tower_x+9, WATER_Y+8, "#bdb5a2")
        for leg in (-5, 3):
            p.rect(tower_x+leg, top, tower_x+leg+3, WATER_Y-4, "#b8432f")
        for beam_y in (top+4, top+40, top+70, DECK_Y+16):
            p.rect(tower_x-6, beam_y, tower_x+6, beam_y+4, "#b8432f")
    p.rect(left_end, DECK_Y-3, right_end, DECK_Y+3, "#5e6b70")
    p.rect(left_end, DECK_Y+3, right_end, DECK_Y+14, "#b8432f")
    for x in range(left_end, right_end, 12):
        p.line((x, DECK_Y+3, x+6, DECK_Y+14, x+12, DECK_Y+3), "#8e2d20", 1)

    def cable_y(x):
        if x <= towers[0]:
            return DECK_Y-(DECK_Y-top)*(x-left_end)/(towers[0]-left_end)
        if x >= towers[1]:
            return DECK_Y-(DECK_Y-top)*(right_end-x)/(right_end-towers[1])
        middle, half = (towers[0]+towers[1])/2, (towers[1]-towers[0])/2
        return DECK_Y-8-(DECK_Y-8-top)*((x-middle)/half)**2  # The main cable sags towards the deck.

    p.line([value for x in range(left_end, right_end+1, 6) for value in (x, cable_y(x))], "#8e2d20", 2)
    for x in range(left_end+12, right_end, 12):
        if all(abs(x-tower) > 4 for tower in towers):
            p.line((x, cable_y(x), x, DECK_Y-3), "#c6584a", 1)
    # Lisbon: houses climb the hill from the quay.
    draw_bank(p, LISBON_RIDGE, -20, LEFT_QUAY_X, "#d8cfa8")
    rng = random.Random(3)
    houses = []
    for x in range(-14, LEFT_QUAY_X-24, 25):
        y = 233
        while y-22 > ridge_y(LISBON_RIDGE, x+12)+4:
            houses.append((y, x))
            y -= 19
    for y, x in sorted(houses):
        p.rect(x, y-20, x+24, y, rng.choice(("#f2e3c6", "#e9c4b6", "#c9dbe0", "#f1d58e", "#e8b7a0", "#f5efe2")))
        p.poly((x-2, y-20, x+12, y-28, x+26, y-20), rng.choice(("#c8693f", "#b85a36", "#d47a4e")))
        p.rect(x+5, y-14, x+10, y-7, "#2f4b5a")
        p.rect(x+14, y-14, x+19, y-7, "#2f4b5a")
    for x in range(10, LEFT_QUAY_X, 46):
        p.oval(x-7, 220, x+7, 234, "#6f9f7a")
    p.text(70, 118, "LISBOA", 10, "#3c5d61", True)
    # Almada: the cliff with Cristo Rei above the river.
    draw_bank(p, ALMADA_RIDGE, RIGHT_QUAY_X, 660, "#b7c08a")
    for x, y in ((532, 222), (556, 214), (586, 190), (620, 176)):
        p.oval(x-9, y-9, x+9, y+7, "#6f9f7a")
    for x in (522, 548):
        p.rect(x, 212, x+20, 233, "#f2e3c6")
        p.poly((x-2, 212, x+10, 204, x+22, 212), "#c8693f")
    base = ridge_y(ALMADA_RIDGE, 600)
    p.poly((590, base, 610, base, 605, base-38, 595, base-38), "#e9e3d3")
    p.rect(598, base-68, 602, base-38, "#f1ece0")
    p.rect(588, base-62, 612, base-58, "#f1ece0")
    p.oval(596, base-76, 604, base-67, "#f1ece0")
    p.text(590, 228, "ALMADA", 10, "#4f6a3e", True)
    # The river, and the two ferry piers built out from the quays.
    for band in range(6):
        top_y = WATER_Y+12+band*(SCENE_H-WATER_Y-12)/6
        color = ("#6fb3c2", "#62a7b8", "#579dae", "#4d92a4", "#45889a", "#3d7f91")[band]
        p.rect(0, top_y, SCENE_W, top_y+(SCENE_H-WATER_Y-12)/6+1, color)
    p.rect(0, WATER_Y, SCENE_W, WATER_Y+12, "#7fbcc8")
    for x, side in ((LEFT_PIER_X, -1), (RIGHT_PIER_X, 1)):
        left, right = (-20, x+30) if side < 0 else (x-30, 660)
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
