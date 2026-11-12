"""Tram ticket selection, sharing the game's existing modal pause slot."""
import tkinter as tk

from tram import TRAM_FARE, TRAM_STOPS, nearby_stop, ride_tram


def open_tram(game):
    if getattr(game, "profile_window", None) is not None:
        return None
    origin = nearby_stop(game.town.x, game.town.y)
    if origin is None:
        game.town.message = "Walk to a TRAM stop and press E to buy a ticket."
        return None
    root = game.root
    game.keys.clear()
    panel = tk.Toplevel(root)
    game.profile_window = panel
    panel.title("Elétrico · Tram tickets")
    panel.transient(root)
    panel.configure(bg="#142c36")
    panel.resizable(False, False)
    body = tk.Frame(panel, bg="#142c36", padx=24, pady=18)
    body.pack(fill="both", expand=True)
    tk.Label(body, text="YELLOW TRAM", bg="#142c36", fg="#f2cd75",
             font=("Segoe UI", 17, "bold")).pack(anchor="w")
    tk.Label(body, text=f"From {origin.name} · Any other stop ${TRAM_FARE}", bg="#142c36", fg="#f4ead2",
             font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 6))
    tk.Label(body, text="Choose a district for an express trip along Lisbon's north bank.\n"
                       "Your cargo and owned vehicle remain available after the trip.",
             bg="#142c36", fg="#c8d6d5", justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12))
    selected = tk.StringVar(panel, next(stop.name for stop in TRAM_STOPS if stop != origin))
    for stop in TRAM_STOPS:
        current = stop == origin
        tk.Radiobutton(body, text=stop.name+("  · current stop" if current else ""), variable=selected,
                       value=stop.name, state="disabled" if current else "normal",
                       bg="#142c36", fg="#f4ead2", activebackground="#284958", activeforeground="#ffffff",
                       selectcolor="#284958", anchor="w", font=("Segoe UI", 11), padx=4, pady=4).pack(fill="x")
    status = tk.StringVar(panel, f"Cash ${game.town.cash:,} · Fare ${TRAM_FARE}")
    tk.Label(body, textvariable=status, bg="#142c36", fg="#f6d69a", justify="left", wraplength=470,
             font=("Segoe UI", 10)).pack(anchor="w", pady=(12, 8))
    controls = tk.Frame(body, bg="#142c36")
    controls.pack(fill="x")

    def clear_pause(event=None):
        if event is None or event.widget is panel:
            if game.profile_window is panel:
                game.profile_window = None
            game.keys.clear()

    def close(event=None):
        clear_pause()
        try:
            panel.grab_release()
            panel.destroy()
            if root.winfo_exists():
                root.focus_set()
        except tk.TclError:
            pass
        return "break"

    def travel(event=None):
        if ride_tram(game.town, selected.get()):
            game.world_view.camera.follow(game.town.x, game.town.y, snap=True)
            game.world_view.last_scroll = None
            game.world_view.last_navigation_update = 0
            return close()
        status.set(game.town.message)
        return "break"

    tk.Button(controls, text=f"Pay ${TRAM_FARE} & ride", command=travel, bg="#e2bd68", fg="#172c33",
              activebackground="#f0d591", padx=16, pady=8, relief="flat", cursor="hand2",
              font=("Segoe UI", 11, "bold")).pack(side="right")
    tk.Button(controls, text="Close", command=close, padx=14, pady=8).pack(side="right", padx=(0, 10))
    panel.bind("<Return>", travel)
    panel.bind("<Escape>", close)
    panel.bind("<Destroy>", clear_pause)
    panel.protocol("WM_DELETE_WINDOW", close)
    panel.update_idletasks()
    width, height = panel.winfo_reqwidth(), panel.winfo_reqheight()
    x = max(0, root.winfo_rootx()+(root.winfo_width()-width)//2)
    y = max(0, root.winfo_rooty()+(root.winfo_height()-height)//2)
    panel.geometry(f"{width}x{height}+{x}+{y}")
    panel.grab_set()
    panel.focus_set()
    return panel
