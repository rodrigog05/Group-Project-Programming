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
            imports = (
                [node.module]
                if isinstance(node, ast.ImportFrom)
                else [a.name for a in node.names]
            )
            if any(i.split(".")[0] in omit for i in imports):
                continue
        start = min(
            [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
        )
        result.extend(source[start - 1 : node.end_lineno])
        result.append("\n")
    return "".join(result)


def prepare():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in (
        "journal_lore journal_market journal_recipes lisbon_scene lisbon_landmarks vehicles "
        "tourism exchange innovation logistics logistics_paths contracts businesses ferry guidance wayfinding vehicle_art casino_interior menu_scene casino_art fountain_water business_signs logistics_view"
    ).split():
        shutil.copyfile(ROOT / f"{name}.py", OUTPUT / f"{name}.py")
    modules = {
        "tycoon": extract(
            "tycoon",
            stop="Game",
            omit=(
                "tkinter",
                "saves",
                "soundtrack",
                "menu_scene",
                "living_world",
                "concurrent",
                "show_rules",
                "configure_display_dpi",
                "market_start",
            ),
        ),
        "interiors": extract("interiors", stop="open_interior", omit=("tkinter",)),
        "places_menu": extract("places_menu", stop="open_places", omit=("tkinter",)),
        "actors": extract(
            "living_world",
            stop="LivingWorld",
            omit=(
                "tkinter",
                "windows_canvas",
                "logistics_view",
                "business_signs",
                "vehicle_art",
            ),
        ),
        "ferry_scene": extract("ferry_panel", stop="open_ferry", omit=("tkinter",)),
        "garage": extract("garage_panel", stop="open_garage", omit=("tkinter",)),
        "prayer": extract("prayer_panel", stop="open_prayer", omit=("tkinter",)),
    }
    # Reuse the player-facing descriptions/calculations, excluding desktop widgets.
    for name, stop in (
        ("research_panel", "_write"),
        ("exchange_panel", "_write"),
        ("journal_panel", "_write"),
        ("contracts_panel", "ContractsPanel"),
        ("businesses_panel", "BusinessesPanel"),
        ("logistics_panel", "LogisticsPanel"),
    ):
        source = extract(
            name, stop=stop, omit=("tkinter", "research_panel", "webbrowser")
        )
        if name in ("contracts_panel", "businesses_panel", "logistics_panel"):
            source = (
                "from research_panel import duration_text, quantity_value\n" + source
            )
        modules[name] = source
    board_class = next(
        n
        for n in ast.parse(
            (ROOT / "exchange_panel.py").read_text(encoding="utf-8")
        ).body
        if getattr(n, "name", None) == "ExchangePanel"
    )
    draw_board = next(
        n for n in board_class.body if getattr(n, "name", None) == "_draw_market_board"
    )
    modules["exchange_panel"] += "\n" + ast.unparse(draw_board) + "\n"
    tree = ast.parse((ROOT / "living_world.py").read_text(encoding="utf-8"))
    world = next(n for n in tree.body if getattr(n, "name", None) == "LivingWorld")
    methods = {"create_actors", "actor", "update_labels", "build_minimap", "label"}
    world.body = [n for n in world.body if getattr(n, "name", None) in methods]
    modules["world_art"] = "from actors import *\n" + ast.unparse(world) + "\n"
    game_tree = ast.parse((ROOT / "tycoon.py").read_text(encoding="utf-8"))
    game = next(n for n in game_tree.body if getattr(n, "name", None) == "Game")
    methods = (
        "wheel_state",
        "draw_casino_screen",
        "casino_key",
        "spin_wheel",
        "settle_spin",
    )
    casino = ast.ClassDef(
        name="CasinoTable",
        bases=[],
        keywords=[],
        decorator_list=[],
        body=[n for n in game.body if getattr(n, "name", None) in methods],
    )
    modules["casino_table"] = "from tycoon import *\n" + ast.unparse(casino) + "\n"
    for name, source in modules.items():
        (OUTPUT / f"{name}.py").write_text(source, encoding="utf-8")
    shutil.copytree(
        HERE / "game",
        OUTPUT,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("build", "__pycache__"),
    )
    for phase in ("day", "night"):
        name = f"world_100_{phase}.png"
        shutil.copyfile(ROOT / "assets" / name, OUTPUT / "assets" / name)
    return OUTPUT


if __name__ == "__main__":
    print(prepare())
