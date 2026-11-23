# Foundry Town

Foundry Town is a browser business tycoon set in Lisboa and Almada. Buy materials, make products, and sell your first product to complete Level 1. Reach $500 for Level 2, then choose whether to continue to the $2,000 final goal. Keep growing with vehicles, a bigger warehouse and investments.

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
| Progress | Streamlit Session State and Supabase | Guests play in session memory. Supabase stores permanent, per-account saves. |
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

Open the local URL printed by Streamlit. You start with $60 and 12 cargo slots. For a first trade, visit Goldenfield Farm and buy four Wheat, visit Sunrise Bakery and start production, then click the street map and give the order time to finish. Collect the Bread and sell it at Daily Bread Market. **Market & recipes** shows one card per trade route (where to buy, make and sell, and the profit per unit); the full market table and recipes are under **Details**.

The Lisbon start menu fills the browser with a looping waterfront scene from Core Edition. Boats and bridge traffic move through a two-minute day–night cycle. The browser plays the muted backdrop while the menu is open and displays a still image when reduced motion is enabled. The **Play** tab has **New Game** and **Continue**, plus **Sign in / Create account** when cloud saves are configured. The **Rules & How to Play** tab lists the goal, controls, a trade route example and travel costs. A new game opens **Basics**, five animated slides that show how to trade, enter stores with **E**, and get around. Use **Back**, **Next** or **Skip**. The slides in `street/tutorial/` were drawn from the game's own map and store scenes. To reopen the start screen from the game, choose **Menu → Start menu**. Replacing your progress requires confirmation. Use **Fullscreen** from the menu or game and **Exit Fullscreen** or **Esc** to return to the browser window.

Under **Menu**, **Game** opens the map. **Market & recipes** shows trading information. **Landmarks** describes Lisbon's monuments. Signed-in players can also save and reload cloud progress from this menu. The bar above the map shows cash, carried bag items (with reserved space listed separately in Inventory), the current market day, and a progress bar for the current level. A centered message appears after each of the three levels; acknowledged levels are saved with your game.

Click or tab into the street map. Walk with **WASD** or the **arrow keys**. Press **E** at a marked entrance to go inside, or at a ferry pier to cross the Tejo (the crossing plays as an animation; click or **Esc** skips it). On the street, **Q** buys up to four units at a supplier. The buttons below the map provide touch controls.

The original desktop guitar soundtrack is enabled by default. Click or press a key during play to start it if the browser blocks autoplay. To turn music off or on, open **Settings** beside the map controls and select **Music**. The browser remembers your choice.

Most buildings show an illustrated scene from the desktop game. The vendor answers in a speech bubble and the chalkboard shows live prices. Use the buttons or their keys: **E** to buy, make, sell or collect (or expand the warehouse), **Q** to buy four, **1–4** for vehicles in a garage, and in the casino pick a chip (**←** / **→**) and press **1** (red), **2** (black) or **3** (green 0) to spin the wheel. **Esc** leaves. The building is drawn in the same game view as the street, so the keys work straight away without clicking. A light-bulb hint in the corner of the game view says what to do next (for example *Now you should go to Sunrise Bakery to turn your Wheat into Bread*); **Route options → Show hints** hides it, and **Show route to …** puts that building in Destination. The top-right corner shows the quantity and seconds remaining for every active batch, both inside buildings and on the street. Finished batches stay marked ready to collect until picked up. Inventory lists only carried materials and goods; ingredients leave the bag when production starts and finished goods enter it when collected. The hint simply says to collect; the seller keeps their usual line and the board keeps the recipe while the order is pending. **Route options → Destination** selects a light-blue dashed street route. Follow it and press **E** at the door to enter; selecting a destination never moves you or opens a store. The Jerónimos monastery improves your casino odds by 5% per visit, up to 20%. Luck scales each bet's normal chance, so with +20% red or black wins 58.4% of the time (instead of 48.6%) and green 0 wins 3.2% (instead of 2.7%).

At **Bolsa de Lisboa**, press **E** to enter and use the **Trade shares** panel. The table shows each investment's buy price (**ask**), sell price (**bid**), shares owned, cost basis, and last dividend payout. Choose an **Investment**, set the number of **Shares**, and select **Buy shares** or **Sell shares**.

