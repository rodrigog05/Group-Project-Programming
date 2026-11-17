"""Monastery visit and a personalized prayer illustration."""
import math
import tkinter as tk

from lisbon_landmarks import LANDMARKS


def at_monastery(town):
    left, top, right, bottom = LANDMARKS[0].bounds
    # The monastery is solid scenery. Its public entrance is on the south side.
    return math.hypot(town.x - (left + right) / 2, town.y - (bottom + 16)) <= 40


def draw_prayer(canvas, profile, body_colors, hair_colors, costumes):
    canvas.create_rectangle(0, 0, 640, 400, fill="#363c42", width=0)
    for x in (45, 205, 405, 565):
        canvas.create_rectangle(x-16, 0, x+16, 340, fill="#c6bba4", width=0)
        canvas.create_arc(x-65, 5, x+65, 200, start=0, extent=180,
                          style="arc", outline="#e5d9bd", width=15)
    canvas.create_rectangle(0, 340, 640, 400, fill="#a79982", width=0)
    canvas.create_polygon(260, 400, 405, 310, 525, 310, 640, 400,
                          fill="#72594a", width=0)
    # The priest welcomes the praying player beside the altar.
    canvas.create_oval(440, 94, 474, 137, fill="#8e8b82", width=0)
    canvas.create_oval(442, 99, 472, 135, fill="#dbab83", width=0)
    canvas.create_arc(441, 95, 473, 122, start=0, extent=180,
                      fill="#8e8b82", outline="#8e8b82")
    canvas.create_polygon(439, 139, 476, 139, 502, 300, 414, 300,
                          fill="#242830", outline="#555b63", width=2)
    canvas.create_rectangle(451, 139, 464, 145, fill="#faf4e6", width=0)
    canvas.create_polygon(443, 148, 449, 149, 442, 261, 435, 259, fill="#9365aa")
    canvas.create_polygon(469, 148, 475, 148, 488, 259, 481, 261, fill="#9365aa")
    canvas.create_line(440, 158, 422, 189, 401, 175, fill="#242830", width=13)
    canvas.create_oval(393, 166, 406, 179, fill="#dbab83", width=0)
    canvas.create_line(449, 119, 452, 119, fill="#423229", width=2)
    canvas.create_line(463, 119, 466, 119, fill="#423229", width=2)
    canvas.create_line(452, 128, 461, 128, fill="#8d5745", width=1)
    canvas.create_rectangle(398, 305, 514, 324, fill="#d4c6a9", width=0)
    canvas.create_text(457, 37, text="Priest", fill="#f6e4b2", font=("Segoe UI", 13, "bold"))
    skin = body_colors[profile["body"]]
    hair = hair_colors[profile["hair"]]
    outfit, accessory = costumes[profile["costume"]]
    # Upright thighs meet grounded knees. Both shins extend behind the player.
    trousers = "#384958"
    canvas.create_oval(175, 341, 275, 354, fill="#827562", width=0)
    canvas.create_polygon(235, 296, 251, 298, 252, 337, 242, 346,
                          185, 343, 186, 329, 233, 331,
                          fill="#293946", outline="#25313a", width=2)
    canvas.create_polygon(247, 296, 263, 299, 265, 340, 254, 350,
                          198, 347, 199, 332, 246, 334,
                          fill=trousers, outline="#25313a", width=2)
    canvas.create_oval(247, 331, 265, 350, fill=trousers, width=0)
    canvas.create_line(202, 340, 245, 343, fill="#566b7b", width=2)
    canvas.create_polygon(185, 329, 185, 341, 168, 336, 169, 330,
                          179, 319, 186, 322, fill="#292b30")
    canvas.create_polygon(199, 332, 199, 347, 181, 342, 180, 336,
                          191, 322, 198, 326, fill="#34373c")
    canvas.create_polygon(227, 247, 257, 243, 269, 303, 231, 311,
                          fill=outfit, outline="#383434", width=2)
    canvas.create_oval(231, 205, 270, 252, fill=skin, outline="#383434", width=2)
    canvas.create_arc(231, 202, 270, 241, start=15, extent=210, fill=hair, outline=hair)
    canvas.create_rectangle(234, 246, 245, 253, fill=accessory, width=0)
    canvas.create_line(254, 266, 281, 282, 293, 250, fill=outfit, width=12)
    canvas.create_oval(287, 237, 298, 255, fill=skin, width=0)
    canvas.create_oval(297, 237, 305, 255, fill=skin, width=0)
    canvas.create_line(259, 225, 264, 227, fill="#383434", width=2)
    canvas.create_text(246, 375, text=profile["name"], fill="#fff2d5", font=("Segoe UI", 13, "bold"))


def open_prayer(game):
    if game.profile_window is not None:
        return
    from tycoon import BODY_COLORS, HAIR_COLORS, COSTUMES
    game.keys.clear()
    panel = game.profile_window = tk.Frame(game.root, bg="#363c42")
    panel.place(x=0, y=0, relwidth=1, relheight=1)
    panel.lift()
    canvas = tk.Canvas(panel, highlightthickness=0, bg="#363c42")
    canvas.pack(fill="both", expand=True)
    footer = tk.Frame(panel, bg="#252c31", padx=18, pady=12)
    footer.pack(fill="x")
    tk.Label(footer, text="Mosteiro dos Jerónimos", bg="#252c31", fg="#e5d9bd",
             font=("Segoe UI", 11)).pack(side="left")

    def render(event):
        canvas.delete("all")
        draw_prayer(canvas, game.town.profile, BODY_COLORS, HAIR_COLORS, COSTUMES)
        scale = min(event.width / 640, event.height / 400)
        canvas.scale("all", 0, 0, scale, scale)
        canvas.move("all", (event.width - 640 * scale) / 2, (event.height - 400 * scale) / 2)
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                canvas.itemconfigure(item, font=("Segoe UI", max(8, round(13 * scale)), "bold"))

    canvas.bind("<Configure>", render)

    def close():
        game.keys.clear()
        game.profile_window = None
        panel.destroy()
        game.root.focus_set()

    tk.Button(footer, text="Return to Lisboa  ·  Esc", command=close,
              bg="#d4c6a9", fg="#252c31", activebackground="#e5d9bd",
              relief="flat", padx=16, pady=8, font=("Segoe UI", 11, "bold")).pack(side="right")
    panel.bind("<Escape>", lambda event: close())
    panel.focus_set()
