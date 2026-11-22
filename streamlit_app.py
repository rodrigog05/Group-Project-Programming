"""Foundry Town's Streamlit interface."""
from base64 import b64encode
from copy import deepcopy
import os
from pathlib import Path
import sqlite3
from time import monotonic

import streamlit as st
from streamlit.components.v1 import declare_component

import businesses
import exchange
from place_names import localize_place_names, place_name
from browser_game import (COLLISION_MAP, MONASTERY, OPEN_SITES, bag_full, next_move, STREET_LIFE, LocalSave, building_at, greeting, scene_for,
                          SaveConflict, entrance, place_vehicle_on_road, street_event, street_input)
from journal_market import market_snapshot
from journal_recipes import RECIPE_BY_KEY
from lisbon_landmarks import LANDMARKS
from ferry import FERRY_PIERS, nearby_pier
from lisbon_scene import RIVER_BOTTOM
from tourism import monument_description
from supabase_saves import CloudSave, SignupError, Supabase
from tycoon import DAY_SECONDS, EGG_COST, INDUSTRIES, SITES, TRADES, ROULETTE_POCKETS, Town, roulette_color
from vehicles import VEHICLES
from navigation import directions
from oriente_station import BOUNDS as ORIENTE_BOUNDS, station_svg


PLACES = {site.name: site for site in OPEN_SITES}
DEFAULT_DESTINATION = "No destination"
ROOT = Path(__file__).resolve().parent
street_map = declare_component("foundry_street", path=str(ROOT / "street"))
START_MESSAGE = "Buy materials, turn them into products, and sell them to grow your business."
SAVE_ERRORS = (OSError, sqlite3.Error, ValueError, KeyError, TypeError)

st.set_page_config(page_title="Foundry Town", layout="wide")
save_path = os.environ.get("FOUNDRY_LOCAL_DB")


def cloud_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not url and not key:
        return None
    if not url or not key:
        st.warning("Cloud saves need the Supabase project URL and publishable key.")
        return None
    try:
        return Supabase(url, key)
    except ValueError:
        st.warning("Cloud saves need a valid HTTPS project URL and a Supabase publishable key.")
        return None


cloud = None if save_path else cloud_client()
cloud_session = st.session_state.get("cloud_session")
cloud_store = CloudSave(cloud, cloud_session) if cloud and cloud_session else None
store = LocalSave(save_path) if save_path else cloud_store


def load_game():
    town, revision = store.load() if store else (Town(), 0)
    if not revision:
        town.message = START_MESSAGE
    st.session_state.town = town
    st.session_state.revision = revision
    st.session_state.save_error = ""
    st.session_state.cloud_conflict = False
    st.session_state.next_cloud_checkpoint = monotonic() + 15


if "town" not in st.session_state:
    try:
        load_game()
    except SAVE_ERRORS:
        st.error("Could not open your save. Reload to try again.")
        st.stop()


def act(operation, *args):
    """Apply an action to a copy of the town and save it. A map event returns the building to open."""
    candidate = deepcopy(st.session_state.town)
    if operation not in (street_input, street_event):
        candidate.message = ""
    result = operation(candidate, *args)
    if result is False and operation is street_input:
        return
    before = st.session_state.town
    buying = operation is interact or (operation is street_event and isinstance(args[0], dict)
                                       and args[0].get("action") == "bulk")
    supplier = before.nearby()
    if buying and supplier and supplier.role == "SUPPLIER" and bag_full(before):
        # The purchase was refused: show a red warning at the top of the game view.
        previous = st.session_state.get("alert", {}).get("id", 0)
        st.session_state.alert = {"id": previous + 1,
                                  "text": "Your bag is full"}  # The hint says what to make or sell
    moving_between_banks = (before.y >= RIVER_BOTTOM) != (candidate.y >= RIVER_BOTTOM)
    map_tick = operation is street_event and not args[0].get("action") and not moving_between_banks
    saved = save_town(candidate, checkpoint=map_tick)
    if saved and moving_between_banks and before.vehicle is None:
        # On foot, changing banks means a ferry ride: the street map plays the crossing.
        previous = st.session_state.get("ferry", {}).get("id", 0)
        st.session_state.ferry = {"id": previous + 1, "heading": 1 if candidate.y >= RIVER_BOTTOM else -1}
    return result if operation is street_event and saved else saved


def save_town(candidate, *, checkpoint=False):
    if cloud_store and st.session_state.get("cloud_conflict"):
        return False
    if cloud_store and checkpoint and monotonic() < st.session_state.get("next_cloud_checkpoint", 0):
        # Avoid a network write on every movement update.
        st.session_state.town = candidate
        return True
    if cloud_store:
        st.session_state.next_cloud_checkpoint = monotonic() + 15
    try:
        if store:
            st.session_state.revision = store.save(candidate, st.session_state.revision)
    except SaveConflict:
        st.session_state.cloud_conflict = bool(cloud_store)
        st.session_state.save_error = "Another tab updated this save. Reload progress before continuing."
        return
    except SAVE_ERRORS:
        st.session_state.save_error = "Could not save this action. Check your connection or save settings and try again."
        return
    st.session_state.town = candidate
    st.session_state.save_error = ""
    return True