The market clock and production run while the map has focus. Click outside the map to pause street play. Each day has 60 seconds of daylight followed by 60 seconds of night. The market settles every 120 game seconds. Trade shortcuts appear only within reach of the right supplier, with enough cash and free cargo space. On foot, the ferry costs $2. With a vehicle, bridges charge a $3 toll toward Lisbon.

Destination starts at **No destination**, with no route drawn. Choose a building to show directions, or choose **No destination** to cancel them. Reaching the selected building resets the selector and clears the line. Ferry stops keep your final destination selected. Starting a new game clears any previous destination.

The street view includes the original map art and collision rules, with the desktop game's traffic, the waterfront tram, the shuttling ferry and pedestrians who keep to the pavements, as decoration (they never block you). The desktop save services are outside this port. Driving a vehicle back to Lisboa needs the $3 bridge toll in cash before you start across.

Vehicles drive on paved streets, bridges, and the Almada tunnel. Drive straight through the road portals on either side of the Almada park. Your vehicle disappears under the park and reappears at the exit. Press **V** or choose **Leave vehicle** to walk on sidewalks. Return to a street to use **Bring back vehicle**. Free up bag space first if you are using the trunk, and finish crossing any bridge or tunnel before getting out.

Street movement and camera tracking render immediately in the browser. Movement is batched approximately every 200 ms, with one request in flight, and Python validates collisions before trading or saving. The browser reconciles each reply and replays unsent movement. Prediction buffers at most two seconds during a slow response. The compressed night map loads only when night is first shown.

## Vehicles

Vehicles use the same side-view skins in the dealership and on the street. All four player vehicles drive 30% slower than before, on roads and off-road. Press **V** or **Leave vehicle** below the map to park your vehicle and walk; on a street, **V** or **Bring back vehicle** gets you back in. Owned rides remain available at the garage through **Drive · Free**, including after restoring a cloud save. Empty excess cargo and finish reserved orders before switching to your smaller walking bag. Leave bridges before dismounting.

## Guest progress

Guest progress lives in Streamlit Session State. Use **Continue** to resume from the start menu within the same session. Refreshing the browser, opening a separate tab, or restarting the server starts a new guest session. Sign in to keep progress across sessions.

## Publish on Streamlit Community Cloud

1. Sign in at Streamlit Community Cloud with a GitHub account that can see this repository.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app** and select the repository and branch.
3. Set **Main file path** to `streamlit_app.py`. Select Python 3.12 in advanced settings, then deploy.
4. Open the assigned URL and run the first-trade walkthrough above. Open a separate private browser window and confirm it starts with $60.

