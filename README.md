# Foundry Town

Run **Play Foundry Town.cmd** on Windows or run `python tycoon.py` with Python 3 and Tkinter. No pip packages are required.

On macOS, double-click **Play Foundry Town (Mac)**. The other **Play Foundry Town** file is the Windows launcher and won't open on a Mac. Finder hides file extensions, so the two can look alike. The first time, macOS may block the launcher because it was downloaded. If it does, right-click it, choose **Open**, then confirm.

The game needs Python with Tk 8.6 or newer. Apple's built-in Python uses Tk 8.5, which shows a black window on recent macOS. Install a newer Python in either of these ways, and the launcher finds it automatically:

- With [uv](https://docs.astral.sh/uv/): `uv python install 3.12`
- From [python.org](https://www.python.org/downloads/macos/)

Move with **WASD** or the arrow keys. Walk to a colored doorstep and press **E** to interact. At a supplier, **Q** buys up to four units at once.

| Route | Buy | Produce and collect | Sell |
| --- | --- | --- | --- |
| Metal | Iron ore at Iron Hill Mine for $5 | Tools at Ironworks | Tool Market customers pay $18 each |
| Timber | Timber at Pine Mill for $7 | Furniture at Oak Workshop | Home Market customers pay $26 each |
| Clay | Clay at Redbank Clay Pit for $6 | Pottery at Ember Kiln | The Pottery Shop customers pay $22 each |
| Farm | Wheat at Goldenfield Farm for $4 | Bread at Sunrise Bakery | Daily Bread Market customers pay $14 each |

Each unit of supply makes one finished good. Press **E** at the factory to drop off supplies, then press it again when the order is ready. Each public shop buys as many finished goods as its customers still want that day.

A game day lasts 24 real hours. The market calendar starts on first launch and keeps moving while the game is closed. Every third day, a one-day market event changes a route's material cost, selling price, and customer demand. Look for the market banner to see the changes.

You start with $60 and 12 bag slots. Factory orders reserve space for pickup. Reach $500 to hit the cash goal. You can keep trading afterward.

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