def button(label, operation, *args, key=None, **options):
    st.button(label, key=key, on_click=act, args=(operation, *args), **options)


def interact(town, bulk=False):
    town.interact(bulk)
    # Production timing belongs to the corner timer, not the action acknowledgement.
    message, timing, _ = town.message.partition(". Ready in ")
    if timing:
        town.message = f"{message}."


def warehouse(town):
    price = 300 + town.warehouse_level * 250
    if town.cash < price:
        town.message = f"You need ${price:,} for this warehouse expansion."
        return
    town.cash -= price
    town.other_expenses_today += price
    town.bag_size += 12
    town.warehouse_level += 1
    town.message = f"Warehouse expanded. Total capacity is {town.carry_capacity}."


def show_directions(label):
    st.session_state.destination = label
    st.session_state.town_page = "Game"
    st.session_state.inside = None


def district_exchange():
    rows = exchange.portfolio_rows(town)
    st.dataframe([{k: row[k] for k in ("name", "ask", "bid", "owned", "cost_basis", "last_payout")}
                  for row in rows], hide_index=True)
    asset = st.selectbox("Investment", exchange.ASSETS, format_func=lambda item: item.name)
    quantity = st.number_input("Shares", 1, asset.cap)
    left, right = st.columns(2)
    with left:
        button("Buy shares", exchange.buy_shares, asset.symbol, quantity)
    with right:
        button("Sell shares", exchange.sell_shares, asset.symbol, quantity)


def play_street(site_inside=None):
    place_vehicle_on_road(town)
    nearby = town.nearby()
    pier = nearby_pier(town.x, town.y)
    hint = "Follow the marked entrances to buy, make, and sell."
    if nearby:
        hint = f"{place_name(nearby.name)} · {site_status(nearby)}"
    if pier:
        hint = f"{pier.name} · Take the ferry for $2"

    def play():
        event = st.session_state.get("street_map")
        if not isinstance(event, dict):
            return
        if site_inside is not None and event.get("action") in ("leave", "building"):
            act(street_event, {**event, "action": None})  # The time spent inside still counts
            if event["action"] == "leave":
                leave_building()
            else:
                run_building_key(site_inside, event.get("key"))
            return
        name = act(street_event, event)
        if name:
            enter_building(name)

    last_input = st.session_state.get("street_map")
    ack = last_input.get("id") if isinstance(last_input, dict) else None
    street_map(
        key="street_map", on_change=play, x=town.x, y=town.y, ack=ack,
        night=town.market_elapsed % DAY_SECONDS >= 180, facing=town.facing,
        vehicle=town.vehicle, stowed_vehicle=town.stowed_vehicle, hint=hint, message=localize_place_names(town.message),
        speed=town.movement_speed, collision=COLLISION_MAP, life=STREET_LIFE,
        cash=town.cash, on_bridge=town.bridge_journey is not None, ferry=st.session_state.get("ferry"),
        station_bounds=ORIENTE_BOUNDS,
        alert=st.session_state.get("alert"),
        interior=interior_view(site_inside) if site_inside is not None else None,
        next_move=visible_next_move(st.session_state.get("inside")) if st.session_state.get("show_hints", True) else None,
        route=directions(town, destination_point(st.session_state.get("destination", DEFAULT_DESTINATION))),
        suppliers=[{"x": site.door[0], "y": site.door[1], "trade": site.trade,
                    "cost": town.costs[site.trade]} for site in OPEN_SITES if site.role == "SUPPLIER"],
        free_slots=town.carry_capacity-town.cargo-town.reserved,
        locations=[
            {"name": place_name(site.name), "x": site.door[0], "y": site.door[1], "color": site.color}
            for site in OPEN_SITES
        ] + [
            {"name": pier.name, "x": pier.x, "y": pier.y, "color": "#91dfff"}
            for pier in FERRY_PIERS
        ],
    )


def visible_next_move(inside=None):
    hint = next_move(town, inside)
    return {**hint, "text": localize_place_names(hint["text"])} if hint else None


def site_status(site):
    if site.role == "FACTORY":
        trade = TRADES[town.business_site(site).trade]
        return f"{trade.supply} → {trade.product}"
    status = town.site_status(site).replace(f" · Eggs ${EGG_COST}", "")
    for shortcut in (" · B Manage", " · L Deliveries", " (F / R)", "E · ", "E "):
        status = status.replace(shortcut, "")
    return status


def destination_point(name):
    if name == DEFAULT_DESTINATION:
        return None
    if name == MONASTERY:
        left, _, right, bottom = LANDMARKS[0].bounds
        return (left+right)/2, bottom+16
    return entrance(PLACES[name])


