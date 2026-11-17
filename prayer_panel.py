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
    # Bent legs and clasped hands make the player's kneeling posture explicit.
    canvas.create_line(242, 303, 227, 339, 273, 347, fill=outfit, width=22)
    canvas.create_line(270, 346, 284, 346, fill="#3c3431", width=10)
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

    def render(event):
        canvas.delete("all")
        draw_prayer(canvas, game.town.profile, BODY_COLORS, HAIR_COLORS, COSTUMES)
        scale_x, scale_y = event.width / 640, event.height / 400
        canvas.scale("all", 0, 0, scale_x, scale_y)
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                canvas.itemconfigure(item, font=("Segoe UI", max(8, round(13 * min(scale_x, scale_y))), "bold"))

    canvas.bind("<Configure>", render)

    def close():
        game.keys.clear()
        game.profile_window = None
        panel.destroy()
        game.root.focus_set()

    tk.Button(panel, text="Return to Lisboa  ·  Esc", command=close).place(
        relx=0.02, rely=0.03, anchor="nw")
    panel.bind("<Escape>", lambda event: close())
    panel.focus_set()
