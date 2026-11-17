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
    # A peaceful depiction of Jesus beside the altar, facing the praying player.
    canvas.create_oval(412, 50, 502, 140, outline="#dfc17d", width=4)
    canvas.create_rectangle(450, 80, 464, 165, fill="#775137", width=0)
    canvas.create_rectangle(424, 102, 491, 114, fill="#775137", width=0)
    canvas.create_oval(435, 92, 478, 145, fill="#694533", width=0)
    canvas.create_oval(442, 99, 472, 135, fill="#dbab83", width=0)
    canvas.create_polygon(439, 139, 476, 139, 502, 300, 414, 300,
                          fill="#efe5cc", outline="#d3c4aa", width=2)
    canvas.create_polygon(470, 140, 480, 142, 493, 288, 468, 298,
                          fill="#a25445", width=0)
    canvas.create_line(440, 158, 422, 189, 401, 175, fill="#efe5cc", width=13)
    canvas.create_oval(393, 166, 406, 179, fill="#dbab83", width=0)
    canvas.create_line(449, 119, 452, 119, fill="#423229", width=2)
    canvas.create_line(463, 119, 466, 119, fill="#423229", width=2)
    canvas.create_polygon(446, 127, 457, 140, 468, 127, 458, 132, fill="#694533")
    canvas.create_rectangle(398, 305, 514, 324, fill="#d4c6a9", width=0)
    canvas.create_text(457, 37, text="Jesus Christ", fill="#f6e4b2", font=("Segoe UI", 13, "bold"))
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
    panel = game.profile_window = tk.Toplevel(game.root)
    panel.title("Mosteiro dos Jerónimos · Prayer")
    panel.transient(game.root)
    panel.resizable(False, False)
    panel.grab_set()
    canvas = tk.Canvas(panel, width=640, height=400, highlightthickness=0)
    canvas.pack()
    draw_prayer(canvas, game.town.profile, BODY_COLORS, HAIR_COLORS, COSTUMES)

    def close():
        game.keys.clear()
        game.profile_window = None
        panel.destroy()
        game.root.focus_set()

    tk.Button(panel, text="Return to Lisboa", command=close).pack(pady=10)
    panel.bind("<Escape>", lambda event: close())
    panel.protocol("WM_DELETE_WINDOW", close)