def places():
    name = st.session_state.get("inside")
    if not (name and building_at(town) == name):
        st.session_state.inside = name = None
    destination = st.session_state.get("destination", DEFAULT_DESTINATION)
    point = destination_point(destination)
    arrived = point is not None and (
        building_at(town) == destination or (town.x-point[0])**2 + (town.y-point[1])**2 <= 28**2
    )
    if st.session_state.pop("reset_destination", False) or arrived:
        st.session_state.destination = DEFAULT_DESTINATION
    # One row with a fixed height: a button appearing here must not push the game view down (it flickered).
    pick, route, hints = st.columns((3, 2, 1), vertical_alignment="bottom")
    destination = pick.selectbox("Destination", [DEFAULT_DESTINATION, *PLACES, MONASTERY],
                                 index=0, format_func=place_name,
                                 key="destination")
    hints.toggle("💡 Show hints", value=True, key="show_hints")
    hint = next_move(town, name)
    target = hint and hint["target"]
    route.button(f"Show route to {place_name(target)}" if target else "Show route", width="stretch",
                 disabled=not (st.session_state.show_hints and target and target != destination),
                 on_click=st.session_state.update, kwargs={"destination": target})
    site_inside = PLACES.get(name, MONASTERY) if name else None
    # The game view stays on screen inside buildings too, so it keeps the keyboard (see street.js).
    play_street(site_inside)
    if site_inside is None:
        st.caption(directions(town, destination_point(destination))["instruction"])
    else:
        building(site_inside)


def enter_building(name):
    st.session_state.inside = name
    st.session_state.reply = None
    if name == MONASTERY:
        st.session_state.reply = st.session_state.town.message


def leave_building():
    st.session_state.inside = None


def inside(operation, *args):
    """Run a building action; the vendor answers with the result."""
    alert = st.session_state.get("alert")
    saved = act(operation, *args)
    if st.session_state.get("alert") != alert:
        # A full bag is the player's problem, not the vendor's: the red banner and the hint explain it,
        # and the vendor keeps their usual line.
        st.session_state.reply = None
    else:
        st.session_state.reply = st.session_state.town.message
    return saved


def building_actions(site):
    """(key, label, operation, args) for a building. The same list drives the scene's buttons and keys."""
    if site == MONASTERY:
        return []
    role = site.role
    if role == "SUPPLIER":
        supply = TRADES[site.trade].supply
        return [("e", f"Buy 1 {supply}", interact, ()), ("q", f"Buy up to 4 {supply}", interact, (True,))]
    if role == "GARAGE":
        def label(key, ride):
            if key in town.owned_vehicles or town.vehicle == key:
                return f"Drive {ride.label} · Free"
            return f"Buy {ride.label} · ${ride.price:,} · +{ride.trunk} slots"
        return [(str(number), label(key, ride), Town.purchase_vehicle, (key,))
                for number, (key, ride) in enumerate(VEHICLES.items(), start=1)]
    if role == "WAREHOUSE":
        return [("e", f"Add 12 slots · ${300 + town.warehouse_level * 250:,}", warehouse, ())]
    if role == "CASINO":
        return [("1", "Red · pays 2×", spin, ("red",)), ("2", "Black · pays 2×", spin, ("black",)),
                ("3", "Green 0 · pays 36×", spin, ("green",)),
                ("arrowleft", "Smaller chip", chip_step, (-1,)), ("arrowright", "Bigger chip", chip_step, (1,))] + [
                (f"chip-{value}", f"${value} chip", chip_set, (value,)) for value in CHIPS]
    if role in ("RESEARCH", "EXCHANGE"):
        return []
    labels = {
        "FACTORY": "Produce or collect",
        "PUBLIC SHOP": "Stock shop" if businesses.is_owned(town, site) else "Sell carried goods",
        "TIER2": "Craft, collect or sell machinery",
        "PASTELARIA": "Bake, collect or sell pastéis",
        "SHIPYARD": "Start repair or collect payment",
    }
    return [("e", labels[role], interact, ())]


def run_building_key(site, key):
    """A key pressed on the map view while inside: run the matching building action."""
    for action_key, _, operation, args in building_actions(site):
        if action_key == key:
            if operation in (spin, chip_step, chip_set):
                operation(*args)
            else:
                inside(operation, *args)
            return


