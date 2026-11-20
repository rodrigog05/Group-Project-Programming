"""Optional desktop art refresh. Run on an unobscured desktop or a private Xvfb display."""
from pathlib import Path
import sys
import tkinter as tk
from PIL import ImageGrab

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import interiors
import garage_panel
import prayer_panel
from tycoon import Town, SITES, BODY_COLORS, HAIR_COLORS, COSTUMES

def main():
    town = Town()
    root = tk.Tk()
    root.overrideredirect(True)
    canvas = tk.Canvas(root, width=800, height=400, highlightthickness=0, bg=interiors.INK)
    canvas.pack()
    root.update()
    out = HERE / "game/assets/interiors"
    def capture(name, width=640):
        root.update()
        x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
        ImageGrab.grab((x, y, x+width, y+400)).convert("RGB").save(out / (name+".png"))
    for site in SITES:
        canvas.delete("all")
        painter = interiors.Painter(canvas)
        if site.role in interiors.INTERIOR_ROLES:
            interiors.draw_scene(painter, town, site)
            capture(f"{site.role.replace(' ', '_')}_{site.trade}")
        elif site.role == "GARAGE":
            garage_panel.draw_showroom(painter, town, site)
            capture(site.name, 800)
    canvas.delete("all")
    prayer_panel.draw_prayer(canvas, town.profile, BODY_COLORS, HAIR_COLORS, COSTUMES)
    capture("monastery")
    root.destroy()

if __name__ == "__main__":
    main()
