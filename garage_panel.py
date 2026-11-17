"""Garage showroom: the vehicles on display with their prices and specifications.

Buying still goes through Town.purchase_vehicle, so prices and the rules about
cargo and reserved orders are unchanged.
"""
import time
import tkinter as tk

from interiors import FONT, IS_MAC, INK, OPEN_GRACE_SECONDS, Painter, bubble, counter, vendor
from vehicles import VEHICLES

SCENE_W, SCENE_H = 640, 400
SHOWROOM_X = (95, 255, 415)  # Turntable centres for the three vehicles
FLOOR_Y = 312
SALES_LOOK = {"skin": "#c78d64", "hair": "#1f1b1a", "shirt": "#2f4b5a", "apron": None, "hat": "cap", "cap": "#86caff"}


def showroom_backdrop(p, name):
    p.rect(0, 0, SCENE_W, SCENE_H, "#d9dde0")
    for x in range(0, SCENE_W, 80):
        p.rect(x, 0, x+6, 230, "#c3c9cd")
    # Roller door with daylight and the street outside.
    p.rect(470, 40, 630, 230, "#9fc9da")
    for y in range(40, 120, 8):
        p.line((470, y, 630, y), "#7d8a8c", 2)
    p.rect(470, 200, 630, 230, "#8f9497")
    p.rect(460, 34, 640, 40, "#5e6b70")
    # Shop sign and ceiling spotlights.
    # The shop's name board sits left of the salesperson's speech bubble.
    p.rect(14, 16, 300, 48, "#1f2a30")
    p.text(157, 32, name.upper(), 12, "#f6e7b4", True)
    for x in SHOWROOM_X:
        p.line((x, 0, x, 64), "#3a3a3a", 1)
        p.poly((x-10, 64, x+10, 64, x+16, 78, x-16, 78), "#2f3d45")
        p.poly((x-16, 78, x+16, 78, x+60, 300, x-60, 300), "#eef1f0")
    p.rect(0, 230, SCENE_W, SCENE_H, "#b8bec2")
    for x in range(-40, SCENE_W+40, 60):
        p.line((x, 230, x-60, SCENE_H), "#aab0b4", 1)
    p.rect(0, 228, SCENE_W, 232, "#8f9497")
    # Tools on a wall board.
    p.rect(20, 70, 50, 200, "#7a5a3b")
    for y in (90, 120, 150, 180):
        p.line((26, y, 44, y-8), "#9aa3a6", 3)


def price_card(p, x, ride, town, key, number):
    """Price tag above a vehicle: price, trunk, total cargo and speeds."""
    current = town.vehicle == key
    left, top, right, bottom = x-72, 98, x+72, 214
    p.rect(left+3, top+3, right+3, bottom+3, "#9aa3a6")
    p.rect(left, top, right, bottom, "#fffaf0", outline="#f2c230" if current else "#3a3a3a", width=3 if current else 1)
    p.text(x, top+14, ride.label.upper(), 10, INK, True)
    if current:
        p.rect(left+14, top+26, right-14, top+48, "#2e8b57")
        p.text(x, top+37, "YOUR RIDE", 11, "#f6efe1", True)
    else:
        p.text(x, top+37, f"${ride.price:,}", 16, "#b8432f", True)
    p.text(x, top+60, f"Trunk +{ride.trunk}  ·  {town.bag_size+ride.trunk} cargo", 8, "#3a3a3a")
    p.text(x, top+76, f"Road speed {ride.road_speed}", 8, "#3a3a3a")
    p.text(x, top+90, f"Off-road {ride.offroad_speed}", 8, "#3a3a3a")
    p.text(x, top+106, "Your current ride" if current else f"Click or press {number}", 7,
           "#2e8b57" if current else "#6b7d6c", True)
    return left, top, right, bottom


def draw_vehicle(canvas, key, x, town, scale=1.65):
    """Draw a vehicle from the game's own artwork, centred on its turntable."""
    from tycoon import BODY_COLORS, COSTUMES
    from vehicle_art import draw_player_vehicle
    previous = set(canvas.find_withtag("player"))
    draw_player_vehicle(canvas, key, 1, town.profile, BODY_COLORS, COSTUMES)
    items = [item for item in canvas.find_withtag("player") if item not in previous]
    for item in items:
        canvas.dtag(item, "player")
        canvas.addtag_withtag(f"showcar_{key}", item)
    canvas.scale(f"showcar_{key}", 0, 0, scale, scale)
    bbox = canvas.bbox(f"showcar_{key}")
    if bbox:
        canvas.move(f"showcar_{key}", x-(bbox[0]+bbox[2])/2, FLOOR_Y-bbox[3])