def interior_view(site):
    """What the map view draws inside a building: its scene, the vendor's words and the keys."""
    found = scene_for(town, site)
    name, layout = found if found else (None, {"size": (640, 400), "bubble": None, "board": None})
    title = site if site == MONASTERY else place_name(site.name)
    keys = [[key, label] for key, label, *_ in building_actions(site) if not key.startswith(("arrow", "chip-"))]
    view = {"title": title, "scene": name, "size": layout["size"], "bubble": layout["bubble"],
            "board": layout["board"], "speech": localize_place_names(st.session_state.get("reply") or greeting(town, site)),
            "board_text": site_status(site) if site != MONASTERY and layout["board"] else "",
            "keys": keys + [["escape", "Leave"]],
            "accepts": [key for key, *_ in building_actions(site)] + ["escape"]}
    if site != MONASTERY and site.role == "CASINO":
        view["casino"] = {"spin": st.session_state.get("spin"), "chip": st.session_state.get("chip") or 10,
                          "chips": list(CHIPS), "luck": town.casino_luck}
    if site != MONASTERY and site.role == "GARAGE":
        # One card per vehicle, drawn under it in the showroom; the key bar just says 1-4.
        view["showroom"] = [
            {"number": number, "label": ride.label, "price": ride.price, "trunk": ride.trunk,
             "cargo": town.bag_size + ride.trunk, "road": ride.road_speed, "offroad": ride.offroad_speed,
             "status": "current" if town.vehicle == key else
                       "owned" if key in town.owned_vehicles or key == town.stowed_vehicle else "buy",
             "affordable": town.cash >= ride.price}
            for number, (key, ride) in enumerate(VEHICLES.items(), start=1)]
        view["keys"] = [["1–4", "Choose a vehicle"], ["escape", "Leave"]]
    if site != MONASTERY and site.role == "FACTORY":
        # Countdown in the corner while a batch is being made here.
        trade = town.business_site(site).trade
        order = town.orders[trade]
        if order is not None:
            view["speech"] = greeting(town, site)
            view["timer"] = {"product": TRADES[trade].product, "quantity": order.quantity,
                             "seconds": max(0.0, order.ready_at - town.elapsed)}
    return view


def building(site):
    """Inside a building. The scene and its buttons are drawn in the map view above; only notes stay here."""
    if site == MONASTERY:
        st.caption(f"Casino luck +{town.casino_luck}% · Maximum +20%")
        return
    if site.role == "CASINO":
        st.caption(f"Monastery luck: your odds are {town.casino_luck}% better")
    if site.role == "EXCHANGE":
        district_exchange()


CHIPS = (5, 10, 25, 50, 100)
SPIN_SECONDS = 4.5


def spin_remaining():
    spin_state = st.session_state.get("spin")
    return max(0, spin_state["ends_at"] - monotonic()) if spin_state else 0


def spin(choice):
    """Bet the chosen chip; the wheel animation lands on the result."""
    if spin_remaining():
        return
    stake = st.session_state.get("chip") or 10
    landed = {}

    def bet(town):
        if town.cash < stake:
            town.message = f"You need ${stake} in cash for that chip."
            return
        number = ROULETTE_POCKETS[town.roulette_pocket(choice)]
        payout = town.bet_roulette(choice, stake, number)
        if payout:
            town.add_cash(payout)
        result = f"You win ${payout - stake}!" if payout else f"You lose ${stake}."
        town.message = f"{number} {roulette_color(number).upper()} · {result}"
        landed["number"] = number

    if inside(bet) and landed:
        previous = st.session_state.get("spin") or {"id": 0, "angle": 0}
        pocket = ROULETTE_POCKETS.index(landed["number"])
        # Turn the wheel at least three times and stop with the winning pocket under the ball.
        target = previous["angle"] - (previous["angle"] % 360) - 3 * 360 - pocket * 360 / len(ROULETTE_POCKETS)
        st.session_state.spin = {"id": previous["id"] + 1, "angle": target, "from": previous["angle"],
                                 "number": landed["number"], "ends_at": monotonic() + SPIN_SECONDS}


def chip_set(value):
    if value in CHIPS:
        st.session_state.chip = value


def chip_step(step):
    index = CHIPS.index(st.session_state.get("chip") or 10)
    st.session_state.chip = CHIPS[max(0, min(len(CHIPS) - 1, index + step))]


ROUTE_COLOURS = ("#9aa3a6", "#b48762", "#c56b47", "#e8b04a")


