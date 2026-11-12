"""Build the expanded world's day/night caches; Pillow is build-time only."""
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from lisbon_scene import LisbonScene, WORLD_WIDTH, WORLD_BOTTOM
from render_lisbon import Painter
from tycoon import SITES


def build():
    painter = Painter(scale=1.5, world_size=(WORLD_WIDTH, WORLD_BOTTOM))
    scene = LisbonScene(SimpleNamespace(canvas=painter, label=painter.label), SITES)
    day = painter.image.copy()
    painter.make_night(scene)
    night = painter.image
    directory = Path(__file__).parent / "assets"
    for zoom in (100, 125, 150):
        size = round(WORLD_WIDTH*zoom/100), round(WORLD_BOTTOM*zoom/100)
        for phase, source in (("day", day), ("night", night)):
            source.resize(size, Image.Resampling.LANCZOS).save(directory/f"world_{zoom}_{phase}.png", optimize=True)
    print(f"Built expanded world: {WORLD_WIDTH} x {WORLD_BOTTOM}, three zoom levels, day/night")


if __name__ == "__main__":
    build()