def draw_showroom(p, town, site):
    """Draw the whole showroom. Returns the speech item and clickable card areas."""
    showroom_backdrop(p, site.name)
    cards = []
    for number, (x, (key, ride)) in enumerate(zip(SHOWROOM_X, VEHICLES.items()), start=1):
        p.oval(x-70, FLOOR_Y-12, x+70, FLOOR_Y+16, "#8f9497")
        p.oval(x-64, FLOOR_Y-10, x+64, FLOOR_Y+10, "#d6dadc")
        draw_vehicle(p.c, key, x, town)
        cards.append((price_card(p, x, ride, town, key, number), key))
    vendor(p, 575, 330, SALES_LOOK)
    counter(p, 510, 330, SCENE_W, ("#e9eef0", "#9aa6aa", "#5e6b70"))
    speech = bubble(p, 316, 10, 630, 80, 560, 206)
    return speech, cards


def greeting(town):
    ride = VEHICLES.get(town.vehicle)
    if ride is None:
        return "Tired of walking? The bridges are for vehicles only. Pick a ride and I'll hand you the keys!"
    return f"How's the {ride.label.lower()} running? Trade up for a bigger trunk any time."


def open_garage(game, site):
    """Show the garage showroom. 1/2/3 or clicking a card buys that vehicle; Esc leaves."""
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
    state = {"reply": greeting(town), "cards": [], "scale": 1, "offset": (0, 0),
             "opened": time.monotonic(), "held": {"e"}, "timer": None, "size": None}

    def close():
        if state["timer"] is not None:
            panel.after_cancel(state["timer"])
        game.keys.clear()
        game.interior_open = False
        game.profile_window = None
        panel.destroy()
        game.root.focus_set()

    def buy(key):
        town.purchase_vehicle(key)
        state["reply"] = town.message
        redraw()

    def fleet():
        close()
        game.open_deliveries()

    def button(text, command, primary=False):
        options = dict(text=text, command=command, font=(FONT, 11, "bold"), padx=12, pady=6)
        if not IS_MAC:
            options.update(bg="#f2c230" if primary else "#d4c6a9", fg="#252c31", relief="flat",
                           activebackground="#ffd68f" if primary else "#e5d9bd", cursor="hand2")
        tk.Button(footer, highlightbackground="#252c31", **options).pack(side="right", padx=(8, 0))

    button("Leave  ·  Esc", close)
    button("Delivery fleet", fleet)
    for number, (key, ride) in reversed(list(enumerate(VEHICLES.items(), start=1))):
        button(f"{ride.label}  ·  {number}", lambda key=key: buy(key), primary=True)

    def redraw():
        if state["size"] is None:
            return
        width, height = state["size"]
        canvas.delete("all")
        painter = Painter(canvas)
        speech, cards = draw_showroom(painter, town, site)
        canvas.itemconfigure(speech, text=state["reply"])
        scale = min(width/SCENE_W, height/SCENE_H)
        offset = ((width-SCENE_W*scale)/2, (height-SCENE_H*scale)/2)
        state["scale"], state["offset"], state["cards"] = scale, offset, cards
        canvas.scale("all", 0, 0, scale, scale)
        canvas.move("all", *offset)
        for item, (size, wrap, bold) in painter.sizes.items():
            canvas.itemconfigure(item, font=(FONT, max(6, round(size*scale)), "bold" if bold else "normal"),
                                 width=wrap*scale)
        ride = next((value for key, value in VEHICLES.items() if key == town.vehicle), None)
        wallet.configure(text=f"Cash ${town.cash:,}   ·   {ride.label if ride else 'On foot'}   ·   "
                              f"{town.carry_capacity} cargo slots")

    def resize(event):
        state["size"] = (event.width, event.height)
        redraw()

    def click(event):
        scale, (offset_x, offset_y) = state["scale"], state["offset"]
        x, y = (event.x-offset_x)/scale, (event.y-offset_y)/scale
        for (left, top, right, bottom), key in state["cards"]:
            # The card and the vehicle beneath it are both clickable.
            if left <= x <= right and top <= y <= FLOOR_Y+16:
                buy(key)
                return

    def key_down(event):
        key = event.keysym.lower()
        if key == "escape":
            close()
            return
        if key in state["held"] or time.monotonic()-state["opened"] < OPEN_GRACE_SECONDS:
            state["held"].add(key)
            return
        state["held"].add(key)
        if key in ("1", "2", "3"):
            buy(list(VEHICLES)[int(key)-1])
        elif key == "l":
            fleet()

    def key_up(event):
        state["held"].discard(event.keysym.lower())

    canvas.bind("<Configure>", resize)
    canvas.bind("<Button-1>", click)
    panel.bind("<KeyPress>", key_down)
    panel.bind("<KeyRelease>", key_up)
    panel.focus_set()
    return panel