def market():
    """One card per trade route: where to buy, make and sell, and the profit per unit."""
    st.subheader("Trade routes")
    st.caption("Buy materials at a yellow store, make products at a blue store, then sell them at a green market.")
    columns = st.columns(2)
    for index, trade in enumerate(TRADES):
        def named(role):
            return " or ".join(place_name(site.name) for site in OPEN_SITES if site.role == role and site.trade == index)
        cost, price = town.costs[index], town.prices[index]
        with columns[index % 2].container(border=True):
            st.markdown(f"<h4 style='margin:0;color:{ROUTE_COLOURS[index]}'>{trade.product}</h4>",
                        unsafe_allow_html=True)
            st.markdown(f"**1 Buy** {trade.supply} at {named('SUPPLIER')} · \\${cost} each  \n"
                        f"**2 Make** at {named('FACTORY')} · {trade.seconds} s  \n"
                        f"**3 Sell** at {named('PUBLIC SHOP')} · \\${price} each")
            st.markdown(f"**Profit \\${price - cost} per {trade.product.lower()}** · You carry "
                        f"{town.supplies[index]} {trade.supply.lower()} and {town.goods[index]} {trade.product.lower()}")
    with st.expander("Details: market table, today's results and recipes"):
        snapshot = market_snapshot(town, TRADES, INDUSTRIES, SITES)
        if snapshot.event_title:
            st.info(f"{snapshot.event_title} · {snapshot.event_detail}")
        st.dataframe([{
            "Product": row.product, "Materials held": row.raw_stock, "Material cost": row.raw_cost,
            "Sale price": row.price, "Stock": row.stock_label, "In production": row.orders,
            "Buyers / jobs": row.remaining_buyers, "Sold today": row.sold_today,
        } for row in snapshot.rows if not row.key.startswith("innovation:") and row.product != "Pastéis"], hide_index=True)
        st.write(f"Revenue \\${town.daily_revenue:,} · Expenses \\${town.daily_expenses:,} · "
                 f"Net \\${town.daily_net_profit:,}")
        if town.last_day_summary:
            summary = town.last_day_summary
            st.caption(f"Day {summary['day']} settled · Tax \\${summary['tax']:,} · "
                       f"Dividends \\${summary['dividends']:,}")
        st.markdown("**Discovered recipes**")
        if not town.discovered_recipes:
            st.caption("Operate a production site to discover its recipe.")
        for key in town.discovered_recipes:
            recipe = RECIPE_BY_KEY[key]
            if recipe.role == "RESEARCH":
                continue
            ingredients = ", ".join(f"{quantity} × {name}" for name, quantity in recipe.ingredients)
            st.write(f"**{recipe.title}** · {ingredients} · {recipe.seconds}s")


def landmarks():
    map_art = b64encode((ROOT / "street" / "world_100_day.webp").read_bytes()).decode("ascii")
    station = b64encode(station_svg().encode()).decode("ascii")
    city = b64encode((ROOT / "street" / "city_day.svg").read_bytes()).decode("ascii")
    campus = b64encode((ROOT / "street" / "nova_presentation_signs.svg").read_bytes()).decode("ascii")
    x, y, width, height = ORIENTE_BOUNDS
    st.html(f'<div style="position:relative"><img src="data:image/webp;base64,{map_art}" '
            'alt="Foundry Town · Lisboa and Almada" style="width:100%;display:block">'
            f'<img src="data:image/svg+xml;base64,{city}" alt="City buildings" '
            'style="position:absolute;inset:0;width:100%;height:100%">'
            f'<img src="data:image/svg+xml;base64,{station}" alt="Gare do Oriente" '
            f'style="position:absolute;left:{x/2400*100}%;top:{y/1780*100}%;width:{width/2400*100}%;'
            f'height:{height/1780*100}%">'
            f'<img src="data:image/svg+xml;base64,{campus}" alt="Nova SBE presentation" '
            f'style="position:absolute;left:{27/2400*100}%;top:{508/1780*100}%;'
            f'width:{178/2400*100}%;height:{110/1780*100}%"></div>')
    monument = st.selectbox("Landmark", LANDMARKS, format_func=lambda item: item.name)
    st.write(monument_description(monument, SITES))
    if monument.kind == "monastery":
        st.button("Show directions to the monastery", on_click=show_directions, args=(MONASTERY,))


def fullscreen_control(name):
    st.html(f"""
        <button class="foundry-fullscreen" id="foundry-fullscreen-{name}" type="button" hidden>Fullscreen</button>
        <script>
        (() => {{
            const button = document.getElementById("foundry-fullscreen-{name}");
            if (!document.fullscreenEnabled || !document.documentElement.requestFullscreen) return;
            const update = () => {{
                if (!button.isConnected) {{
                    document.removeEventListener("fullscreenchange", update);
                    return;
                }}
                button.textContent = document.fullscreenElement ? "Exit Fullscreen" : "Fullscreen";
            }};
            button.hidden = false;
            update();
            document.addEventListener("fullscreenchange", update);
            button.onclick = async () => {{
                try {{
                    if (document.fullscreenElement) await document.exitFullscreen();
                    else await document.documentElement.requestFullscreen();
                }} catch {{
                    button.textContent = "Fullscreen unavailable";
                }}
            }};
        }})();
        </script>
    """, unsafe_allow_javascript=True)


