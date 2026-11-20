"""Add the Foundry Town splash to a generated Pygbag page."""

import base64
import io
import sys
from pathlib import Path

import pygame

GAME = Path(__file__).resolve().parents[1] / "game"
sys.path.insert(0, str(GAME))

from menu_scene import LisbonMenuScene

STYLE = """
<style>
  #transfer, #infobox { visibility: hidden; }
  #core-splash {
    position: fixed;
    inset: 0;
    z-index: 1000000;
    display: grid;
    place-items: end center;
    box-sizing: border-box;
    padding: 0 1rem clamp(1rem, 7vh, 4rem);
    background: #16303a url("data:image/png;base64,SCENE") center / cover;
    color: #f2f7f6;
    font-family: system-ui, sans-serif;
    text-align: center;
  }
  #core-splash[hidden] { display: none; }
  #core-splash section {
    background: #16303a;
    border: 2px solid #ffc66c;
    box-shadow: 4px 4px #101f28;
    padding: 1.1rem clamp(1.25rem, 6vw, 3.5rem);
  }
  #core-splash h1 {
    color: #ffc66c;
    font-size: clamp(1.4rem, 5vw, 2.25rem);
    margin: 0;
  }
  #core-splash p { color: #6de0b3; margin: .6rem 0 0; }
</style>
"""

SPLASH = """
<div id="core-splash">
  <section aria-labelledby="core-title">
    <h1 id="core-title">FOUNDRY TOWN</h1>
    <p role="status">Loading Core Edition…</p>
  </section>
</div>
"""


def brand_build():
    path = GAME / "build/web/index.html"
    html = path.read_text(encoding="utf-8")
    if 'id="core-splash"' in html:
        return
    if "</head>" not in html or "<body>" not in html:
        raise ValueError("Expected the Pygbag HTML page")
    if "ume_block : 0," not in html:
        raise ValueError("Build with --ume_block 0 so the silent game starts automatically")
    scene = pygame.Surface((800, 540))
    LisbonMenuScene(scene.get_size()).draw(scene, 0)
    image = io.BytesIO()
    pygame.image.save(scene, image, "splash.png")
    data = base64.b64encode(image.getvalue()).decode("ascii")
    html = html.replace("</head>", STYLE.replace("SCENE", data) + "</head>", 1)
    path.write_text(html.replace("<body>", "<body>" + SPLASH, 1), encoding="utf-8")


if __name__ == "__main__":
    brand_build()
