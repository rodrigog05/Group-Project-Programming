"""Assemble a Pygbag source directory from the desktop rules and web frontend."""
import ast
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "build/game"


def extract(module, *, omit=(), stop=None, names=None):
    source = (ROOT / f"{module}.py").read_text(encoding="utf-8").splitlines(True)
    result = []
    for node in ast.parse("".join(source)).body:
        name = getattr(node, "name", None)
        if name == stop and stop is not None:
            break
        if names is not None and name not in names:
            continue
        if name in omit:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            if any(i.split(".")[0] in omit for i in imports):
                continue
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        result.extend(source[start-1:node.end_lineno])
        result.append("\n")
    return "".join(result)


def prepare():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ("journal_lore journal_market journal_recipes lisbon_scene lisbon_landmarks vehicles "
                 "tourism exchange innovation logistics logistics_paths contracts businesses ferry guidance wayfinding").split():
        shutil.copyfile(ROOT / f"{name}.py", OUTPUT / f"{name}.py")
    modules = {
        "tycoon": extract("tycoon", stop="Game", omit=("tkinter", "saves", "soundtrack", "menu_scene",
            "living_world", "concurrent", "show_rules", "configure_display_dpi", "market_start")),
        "interiors": extract("interiors", stop="open_interior", omit=("tkinter",)),
        "places_menu": extract("places_menu", stop="open_places", omit=("tkinter",)),
        "actors": extract("living_world", stop="LivingWorld", omit=("tkinter", "windows_canvas", "logistics_view",
            "business_signs", "vehicle_art")),
        "prayer": extract("prayer_panel", stop="draw_prayer", omit=("tkinter",)),
    }
    tree = ast.parse((ROOT / "living_world.py").read_text(encoding="utf-8"))
    world = next(n for n in tree.body if getattr(n,"name",None)=="LivingWorld")
    routes = next(n for n in world.body if getattr(n,"name",None)=="create_actors")
    modules["routes"] = ("from actors import (random, WORLD_WIDTH, WORLD_BOTTOM, RIVER_TOP, RIVER_BOTTOM, "
                         "south, ROAD_EXCLUSIONS, SOUTH_PARK_BOUNDS, tunnel_covers_y, CAR_SPEED_RANGE, bridge_center, FERRY_PIERS)\n"
                         + ast.unparse(routes) + "\n")
    for name, source in modules.items():
        (OUTPUT / f"{name}.py").write_text(source, encoding="utf-8")
    shutil.copytree(HERE / "game", OUTPUT, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("build", "__pycache__"))
    for phase in ("day", "night"):
        name = f"world_100_{phase}.png"
        shutil.copyfile(ROOT / "assets" / name, OUTPUT / "assets" / name)
    return OUTPUT


if __name__ == "__main__":
    print(prepare())
