# Foundry Town Core Edition

The public Core Edition shows a Lisbon splash while the runtime downloads and then opens the animated start menu automatically. [Play Core Edition](https://rodrigog05.github.io/Group-Project-Programming/core-menu/)

The browser build on this branch uses a 1280 × 720 layout and fits the game to the window at 16:9. Use **Fullscreen** in the top-right corner to enter browser fullscreen. Use **Exit Fullscreen** or press **Esc** to return to the window.

Start outside Goldenfield Farm with $60 and a 12-slot bag. Buy wheat, walk east to Sunrise Bakery, make bread, then walk west to Daily Bread Market to sell it. Four units of wheat cost $16. Four loaves sell for $56. Completing that trip gives you exactly $100, enough for the warehouse bag upgrade.

## Open the tested browser build

On Windows with Python installed, download [the web ZIP](dist/foundry-town-core-web.zip) and open PowerShell in the folder containing the ZIP. Run these commands:

```powershell
Expand-Archive .\foundry-town-core-web.zip -DestinationPath .\foundry-core-preview
py -m http.server 8000 --bind 127.0.0.1 --directory .\foundry-core-preview
```

Open **http://localhost:8000/** in Chrome or Edge. When the menu appears, choose **New Game** to start, **Continue** to resume a save, or **Rules & How to Play** for the controls. Starting a new game asks for confirmation when a save exists. Keep PowerShell open while playing. The browser downloads the Python WebAssembly runtime from Pygbag on first load. Use the same browser and address each time to keep your save.

## Controls and routes

- **WASD or arrows** walk. Both bridges have pedestrian crossings.
- **E** opens a nearby store. Press it again for the action shown. At a supplier, **Q** buys up to four units, limited by cash and space.
- At a workshop, **E** starts a batch with all matching materials. Press **E** when the timer finishes to collect it. Walk to that route's market and press **E** inside to sell your finished goods.
- **P or I** opens the route guide and inventory. Select route **1–4**, then **A**, **B** or **C** to track its supplier, workshop or market. **U** tracks the warehouse. **Esc** leaves a store or closes the guide. On-screen buttons also operate the menus.

| Route | Buy here | Produce here | Sell here | Unit cost / sale | Batch time |
|---|---|---|---|---|---|
| 1. Tools | Iron Hill Mine | Ironworks | Tool Market | $5 / $18 | 5 s |
| 2. Furniture | Pine Mill | Oak Workshop | Home Market | $7 / $26 | 7 s |
| 3. Pottery | Redbank Clay Pit | Ember Kiln | The Pottery Shop | $6 / $22 | 6 s |
| 4. Bread | Goldenfield Farm | Sunrise Bakery | Daily Bread Market | $4 / $14 | 4 s |

Each workshop holds one batch. A batch reserves room in the bag until collected. At Foundry Warehouse, $100 permanently raises capacity from 12 to 24. The map retains original artwork for other landmarks as scenery. The 12 route businesses and warehouse are interactive.

## Team architecture guide

The playable source lives in `core_edition/game/`. Pygbag starts `main.py`. The runtime modules work without importing the desktop game or the earlier prototype.

| File under game/ | Responsibility |
|---|---|
| main.py | Start pygame-ce, read events, handle focus and give the browser time between frames. |
| controller.py | Turn input into walking, entering a shop, selecting a destination or trading. Schedule saves. |
| catalog.py | Define store names, coordinates, prices, batch times and which door the player can enter. |
| world.py | Apply movement speed, solid building outlines, river boundaries and both bridge paths. |
| economy.py | Own the player's cash, inventory, orders and upgrade. Validate each transaction. |
| view.py | Draw the scrolling map, animated builder, illustrated stores, money, route guide and buttons. |
| menu_scene.py | Draw the desktop menu's Lisbon backdrop with Pygame shapes and animate its traffic, boats and lighting. |
| saves.py | Encode and validate versioned JSON, including position, money, capacity and active orders. |
| storage.py | Read and write the Core save through the browser's localStorage and report failures in game. |

The Lisbon map, walking sprite sheet and 12 interior images are packaged in `game/assets/`. Core uses the existing game's businesses, map coordinates, trading values and Pygbag delivery format. Inventory, production, movement, interaction and persistence run in small Core modules. A bake of the map keeps the desktop renderer and excluded systems out of the runtime.

For a price or timer change, edit the route in `catalog.py` and update the matching test. For a movement change, start with `world.py` and the bridge tests. Keep route IDs in their current order because inventory and orders use those indices in saves. A change to those IDs or the saved fields needs a save migration. UI text and layout belong in `view.py`.

## How saving works

Core saves after shop actions, when movement keys are released, on focus loss, and every five active seconds. Local storage uses the key `foundry-town.core.v1`. Reloading restores the player's location, inventory, cash, upgrade and remaining production time. Production pauses away from the game. Desktop saves use a separate format. Clearing browser site data removes the Core save.

Save loading checks types, lengths, capacity, coordinates, schema version and order limits. An unreadable save stays intact while the current session can play. A storage failure shows a message. A player who controls their own browser can edit a local save.

## Build and test from source

From the repository root on branch `core-edition`, with Python 3.12 on Windows:

```powershell
py -3.12 -m venv core_edition/.venv
.\core_edition\.venv\Scripts\Activate.ps1
python -m pip install -r core_edition/requirements.txt
python -m unittest discover -s core_edition/tests
python -m unittest browser_game.test_town
python -m pygbag --build --no_opt --ume_block 0 --title "Foundry Town Core Edition" core_edition/game
python core_edition/tools/brand_build.py
python core_edition/tools/check_build.py
python -m http.server 8000 --bind 127.0.0.1 --directory core_edition/game/build/web
```

On macOS or Linux, create the environment with `python3.12 -m venv core_edition/.venv` and activate with `source core_edition/.venv/bin/activate`. The remaining commands are the same. To run the browser regression, keep that server running and use a second terminal with the same virtual environment:

```sh
python -m pip install playwright bandit
python -m playwright install chromium
python core_edition/tests/browser_play.py http://localhost:8000/
python -m bandit -qr core_edition/game
```

The three unit-test modules cover trading, movement, and saves. The browser test opens a fresh profile and drives the packaged game with real key events. The release checker compares every member of both generated game archives to the reviewed source and images and checks the runtime import list.

## Review checklist

- [x] Chromium rendered the Lisbon menu in daylight and at night. Browser and unit tests covered the menu's save and confirmation behavior.
- [x] Chromium fit the canvas at 1366 × 768, 1920 × 1080, and 720 × 500. Tests covered scaled mouse clicks, fullscreen entry and exit, keyboard movement, and save reload. A separate headed Chromium check verified native Escape from fullscreen.

- [x] Chromium played the wheat-to-bread route on foot, reloaded mid-batch, collected bread and sold it.
- [x] Chromium bought, produced, collected and sold tools, furniture and pottery using the store UI. The test placed the player at each doorway for these three routes.
- [x] Chromium walked across the west bridge and confirmed that a second upgrade purchase costs nothing and the first purchase survives reload.
- [x] Unit tests crossed both bridges in both directions and found walkable paths from spawn to all 13 doorways. They also checked doorway approaches, inventory limits, invalid saves, and unavailable storage.
- [x] Bandit reported zero findings in the Core runtime. PyPI listed zero advisories for the pinned Pygbag and pygame-ce versions and for the pygame-ce wheel used by WebAssembly at test time. Both game archives matched their source and asset files.
- [ ] Direct access to Pygbag's usual CDN from this environment was restricted. Browser testing used a mirror of the upstream runtime files. The loader's optional BrowserFS request failed. Core saving uses localStorage.
- [ ] Safari, Firefox, touch-only controls and live GitHub Pages hosting have not been verified. Playing requires a keyboard.

## Publishing after team approval

The ZIP contains the four generated web files at its root and an empty `.nojekyll`. The relative game and asset paths work beneath a repository URL. If the team approves replacing the existing public game, deploy the reviewed ZIP contents to the root of the existing Pages branch and verify the existing project URL in a fresh browser. If both editions should have public URLs, put Core in a `core/` directory on Pages instead. The current branch has no automatic deployment step. Merging the source into main later would add the separate `core_edition/` directory alongside the desktop game.
