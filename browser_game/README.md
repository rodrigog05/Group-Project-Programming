# Foundry Town in the browser

This keyboard prototype visits the Goldenfield Farm block of the desktop city. Follow the gold ring, then press E at the farm door to buy wheat. Each purchase takes $4 from your starting $60 and adds one wheat to your 12-slot bag. Two cars travel in opposite directions. The bakery is scenery in this version. Refreshing starts a new session.

## Run on Windows

From the original repository in PowerShell, with Python 3.12 installed:

```powershell
git switch browser-version
py -3.12 -m venv browser_game/.venv
browser_game/.venv/Scripts/python -m pip install -r browser_game/requirements.txt
browser_game/.venv/Scripts/python -m pygbag browser_game/game
```

Open http://localhost:8000 in a desktop browser. Click the page to start, then use WASD or the arrow keys. The initial load needs internet access for Pygbag's Python and pygame WebAssembly runtime. Stop the server with Ctrl+C. On Linux or macOS, create the environment with `python3.12` and use `browser_game/.venv/bin/python` for the remaining commands.

## Check the prototype

From the repository root, run `python -m unittest browser_game.test_town`. For a play check, watch the two cars pass, walk left from spawn until the buy prompt appears, and press E once. The display should change from $60 and zero wheat to $56 and one wheat. Hold a movement key against the farm wall, release it, then switch tabs and return. The character should stop at the wall and stay still when focus returns.

## Conversion plan for review

1. **City and movement.** The prototype crops the existing daytime world image at (1200, 450) and uses nine frames drawn from the original builder design. Expand using the day and night images in assets/, tiling them to stay within browser texture and memory limits. Bring over the camera and actor paths from living_world.py, terrain from lisbon_scene.py, and the building locations and collision bounds from tycoon.py. Replace Tk canvas calls, Windows graphics handles and window events with pygame surfaces and input. Test doors, bridges and ferries at every zoom.
2. **Economy and progression.** The slice adapts the desktop farm price, starting cash, inventory limit, walking speed, doorway reach and lane movement. Separate Town, Site, Trade and the snapshot functions in tycoon.py from the Tk imports before sharing them. Port one complete supplier → factory → shop route first. Then connect the existing business, contracts, logistics, innovation, exchange, tourism and vehicle models. Run their desktop tests and compare the same transactions in the browser.
3. **Menus and animation.** Reuse journal entries, recipes, business data, palettes and character art. Rebuild the start menu, HUD, interiors and panels such as businesses_panel.py with pygame controls. Bring over input shortcuts and animations, then check small screens, focus changes and frame pacing. Touch controls need their own pass.
4. **Audio.** Convert the existing saudade_do_tejo.wav to a browser-friendly compressed track, then use pygame.mixer after the first click. Replace the desktop playback backend in soundtrack.py. Check looping, volume and tab suspension.
5. **Saves.** Keep the desktop SQLite path in saves.py. Use a versioned JSON snapshot based on pack_save/unpack_save for the web. Through Pygbag's browser bridge, store a small snapshot under a namespaced localStorage key on completed trades and periodic checkpoints. Measure its size and write cost. Switch to IndexedDB if snapshots grow. Handle blocked storage, corrupted data, migrations and quota errors. Test reload and upgrades on the final origin. Private browsing and clearing site data can erase progress.
6. **Release checks.** Test a complete trading day, reload, menus and audio in desktop Chromium, Firefox and Safari. Measure initial download and frame times on a student laptop before growing the asset bundle. These are several separate implementation and testing milestones beyond the farm prototype.

## GitHub Pages after approval

Review the browser-version branch against main and merge through a pull request after approval. The browser code lives under browser_game/ and the desktop launcher keeps its existing entry point. Build from the repository root using the pinned environment:

```sh
python -m pygbag --build browser_game/game
```

Preview browser_game/game/build/web/ through a static HTTP server. Publish the **contents** of that directory, including index.html and both application archives, as the Pages artifact. Keep archive and image references relative so the repository subpath works. In the original repository select **Settings → Pages → GitHub Actions**. A future approved workflow can install the pinned requirements, build, upload the web directory with actions/upload-pages-artifact, and publish with actions/deploy-pages using the github-pages environment. The expected public URL is https://rodrigog05.github.io/Group-Project-Programming/ once that deployment succeeds. Check the deployed game, including the external runtime downloads, before sharing the link.