Guests can play immediately in separate sessions. [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## Enable per-player cloud saves

1. In your Supabase project, run [`supabase/foundry_saves.sql`](supabase/foundry_saves.sql) once in the SQL Editor. It creates one save row per player and enables row-level security so signed-in players can read and write their own row.
2. Enable **Email** sign-in, new account signups, and email confirmations in Supabase Auth. Under **URL Configuration**, set **Site URL** to your public Streamlit URL. Players confirm their email and then return to the game to sign in. For public signups, configure a custom SMTP provider. The default Supabase mail service sends only to addresses on the project team and has a low rate limit. [Supabase SMTP guide](https://supabase.com/docs/guides/auth/auth-smtp)
3. In Streamlit's **Secrets** settings, add these two top-level values using your project URL and **publishable key**. A private local deployment can also pass them as environment variables.

   ```toml
   SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "sb_publishable_YOUR_KEY"
   ```

4. Open the start menu and choose **Sign in / Create account**. After signing in, **Continue** opens your cloud save. When an account has an empty save slot, signing in from a guest game carries that progress into the account. When the account already has a save, signing in opens that save.

Trades and other explicit actions save immediately. Street movement and clock updates save about every 15 seconds while playing. **Menu → Save progress** saves your position before you close the tab. **Sign out** also saves before ending the session. If another tab has changed the save, use **Menu → Reload cloud progress** to continue from the latest revision. After closing the app or a server restart, sign in again and choose **Continue**. Play a test session in two separate accounts and verify their saves stay independent before sharing the deployed app.

## Tests

From the repository root:

```sh
uv run --python 3.12 --with-requirements requirements.txt --with pytest python -m pytest -q
node --test tests/street_prediction.cjs
```

The tests need no network, accounts or secrets.

- **Game rules** (`tests/test_market.py`, `test_vehicles.py`, `test_contracts.py` and the other engine tests) cover trades, production, prices, vehicles, tolls, contracts, research, businesses and deliveries. They include rejected actions, such as buying without enough cash or space.
- **Browser app** (`tests/test_browser_game.py`) tests New Game, Continue, progress replacement, a full trade loop, rejected purchases, separate guest sessions, ferry fares and bridge tolls.
- **Cloud saves** (`tests/test_supabase_saves.py`) use a fake Supabase service to test authentication, saving and reloading, account separation, stale-save protection and session refresh.
- **Street map** (`tests/test_street.py`) checks walking, collisions, entrances, cargo limits, the ferry, invalid input, and that cars stay on roads and pedestrians never step onto one.
- **Buildings** (`tests/test_buildings.py`) check that every door opens its own building without trading, every scene image exists, E enters and Leave exits, destination selection never teleports or opens a store, casino spins pay by colour and reject unaffordable chips, the monastery's luck cap, and that cross-bank walking routes lead to the ferry.
- **Casino and ferry rules** (`tests/test_casino.py`, `tests/test_ferry.py`) cover the roulette wheel and payouts, fares, failed trips and reaching every business on foot.
- **Browser prediction** (`tests/street_prediction.cjs`) covers delayed-response reconciliation, action ordering, trade shortcuts and deferred night-map loading. The deployed site and visual rendering require a browser check.

## Security and data

- Guests can play without accounts. Supabase cloud saves require sign-in and the app uses a publishable key paired with the player's access token. `.env` files and Streamlit secrets are listed in `.gitignore`.
- The only dependency is `streamlit`, pinned to an exact version in `requirements.txt`.
- Guest progress is held in session memory. Supabase stores versioned game snapshots and enforces save ownership in the database.

## Known limits

- Guest games reset on reload or when the server restarts. Players with cloud saves can sign in again to resume.
- Bolsa de Lisboa uses a text-only interior.
- Nova SBE opens a game-style classroom scene of three team members presenting Foundry Town to the professors, inspired by the supplied reference. It has no research or workshop controls.
- To keep the town simple, the only car dealership is Cacilhas Dealership (your first vehicle needs a ferry ride), Foundry Warehouse is the only warehouse, and eggs and Pastéis de Belém were removed. The engine keeps these buildings for older saves; on the map their plots show apartment blocks and they cannot be entered.
- Contracts, delivery routes and business ownership were taken out of the menus to keep the game simple. Research and advanced crafting were also retired from the browser menus; legacy innovation fields remain readable in saves. Their rules (`contracts.py`, `logistics.py`, `businesses.py`, `innovation.py`) remain in the engine, with their tests, because older saves still store their fields.

## Project structure

- `streamlit_app.py` contains game screens and event handlers.
- `navigation.py` finds safe street routes and directs walkers to the ferry when crossing banks. Routes are cached and never change player position or cash.
- `browser_game.py` adapts navigation and simulation turns for the browser.
- `supabase_saves.py` handles authentication and per-account cloud saves.
- `tycoon.py` and the adjacent simulation modules hold game rules and state.
- `street/` contains the browser map component and original day/night artwork; `street/scenes/` holds the building, casino, monastery and ferry scenes, drawn from the desktop game's own scene code (kept on the `desktop-game` branch).
- `oriente_station.py` draws the station's branching steel canopy and glass platforms for day and night. Run `python oriente_station.py` to rebuild `street/oriente_day.svg` and `street/oriente_night.svg`; the street view and landmark map share this artwork.
- `city_art.py` draws compact supply depots, workshops, product-specific stores, storage and traditional Lisbon apartments. The street and landmark views share its day/night SVG overlays. Building footprints are 128 × 80 within the original plots, with walkable side yards and unchanged entrances. `Site.solid_bounds` supplies the same walls to Python and browser movement validation. Closed buildings retain their apartment footprints.
- `place_names.py` supplies English shop names for signs, destinations, hints, scenes and market routes. Existing building identifiers stay internal so saved buildings and destinations remain compatible. Buildings blend with the surrounding plot ground without inset paving panels. Decorative traffic follows right-hand lanes: westbound above the centre line and eastbound below it.
- Run `python city_art.py` to rebuild the city overlays and classroom SVG. To also export the classroom and tutorial WebP images, run `uv run --python 3.12 --with resvg-py --with Pillow python city_art.py --presentation`. The tutorial views use the same building art and English names as the street. These two image tools are needed only to rebuild those assets; playing the game requires no new dependencies.
