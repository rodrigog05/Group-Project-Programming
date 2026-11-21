# Foundry Town

Foundry Town is a browser business tycoon set in Lisboa and Almada. Buy materials, make products, and sell them to reach $500. Keep growing through research, contracts, investments, business ownership, and automated deliveries.

**Play online:** _Streamlit Community Cloud URL to be added after deployment_

## Team

| Name | Student number |
|---|---|
| Tomás Barata | 62591 |
| Rodrigo Gonçalves | 62589 |
| Martim Palhares Almeida | 62588 |

## Stack

This port uses Python 3.12 and Streamlit. The desktop project's Python simulation supplies the economy and rules. Streamlit supplies the browser interface, and SQLite provides an optional single-user local save. The separate desktop checkout can still run independently.

## Run locally

From the repository root, with uv installed:

```sh
uv run --python 3.12 --with-requirements requirements.txt streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. You start with $60 and 12 cargo slots. For a first trade, visit Goldenfield Farm and buy four Wheat, visit Sunrise Bakery and start production, advance time from the sidebar, collect the Bread, and sell it at Daily Bread Market. **Market & recipes** shows inventory, prices, demand, orders, and discovered recipes.

Click or tab into the street map. Walk with **WASD** or the **arrow keys**. Use **E** at a marked entrance to trade and at a ferry pier to cross the Tejo. At suppliers, **Q** buys up to four units. At farms, **F** buys one egg and **R** buys up to four. The buttons below the map provide touch controls. For garages, the warehouse, the exchange, research, and the casino, **E** selects the building's controls below the map.

The market clock, production, deliveries, research, and contracts run while the map has focus. Click outside the map to pause street play. Use **Advance time** in the sidebar to move the clock from any screen. The market settles every 300 game seconds and the map switches to night after 180 seconds. Use **Visit** below the map for direct travel. On foot, the ferry costs $2. With a vehicle, bridges charge a $3 toll toward Lisboa.

The street view includes the original map art and collision rules. Animated traffic, building interiors, soundtrack, and desktop save services are outside this port.

## Keep local progress

Run a private instance bound to loopback:

```sh
FOUNDRY_LOCAL_DB=.local/game.sqlite3 uv run --python 3.12 --with-requirements requirements.txt streamlit run streamlit_app.py --server.address 127.0.0.1
```

`FOUNDRY_LOCAL_DB` selects one local autosave slot. Choose a new path to start a fresh game or back up the database to keep progress. If two tabs edit the same slot, the older revision must reload before writing. A failed SQLite write leaves the current game state available for retry. The browser build starts fresh from its own save slot and does not import desktop saves.

## Publish on Streamlit Community Cloud

1. Push this repository to GitHub.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app** and select the repository and branch.
3. Set **Main file path** to `streamlit_app.py`. Select Python 3.12 in advanced settings, then deploy.
4. Open the assigned URL and run the first-trade walkthrough above. Open a separate private browser window and confirm it starts with $60.

Cloud mode uses one independent game per browser session. A full reload, disconnected session, or server restart can reset progress. Leave `FOUNDRY_LOCAL_DB` unset for a public instance. No external services, database setup, or account credentials are needed for gameplay. [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## Verify

```sh
uv run --python 3.12 --with-requirements requirements.txt --with pytest python -m pytest -q
```

The suite includes unmodified engine tests from the desktop checkout and browser entrypoint tests for trade, rejection, restart, session isolation, river crossings, and concurrent save conflicts.

- `streamlit_app.py` contains game screens and event handlers.
- `browser_game.py` adapts navigation, time, and persistence for the browser.
- `tycoon.py` and the adjacent simulation modules hold game rules and state.
- `street/` contains the browser map component and original day/night artwork.
