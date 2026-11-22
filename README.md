# Foundry Town

Foundry Town is a browser business tycoon set in Lisboa and Almada. Buy materials, make products, and sell them to reach $500. Keep growing through research, contracts, investments, business ownership, and automated deliveries.

**Play online:** https://foundrytown.streamlit.app/

## Team

| Name | Student number |
|---|---|
| Tomás Barata | 62591 |
| Rodrigo Gonçalves | 62589 |
| Martim Palhares Almeida | 62588 |

## Stack

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.12 | The course language. The game rules were already written in Python. |
| Interface | Streamlit 1.66.0 | Runs Python in the browser with no separate front end, and deploys free on Streamlit Community Cloud. |
| Street map | A small Streamlit component (`street/`, HTML and JavaScript) | Streamlit has no keyboard-driven map, so this one view is custom. |
| Saving | SQLite, optional | Built into Python and enough for one local player. |
| Tests | pytest | The course's test tool. Streamlit's `AppTest` drives the real app in tests. |
| Commands | uv | Installs the pinned dependencies and runs the app and tests with one command. |

The rules come from our earlier desktop (Tkinter) version, which is kept on the `desktop-game` branch.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from a fresh copy of the repository:

```sh
git clone https://github.com/rodrigog05/Group-Project-Programming.git
cd Group-Project-Programming
uv run --python 3.12 --with-requirements requirements.txt streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. You start with $60 and 12 cargo slots. For a first trade, visit Goldenfield Farm and buy four Wheat, visit Sunrise Bakery and start production, then click the street map and give the order time to finish. Collect the Bread and sell it at Daily Bread Market. **Market & recipes** shows inventory, prices, demand, orders, and discovered recipes.

The Lisbon start menu fills the browser with a looping waterfront scene from Core Edition. Boats and bridge traffic move through a 60-second day–night cycle. The browser plays the muted backdrop while the menu is open and displays a still image when reduced motion is enabled. Choose **New Game**, **Continue**, or **Rules & How to Play**. Open it again from **Start menu** above the map. Replacing your progress requires confirmation. Use **Fullscreen** from the menu or game and **Exit Fullscreen** or **Esc** to return to the browser window.

**Game** opens the map. **Market & recipes** shows trading information. Open **More** for contracts, deliveries, businesses, and landmarks. The bar above the map shows cash, bag use including reserved slots, and the current market day.

Click or tab into the street map. Walk with **WASD** or the **arrow keys**. Use **E** at a marked entrance to trade and at a ferry pier to cross the Tejo. At suppliers, **Q** buys up to four units. At farms, **F** buys one egg and **R** buys up to four. The buttons below the map provide touch controls. For garages, the warehouse, the exchange, research, and the casino, **E** selects the building's controls below the map.

The market clock, production, deliveries, research, and contracts run while the map has focus. Click outside the map to pause street play. **Time & progress** shows the market countdown and save information. The market settles every 300 game seconds and the map switches to night after 180 seconds. Use **Visit** below the map for direct travel. On foot, the ferry costs $2. With a vehicle, bridges charge a $3 toll toward Lisboa.

The street view includes the original map art and collision rules, with the desktop game's traffic, pedestrians and waterfront tram as decoration (they never block you). Building interiors, soundtrack, and desktop save services are outside this port. Driving a vehicle back to Lisboa needs the $3 bridge toll in cash before you start across.

Street movement and camera tracking render immediately in the browser. Movement is batched approximately every 200 ms, with one request in flight, and Python validates collisions before trading or saving. The browser reconciles each reply and replays unsent movement. Prediction buffers at most two seconds during a slow response. The compressed night map loads only when night is first shown.

## Keep local progress

Run a private instance bound to loopback:

```sh
FOUNDRY_LOCAL_DB=.local/game.sqlite3 uv run --python 3.12 --with-requirements requirements.txt streamlit run streamlit_app.py --server.address 127.0.0.1
```

`FOUNDRY_LOCAL_DB` selects one local autosave slot. Choose a new path to start a fresh game or back up the database to keep progress. If two tabs edit the same slot, the older revision must reload before writing. A failed SQLite write leaves the current game state available for retry. The browser build starts fresh from its own save slot and does not import desktop saves.

## Publish on Streamlit Community Cloud

1. Sign in at Streamlit Community Cloud with a GitHub account that can see this repository.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app** and select the repository and branch.
3. Set **Main file path** to `streamlit_app.py`. Select Python 3.12 in advanced settings, then deploy.
4. Open the assigned URL and run the first-trade walkthrough above. Open a separate private browser window and confirm it starts with $60.

Cloud mode uses one independent game per browser session. A full reload, disconnected session, or server restart can reset progress. Leave `FOUNDRY_LOCAL_DB` unset for a public instance. No external services, database setup, or account credentials are needed for gameplay. [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## Tests

From the repository root:

```sh
uv run --python 3.12 --with-requirements requirements.txt --with pytest python -m pytest -q
```

The tests need no network, accounts or secrets.

- **Game rules** (`tests/test_market.py`, `test_vehicles.py`, `test_contracts.py` and the other engine tests) cover trades, production, prices, vehicles, tolls, contracts, research, businesses and deliveries. They include rejected actions, such as buying without enough cash or space.
- **Browser app** (`tests/test_browser_game.py`) tests the start menu and save replacement, a full trade loop, rejected purchases, separate player sessions, ferry fares and bridge tolls, and stale-save protection.
- **Street map** (`tests/test_street.py`) checks walking, collisions, entrances, cargo limits, the ferry and invalid input.
- **Not covered by automated tests:** how the street map looks and feels in a real browser, and the deployed site. We check those by hand before the demo.

## Security and data

- The game needs no API keys, passwords or accounts. `.env` files, Streamlit secrets and SQLite saves are listed in `.gitignore`.
- The only dependency is `streamlit`, pinned to an exact version in `requirements.txt`.
- On the public site each browser session plays its own game in memory. Nothing is stored on the server, so a reload or restart starts a new game.
- Locally, `FOUNDRY_LOCAL_DB` turns on one SQLite save slot. All database queries are parameterized.

## Known limits

- Progress on the public site resets on reload or when the server restarts.
- Building interiors and the soundtrack from the desktop version are not in the browser version.
- One local save slot per `FOUNDRY_LOCAL_DB` path, meant for one player.

## Project structure

With Node.js installed, run `node --test tests/street_prediction.cjs` for browser prediction, delayed-response reconciliation, action ordering and deferred night-map checks.

- `streamlit_app.py` contains game screens and event handlers.
- `browser_game.py` adapts navigation, time, and persistence for the browser.
- `tycoon.py` and the adjacent simulation modules hold game rules and state.
- `street/` contains the browser map component and original day/night artwork.
