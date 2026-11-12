# Foundry Town

Run **Play Foundry Town.cmd** on Windows or run `python tycoon.py` with Python 3 and Tkinter. No pip packages are required.

On macOS, double-click **Play Foundry Town (Mac)**. The other **Play Foundry Town** file is the Windows launcher and won't open on a Mac. Finder hides file extensions, so the two can look alike. The first time, macOS may block the launcher because it was downloaded. If it does, right-click it, choose **Open**, then confirm.

The game needs Python with Tk 8.6 or newer. Apple's built-in Python uses Tk 8.5, which shows a black window on recent macOS. Install a newer Python in either of these ways, and the launcher finds it automatically:

- With [uv](https://docs.astral.sh/uv/): `uv python install 3.12`
- From [python.org](https://www.python.org/downloads/macos/)

Move with **WASD** or the arrow keys. Walk to a colored doorstep and press **E** to interact. At a supplier, **Q** buys up to four units at once.

Follow the numbered building signs: **1 BUY RAW MATERIALS → 2 MAKE PRODUCTS → 3 SELL PRODUCTS**. Matching colors and numbers also appear on the minimap. Press **P** or click **Places** to browse suppliers, factories, markets, services and landmarks, with ingredients and instructions. Choose **Guide me here** to mark a doorstep and show a direction; river crossings point you toward a suitable bridge. Purple **2+3 MAKE + SELL** signs identify businesses where you craft, collect and sell at the same place.

Visit **Mosteiro dos Jerónimos** in Belém, **Castelo de São Jorge** in Alfama, **Torre de Belém** beside the western waterfront and **Praça do Comércio** with its open courtyard. They are drawn into the day/night scenery and marked on the minimap. Pine Mill, Redbank Clay Pit and Sunrise Bakery now occupy nearby eastern business plots; the directory always uses their current locations.

Monuments attract extra **local buyers each day**. Jerónimos adds 6 and Torre de Belém adds 3 for Pastéis de Belém; Praça do Comércio adds 4 each for Daily Bread Market, The Pottery Shop and Tool Market; Castelo adds another 3 for The Pottery Shop. The shop's `buyers` display includes its remaining tourists. Regular customers are served first, then the local tourist pool. These extra buyers refresh once per day, keep their remaining counts through saves, and cannot be spent at unrelated markets. Select a shop or landmark in Places to see its tourism effect.

At **Motorworks Garage**, press **E** to buy a ride. The active vehicle's trunk combines with your personal bag and warehouse upgrades:

| Vehicle | Price | Extra trunk slots | Total with starter bag | Road / off-road speed |
| --- | ---: | ---: | ---: | ---: |
| Motorcycle | $120 | 6 | 18 | 520 / 420 |
| Car | $240 | 48 | 60 | 690 / 510 |
| Delivery van | $360 | 108 | 120 | 620 / 430 |

The HUD shows **BAG + TRUNK**, total capacity and the active road-speed bonus. All purchases, factory collections and eggs use that combined capacity. Switching to a smaller trunk is blocked while your cargo and reserved orders exceed its limit. Older car saves gain the new trunk automatically without repeatedly adding slots.

For early travel, walk to a yellow **TRAM · E · $3** platform and press **E**. Choose any other stop for a **$3 express trip** between Belém, Alcântara, Baixa/Praça do Comércio, Alfama, Oriente, Marvila and Parque das Nações. Stops are marked **T** on the minimap and listed in Places → Services. Trips keep your cargo, vehicle and orders; fares count as expenses. The tram serves Lisbon's north bank, while the two bridges connect to Almada.

At the fullscreen start menu, choose your character's name, skin tone, hair, and outfit before starting or continuing.

The game fills the monitor in fullscreen and follows the window size in windowed mode. A smooth following camera shows a portion of the world at a readable scale, with the HUD and Settings fixed on screen. Press **M** to toggle the minimap and use **Settings → Camera zoom** to choose 1.0×, 1.25× or 1.5×.

The playable world is **2400 × 1600**, with closer districts and about one third less area than the first expanded map. Destinations include Marvila Timber Depot, Oriente Tool Market, Mercado das Nações, Quinta de Palmela, Cacilhas Garage and Armazém do Seixal. Their prices, daily demand and upgrades belong to the same town economy. Old saves keep their inventory and finances; a saved position that is no longer walkable returns to the starting street. New district positions also save normally.

The city now has 30 walking pedestrians, 12 road vehicles, four moving boats, water movement, the traveling elétrico and repair activity at the shipyard. There are 73 additional trees along waterfront paths, streets and parks, baked into the scenery. Windows uses cached map bitmaps and antialiased sprites through its built-in graphics APIs; it needs no additional Python packages. macOS, Linux and systems without that backend use the Tk renderer. The player and power-ups reuse their drawing objects, and the minimap refreshes at 10 Hz. The renderer targets **120 FPS**, using a high-resolution clock for both movement and frame pacing, with an actual FPS readout on the minimap. Settings can toggle traffic and ambient activity independently.

The Windows renderer keeps a bounded sprite cache, releases its bitmap contexts when the game closes, and pairs its active [high-resolution timer request](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod) with cleanup when returning to the menu or exiting.

Run `python benchmark_world.py --seconds 12` to measure a moving-camera day/night session at your current resolution. It focuses the game, allows one second for the window to warm up, then measures completed frames, day/night FPS, the lowest full one-second frame count and p95/p99 frame times while walking back and forth. Add `--zoom 1.0` or `--zoom 1.5` to check another view, or `--target-fps 90` for a temporary cap comparison. This benchmark uses temporary progress in memory.

Windows startup uses the monitor's physical resolution, including 1920 × 1080 displays with Windows scaling enabled. Settings shows the current display size. **Save and Close Game** writes progress to the configured save storage before exiting; a failed save keeps the game open so you can retry.

The Lisboa edition has a compact west-to-east layout inspired by Belém, Alcântara, Baixa/Chiado, Alfama/Graça and Oriente. The Tejo separates Lisbon from Almada. Both Ponte 25 de Abril and Ponte Vasco da Gama are usable crossings; Vasco da Gama connects the eastern waterfront beside Parque das Nações to the Seixal side of the map. Both crossings appear on the minimap. Precision Works is on the Almada bank. A yellow elétrico follows a fictional waterfront line between the neighborhoods. The architecture uses tiled roofs, azulejos, balconies and calçada, with antialiased scenery cached as PNGs for smooth movement. Geographic references come from [Turismo de Portugal](https://www.visitportugal.com/en/destinos/lisboa/73775) and [Visit Lisboa's Tagus route](https://www.visitlisboa.com/en/lisbon-stories/15-tagus-route/pois?page=2).

**Saudade do Tejo** is a bundled original 60-second fado-inspired guitar instrumental, composed for this game. It loops locally without an internet connection. Use the gold **Settings** button or **F1** to toggle music, change fullscreen mode, and read the rules. Windows uses its built-in WAV player; macOS uses `afplay`; Linux uses `paplay` or `aplay` when available. To rebuild assets, run `python compose_fado.py` for audio or `python render_world.py` for the expanded world (the scenery build requires Pillow; playing does not). `render_lisbon.py` can still rebuild the compact map previews.

| Route | Buy | Produce and collect | Sell |
| --- | --- | --- | --- |
| Metal | Iron ore at Iron Hill Mine for $5 | Tools at Ironworks | Tool Market customers pay $18 each |
| Timber | Timber at Pine Mill for $7 | Furniture at Oak Workshop | Home Market customers pay $26 each |
| Clay | Clay at Redbank Clay Pit for $6 | Pottery at Ember Kiln | The Pottery Shop customers pay $22 each |
| Farm | Wheat at Goldenfield Farm for $4 | Bread at Sunrise Bakery | Daily Bread Market customers pay $14 each |

Each unit of supply makes one finished good. Press **E** at the factory to drop off supplies, then press it again when the order is ready. Each public shop buys as many finished goods as its customers still want that day.

Foundry Precision Works is the Tier 2 factory. Bring one Tool and one Furniture to craft one Precision Machinery. It takes 12 seconds. Press **E** to collect it, then press **E** again to sell it at Precision Works.

**Pastéis de Belém** is in the Belém neighborhood. Buy Wheat at Goldenfield Farm with **E** (one) or **Q** (up to four), and Eggs with **F** (one) or **R** (up to four). Each egg costs $2. Bring **1 Wheat + 1 Egg** per pastel to the pastelaria and press **E** to bake all matching pairs. After eight seconds, press **E** to collect, then **E** again to sell. The base sale price is $24 per pastel, giving a base material cost of $6 and profit of $18. Stock occupies bag space, and baking orders reserve their pickup slots.

**Estaleiro do Tejo** is on the Almada waterfront, next to the repair dock. Bring **2 Timber + 2 Iron ore** and press **E** to accept a boat repair. After 20 seconds, return and press **E** to claim the agreed payment (base $100 against $24 of materials). Boat repairs are services, so boats do not occupy your bag. The quoted payment is fixed when the job starts, including across a save or a market-day change. There are three repair contracts at base daily demand.

Iron Hill Mine is on the Almada bank; use Places guidance to reach it across either bridge. New businesses use the dynamic daily market and appear in the P&L panel. Eggs, pastéis, repair contracts and quoted payments are included in autosaves; older saves receive the new inventory and business defaults.

A game day lasts five minutes, with three minutes of daylight and two minutes of night. Every third day, a one-day market event changes a route's material cost, selling price, and customer demand. Look for the market banner to see the changes.

At night, building windows and entrances, waterfront lamps, both bridges and the elétrico are illuminated. Day and night backgrounds are cached so the lights do not require rebuilding the scenery each frame.

At each full day's end, the game charges **20% of positive net daily profit**, rounded to the nearest whole dollar. This is a cash-based game calculation: all income received (sales, repair fees, bonuses and casino payouts) minus materials, eggs, vehicle/warehouse purchases, casino stakes and tolls. Starting cash is excluded, and loss-making or break-even days pay no tax. The P&L panel shows the estimate, last day's settlement, total taxes and tolls. Settlements are saved and cannot be charged twice after a reload or an offline time jump.

Both bridges charge a **$3 game toll for a completed Almada → Lisboa crossing**, on foot, by motorcycle or by car. Lisboa → Almada and halfway turnarounds are free. A crossing saved mid-bridge resumes normally and charges once at the Lisbon end. The fee still applies if cash is low, so the balance can become negative; buying materials never creates negative quantities. These are fictional game rates.

Choose **Rules & How to Play** on the start menu for game instructions. During play, click **Settings** in the top bar to switch between fullscreen and windowed mode, toggle moving traffic, or reopen the rules.

You start with $60 and 12 bag slots. Factory orders reserve space for pickup. Reach $500 to hit the cash goal. You can keep trading afterward.

## Foundry Casino

The Foundry Casino is in the Casino District on the right of the map. Walk to its door and press **E** to play roulette. It uses a real European wheel with 37 pockets: 18 red, 18 black, and a green 0.

1. Pick a chip of $5, $10, $25, $50, or $100 by clicking it or with the left and right arrow keys.
2. Bet on a color by clicking it or pressing **R**, **B**, or **G**.

| Bet | Wins on | Pays |
| --- | --- | --- |
| Red | 18 red numbers | 2× your chip |
| Black | 18 black numbers | 2× your chip |
| Green | 0 only | 36× your chip |

The stake leaves your cash when the wheel starts spinning. Winnings arrive when the ball lands. When the ball lands on 0, red and black bets lose, so the house wins over time. If you lose everything, the $30 cash power-up still appears on the map. Press **Esc** or **E** to leave. Game time pauses while you are in the casino.

## Desktop saves and the Python API

The desktop launcher automatically resumes your game and saves every ten seconds and on exit. By default it stores progress in `~/.foundry-town/saves.sqlite3` on your computer. The desktop game and its save server use Python's standard library.

To share a server with friends, run these commands on the server computer:

```
python save_api.py add-player
python save_api.py serve
```

Run `add-player` once per player. Give each player their own private key. The server listens on loopback port 8765. For internet play, put it behind an HTTPS reverse proxy and keep the SQLite database on persistent storage. Both commands accept `--database PATH` to select the same database.

On each player's computer, set the server address and key, then launch from that same window. On Windows, use PowerShell:

```powershell
$env:FOUNDRY_SAVE_URL = 'https://your-save-server.example'
$env:FOUNDRY_PLAYER_KEY = 'your-private-player-key'
& '.\Play Foundry Town.cmd'
```

On macOS, use Terminal:

```bash
export FOUNDRY_SAVE_URL='https://your-save-server.example'
export FOUNDRY_PLAYER_KEY='your-private-player-key'
./'Play Foundry Town (Mac).command'
```

For testing on the server computer, use `http://127.0.0.1:8765`. The first launch with a new key starts a new game. Reuse the same key to resume on another device.
