"""Check release contents against reviewed Core sources. Never extract an archive."""

import ast
import tarfile
import zipfile
from pathlib import Path

GAME = Path(__file__).resolve().parents[1] / "game"
MODULES = ["catalog", "controller", "economy", "main", "saves", "storage", "view", "world"]
IMAGES = ["world_100_day.png", "builder.png"] + [
    f"{role}_{i}.png"
    for role in ("SUPPLIER", "FACTORY", "PUBLIC_SHOP")
    for i in range(4)
]
ALLOWED_IMPORTS = set(
    MODULES
    + ["asyncio", "dataclasses", "functools", "json", "math", "pathlib", "platform", "pygame", "sys", "time"]
)


def check():
    files = [GAME / f"{m}.py" for m in MODULES] + [
        GAME / "assets" / name for name in IMAGES
    ]
    expected = {
        "assets/" + p.relative_to(GAME).as_posix(): p.read_bytes() for p in files
    }
    for name in MODULES:
        for node in ast.walk(
            ast.parse((GAME / f"{name}.py").read_text(encoding="utf-8"))
        ):
            imports = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(n not in ALLOWED_IMPORTS for n in imports):
                raise ValueError(f"Unexpected runtime dependency in {name}: {imports}")
    web = GAME / "build/web"
    with zipfile.ZipFile(web / "game.apk") as archive:
        if sorted(archive.namelist()) != sorted(expected):
            raise ValueError("Unexpected files in APK")
        for name, data in expected.items():
            if archive.read(name) != data:
                raise ValueError(f"Stale APK member: {name}")
    with tarfile.open(web / "game.tar.gz") as archive:
        if sorted(archive.getnames()) != sorted(expected):
            raise ValueError("Unexpected files in tarball")
        for member in archive:
            if (
                not member.isfile()
                or member.size != len(expected[member.name])
                or archive.extractfile(member).read() != expected[member.name]
            ):
                raise ValueError(f"Unexpected tar member: {member.name}")
    index = (web / "index.html").read_text(encoding="utf-8")
    if (
        'platform.fopen("game.tar.gz"' not in index
        or not (web / "favicon.png").is_file()
    ):
        raise ValueError("Web entry point missing its relative game bundle or icon")
    print(
        f"Verified both archives: {len(MODULES)} Python modules and {len(IMAGES)} images; relative web entry point present."
    )


if __name__ == "__main__":
    check()