TUTORIAL = (
    ("Your goal", "goal.webp",
     "You start in Lisboa with **$60** and a 12-slot bag. Grow your business to **$500** by running trade routes: "
     "buy materials, turn them into products, and sell the products for more than they cost."),
    ("1 · Buy materials", "buy.webp",
     "Walk with **WASD** or the **arrow keys** to a store with a yellow **COMPRAR MATERIAIS** sign and press **E** at "
     "its door. Inside, **E** buys one unit and **Q** buys up to four. Armazém de Cereais sells wheat for $4."),
    ("2 · Make products", "make.webp",
     "Take the materials to a store with a blue **FABRICAR PRODUTOS** sign. Press **E** to drop them off. Production "
     "takes a few seconds while you play; press **E** again to collect the finished products."),
    ("3 · Sell products", "sell.webp",
     "Bring the products to a green **VENDER PRODUTOS** market and press **E** to sell everything you carry. Bread "
     "made from $4 wheat sells for $14. Repeat with bigger batches to grow faster."),
    ("Getting around", "garage.webp",
     "The only car **CONCESSIONÁRIO** is in Cacilhas, across the Tejo: take the ferry ($2) from Cais do Sodré "
     "to get there. Vehicles are faster and carry more, and by car the bridges charge a $3 toll toward Lisboa. "
     "Pick a **Destination** above the map to see the route, and press **Esc** to leave any building."),
)


def dismiss_tutorial():
    """The dialog's X: forget the tutorial too, or the next rerun would open it again."""
    st.session_state.show_tutorial = False
    st.session_state.tutorial_step = 0


@st.dialog("Basics", width="large", on_dismiss=dismiss_tutorial)
def tutorial():
    step = min(st.session_state.get("tutorial_step", 0), len(TUTORIAL) - 1)
    title, image, text = TUTORIAL[step]
    # Keep the slide, its text and the buttons on one screen.
    st.html("""<style>
        .st-key-tutorial_slide img {max-height: 46dvh; width: auto !important; max-width: 100%; margin: 0 auto;
                                    display: block; border-radius: 8px;}
        .st-key-tutorial_slide [data-testid="stImage"],
        .st-key-tutorial_slide [data-testid="stImageContainer"] {width: 100%; display: flex; justify-content: center;}
    </style>""")
    st.subheader(title)
    with st.container(key="tutorial_slide"):
        st.image(str(ROOT / "street" / "tutorial" / image))
    st.markdown(text.replace("$", "\\$"))  # A plain $ would start a maths formula in Markdown
    st.caption(f"{step + 1} / {len(TUTORIAL)}")
    back, skip, forward = st.columns(3)
    back.button("Back", disabled=step == 0, width="stretch", on_click=st.session_state.update,
                kwargs={"tutorial_step": step - 1})
    last = len(TUTORIAL) - 1
    # Skip jumps to the last slide, whose button starts the game.
    skip.button("Skip", disabled=step == last, width="stretch", on_click=st.session_state.update,
                kwargs={"tutorial_step": last})
    if step < last:
        forward.button("Next", type="primary", width="stretch", on_click=st.session_state.update,
                       kwargs={"tutorial_step": step + 1})
    elif forward.button("Start playing", type="primary", width="stretch"):
        close_tutorial()
        # A button inside a dialog only reruns the dialog; rerun the whole page so it closes.
        st.rerun()


def open_tutorial():
    st.session_state.show_menu = False
    st.session_state.show_tutorial = True
    st.session_state.tutorial_step = 0


def close_tutorial():
    st.session_state.show_tutorial = False
    st.session_state.tutorial_step = 0


@st.dialog("Foundry Town · Lisboa", width="large", dismissible=False)
def start_menu():
    with st.container(key="foundry_waterfront"):
        st.video(
            str(ROOT / "street" / "lisbon_waterfront.webm"),
            format="video/webm",
            autoplay=True,
            loop=True,
            muted=True,
        )
    with st.container(key="foundry_start"):
        fullscreen_control("menu")
        start_menu_card()


def start_menu_card():
    st.title("Foundry Town")
    st.caption("Lisboa · Build your fortune along the Tejo")
    if notice := st.session_state.pop("sign_out_notice", ""):
        st.warning(notice)
    town = st.session_state.town
    can_continue = bool(st.session_state.revision or st.session_state.get("started"))
    st.caption(f"Continue with ${town.cash:,} in cash." if can_continue else "Start with $60 and a 12-slot bag.")
    new, resume = st.columns(2)
    if new.button("New Game", width="stretch", type="primary"):
        if can_continue:
            st.session_state.confirm_restart = True
        elif not cloud_store or save_town(Town()):
            enter_game(new_game=True)
        else:
            st.error(st.session_state.save_error)
    if resume.button("Continue", width="stretch", disabled=not can_continue):
        enter_game()
    if st.session_state.get("confirm_restart"):
        st.warning("Start over and replace your current progress?")
        confirm, cancel = st.columns(2)
        if confirm.button("Replace progress"):
            if save_town(Town()):
                enter_game(new_game=True)
            st.error(st.session_state.save_error)
        if cancel.button("Keep my progress"):
            st.session_state.confirm_restart = False
            st.rerun()
    if st.button("Basics · how to play in 5 slides", width="stretch"):
        open_tutorial()
        st.rerun()
    with st.expander("Rules & How to Play"):
        st.markdown(
            "**Goal** · Start with $60 and grow to $500, then keep growing through trading, vehicles and "
            "business ownership.\n\n"
            "**Controls** · Move with **WASD** or the **arrow keys**. Press **E** at a door to go inside and **Esc** "
            "to leave. Inside: **E** buys, makes or sells, **Q** buys up to four.\n\n"
            "**Trade route** · Buy materials at a yellow store, make products at a blue store, sell them at a green "
            "market. Example: wheat at Armazém de Cereais → bread at Padaria do Sol → Pão de Cada Dia.\n\n"
            "**Getting around** · The ferry crosses the Tejo for $2 on foot; with a vehicle the bridges charge "
            "$3 toward Lisboa. Choose a **Destination** above the map to see the route.".replace("$", "\\$"))
    if cloud:
        cloud_account()


