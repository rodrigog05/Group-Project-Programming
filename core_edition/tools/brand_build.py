"""Add the splash, responsive canvas and fullscreen control to Pygbag's page."""

import base64
import io
import re
import sys
from pathlib import Path

import pygame

GAME = Path(__file__).resolve().parents[1] / "game"
sys.path.insert(0, str(GAME))

from view import H, W

from menu_scene import LisbonMenuScene

STYLE = """
<style>
  body {
    --game-width: min(100vw, calc(100dvh * GAME_WIDTH / GAME_HEIGHT));
    overflow: hidden;
    background: #101f28 !important;
  }
  #canvas {
    position: fixed;
    inset: 0;
    margin: auto;
    width: var(--game-width);
    height: calc(var(--game-width) * GAME_HEIGHT / GAME_WIDTH);
    outline: none;
  }
  #core-fullscreen {
    position: fixed;
    top: 6px;
    right: 8px;
    z-index: 6;
    min-height: 32px;
    padding: 4px 10px;
    border: 1px solid #ffc66c;
    border-radius: 4px;
    color: #ffc66c;
    background: #16303a;
    font: 600 14px system-ui, sans-serif;
    cursor: pointer;
  }
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
<button id="core-fullscreen" type="button" hidden>Fullscreen</button>
<script>
  const fullscreenButton = document.getElementById("core-fullscreen");
  function updateFullscreenButton() {
    fullscreenButton.textContent = document.fullscreenElement
      ? "Exit Fullscreen" : "Fullscreen";
  }
  if (document.fullscreenEnabled && document.documentElement.requestFullscreen) {
    fullscreenButton.hidden = false;
    document.addEventListener("fullscreenchange", updateFullscreenButton);
    fullscreenButton.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await document.documentElement.requestFullscreen();
        }
        document.getElementById("canvas").focus({preventScroll: true});
      } catch (error) {
        console.warn("Foundry Town fullscreen unavailable", error);
      }
    });
  }
</script>
"""


def brand_build():
    path = GAME / "build/web/index.html"
    html = path.read_text(encoding="utf-8")
    if 'id="core-splash"' in html:
        return
    if "</head>" not in html or "<body>" not in html:
        raise ValueError("Expected the Pygbag HTML page")
    if "ume_block : 0," not in html:
        raise ValueError(
            "Build with --ume_block 0 so the silent game starts automatically"
        )
    # SDL keeps its framebuffer size. CSS owns only the display size and position.
    if "user_canvas_managed : 0," not in html:
        raise ValueError("Expected Pygbag's default canvas configuration")
    html = html.replace("user_canvas_managed : 0,", "user_canvas_managed : 1,", 1)
    # Core uses localStorage. This unused legacy script blocks parsing the
    # splash markup below it until the CDN request finishes.
    html = re.sub(r'<script src="[^"]*/browserfs\.min\.js"></script>\s*', "", html)
    scene = pygame.Surface((W, H))
    LisbonMenuScene(scene.get_size()).draw(scene, 0)
    image = io.BytesIO()
    pygame.image.save(scene, image, "splash.png")
    data = base64.b64encode(image.getvalue()).decode("ascii")
    style = STYLE.replace("GAME_WIDTH", str(W)).replace("GAME_HEIGHT", str(H))
    html = html.replace("</head>", style.replace("SCENE", data) + "</head>", 1)
    path.write_text(html.replace("<body>", "<body>" + SPLASH, 1), encoding="utf-8")


if __name__ == "__main__":
    brand_build()