def cloud_account():
    if cloud_store:
        st.caption("Cloud saves are active.")
        if st.button("Sign out"):
            saved = save_town(st.session_state.town)
            st.session_state.clear()
            if not saved:
                st.session_state.sign_out_notice = "Signed out. Your last cloud save is still available."
            st.rerun()
        return

    with st.expander("Sign in for cloud saves"):
        st.caption("Signing in opens your cloud save. A new account can save your current guest game.")
        with st.form("cloud_account", clear_on_submit=True):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            sign_in = st.form_submit_button("Sign in")
            sign_up = st.form_submit_button("Create account")
        if not (sign_in or sign_up):
            return
        if not email.strip() or not password:
            st.error("Enter your email and password.")
            return
        if sign_up:
            try:
                session = cloud.sign_up(email.strip(), password)
            except SignupError as error:
                st.error(str(error))
                return
            except SAVE_ERRORS:
                st.error("Could not reach the account service. Try again in a moment.")
                return
            if session is None:
                st.success("Check your inbox or spam folder for the confirmation email, then sign in here.")
                return
        else:
            try:
                session = cloud.sign_in(email.strip(), password)
            except SAVE_ERRORS:
                st.error("Could not sign in. Check your details and confirm your email first.")
                return
        try:
            remote = CloudSave(cloud, session)
            town, revision = remote.load()
            if not revision and st.session_state.get("started"):
                town = st.session_state.town
                revision = remote.save(town, 0)
        except (SaveConflict, *SAVE_ERRORS):
            st.error("Could not open your cloud save. Your guest game is still available.")
            return
        st.session_state.clear()
        st.session_state.update(
            cloud_session=session, town=town, revision=revision, save_error="",
            next_cloud_checkpoint=monotonic() + 15,
        )
        st.rerun()


def enter_game(*, new_game=False):
    if new_game:
        st.session_state.reset_destination = True
        st.session_state.town_page = "Game"
        st.session_state.show_tutorial = True
        st.session_state.tutorial_step = 0
    st.session_state.started = True
    st.session_state.show_menu = False
    st.session_state.confirm_restart = False
    st.rerun()


town = st.session_state.town
waterfront = b64encode((ROOT / "street" / "lisbon_waterfront.webp").read_bytes()).decode("ascii")
st.html(f"""
<style>
  [data-testid="stMainBlockContainer"] {{
    max-width: none;
    padding-inline: clamp(0.5rem, 2vw, 1.75rem);
    padding-top: 3.25rem;
  }}
  section[role="dialog"]:has(.st-key-foundry_start) {{
    position: fixed !important;
    inset: 0 !important;
    transform: none !important;
    width: 100vw !important;
    max-width: none !important;
    height: 100dvh !important;
    max-height: none !important;
    margin: 0;
    border-radius: 0;
    background: #17343b url("data:image/webp;base64,{waterfront}") center / cover;
  }}
  section[role="dialog"]:has(.st-key-foundry_start) > :first-child:not(:has(.st-key-foundry_start)) {{
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }}
  .st-key-foundry_waterfront {{
    position: fixed;
    inset: 0;
    pointer-events: none;
  }}
  .st-key-foundry_waterfront video {{
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .st-key-foundry_waterfront video::-webkit-media-controls {{ display: none; }}
  @media (prefers-reduced-motion: reduce) {{
    .st-key-foundry_waterfront {{ display: none; }}
  }}
  .st-key-foundry_start {{
    position: relative;
    z-index: 1;
    width: min(100%, 38rem);
    margin: clamp(2rem, 50dvh - 6rem, 26rem) auto 2rem;
    max-height: calc(100dvh - 3rem);
    overflow-y: auto;
    transition: margin-top 0.2s;
    padding: clamp(1rem, 3vw, 2rem);
    border: 2px solid #ffc66c;
    border-radius: 12px;
    background: #16303a;
    color: #fff7e6;
    color-scheme: dark;
  }}
  .st-key-foundry_start:has(details[open]) {{ margin-top: 1.5rem; }}
  .st-key-foundry_start details p {{ color: #fff7e6; line-height: 1.5; }}
  .st-key-foundry_start details strong {{ color: #ffc66c; }}
  .st-key-foundry_start h1 {{ color: #ffc66c; }}
  .st-key-foundry_start [data-testid="stCaptionContainer"] p {{ color: #a9e2ce; }}
  .st-key-foundry_start button[data-testid^="stBaseButton"] {{
    background: #2c4a55;
    color: #fff7e6;
    border-color: #577480;
  }}
  .st-key-foundry_start button[data-testid="stBaseButton-primary"] {{
    background: #ffc66c;
    color: #101f28;
  }}
  .st-key-foundry_start button[data-testid^="stBaseButton"]:disabled {{
    background: #253e48;
    color: #a0b2b8;
  }}
  .foundry-fullscreen {{
    position: fixed;
    top: 0.5rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 100;
    background: #16303a;
    border: 1px solid #ffc66c;
    border-radius: 5px;
    padding: 0.35rem 0.75rem;
    color: #ffc66c;
    font: 600 0.875rem system-ui, sans-serif;
    cursor: pointer;
  }}
  #foundry-fullscreen-game {{
    position: static;
    transform: none;
  }}
  .st-key-foundry_hud {{
    background: #101f28;
    border: 1px solid #31515d;
    border-radius: 8px;
    padding: 0.55rem 0.85rem;
    color: #fff3dc;
  }}
  .st-key-foundry_hud h1 {{
    color: #ffda86;
    font-size: clamp(1.15rem, 2vw, 1.6rem);
    padding: 0;
  }}
  .st-key-foundry_hud [data-testid="stMetricLabel"] p {{ color: #b7cacb; }}
  .st-key-foundry_hud [data-testid="stMetricValue"] {{
    color: #ffda86;
    font-size: 1.15rem;
    font-weight: 700;
  }}
  .st-key-foundry_hud [data-testid="stBaseButton-secondary"] {{
    color: #fff3dc;
    background: #16303a;
    border-color: #577480;
  }}
  .st-key-foundry_nav [data-testid="stBaseButton-primary"] {{
    background: #ffc66c;
    border-color: #b38239;
    color: #101f28;
  }}
  @media (max-width: 760px) {{
    .st-key-foundry_hud [data-testid="stHorizontalBlock"],
    .st-key-foundry_nav [data-testid="stHorizontalBlock"] {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      align-items: center;
      gap: 0.55rem;
    }}
    .st-key-foundry_hud [data-testid="stColumn"],
    .st-key-foundry_nav [data-testid="stColumn"] {{ width: auto !important; }}
    .st-key-foundry_hud [data-testid="stColumn"]:first-child {{ grid-column: 1 / -1; }}
  }}
  body:has(.st-key-foundry_start) #foundry-fullscreen-game {{ display: none; }}
</style>
""")
with st.container(key="foundry_hud"):
    title, cash, cargo, day, menu, display = st.columns(
        (2, 1, 1, 1, 1, 1), vertical_alignment="center"
    )
    title.title("Foundry Town")
    cash.metric("Cash", f"${town.cash:,}")
    cargo.metric("Bag + reserved", f"{town.cargo + town.reserved} / {town.carry_capacity}")
    day.metric("Day", town.day)
    menu.button("Start menu", on_click=st.session_state.update, kwargs={"show_menu": True})
    with display:
        fullscreen_control("game")
    goal = "Goal reached! Keep growing." if town.won else f"\\${town.cash:,} of the \\$500 goal"
    st.progress(1.0 if town.won else max(0.0, min(town.cash / 500, 1.0)), text=goal)

page = st.session_state.get("town_page", "Game")
PAGES = {"Game": places, "Market & recipes": market, "Landmarks": landmarks}
if page not in PAGES:  # A page from an older version of the game
    page = st.session_state.town_page = "Game"
with st.container(key="foundry_nav"):
    columns = st.columns(len(PAGES) + bool(store), vertical_alignment="center")
    for column, label in zip(columns, PAGES):
        column.button(
            label, type="primary" if page == label else "secondary", width="stretch",
            on_click=st.session_state.update, kwargs={"town_page": label},
        )
    if store:
        with columns[-1].popover("Saves", width="stretch"):
            if cloud_store and st.button("Save progress", width="stretch"):
                if save_town(town):
                    st.toast("Progress saved.")
            reload_label = "Reload cloud progress" if cloud_store else "Reload local progress"
            if st.button(reload_label, width="stretch"):
                try:
                    load_game()
                    st.rerun()
                except SAVE_ERRORS:
                    st.session_state.save_error = "Could not reload progress. Check your save settings and try again."

if st.session_state.save_error:
    st.error(st.session_state.save_error)
if town.won and not town.milestone_acknowledged:
    st.success("You reached the $500 cash milestone.")
    button("Continue building", Town.continue_after_milestone)

PAGES[page]()

if town.message:
    st.info(localize_place_names(town.message))

if st.session_state.get("show_menu", True):
    start_menu()
elif st.session_state.get("show_tutorial"):
    tutorial()
