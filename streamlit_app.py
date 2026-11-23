"""Foundry Town's Streamlit interface."""
from base64 import b64encode
from copy import deepcopy
import os
from pathlib import Path
from time import monotonic

import streamlit as st
from streamlit.components.v1 import declare_component

import businesses
import exchange
import innovation
from place_names import localize_place_names, place_name
from browser_game import (COLLISION_MAP, MONASTERY, OPEN_SITES, bag_full, next_move, STREET_LIFE, building_at, greeting, scene_for,
                          entrance, place_vehicle_on_road, street_event, street_input)
from journal_market import market_snapshot
from journal_recipes import RECIPE_BY_KEY
from lisbon_landmarks import LANDMARKS
from ferry import FERRY_PIERS, nearby_pier
from lisbon_scene import RIVER_BOTTOM
from tourism import monument_description
from supabase_saves import CloudSave, SaveConflict, SignupError, Supabase
from tycoon import DAY_SECONDS, DAYLIGHT_SECONDS, EGG_COST, INDUSTRIES, SITES, TRADES, ROULETTE_POCKETS, Town, roulette_color
from vehicles import VEHICLES
from navigation import directions
from oriente_station import BOUNDS as ORIENTE_BOUNDS, station_svg


PLACES = {site.name: site for site in OPEN_SITES}
DEFAULT_DESTINATION = "No destination"
ROOT = Path(__file__).resolve().parent
street_map = declare_component("foundry_street", path=str(ROOT / "street"))
START_MESSAGE = "Buy materials, turn them into products, and sell them to grow your business."
SAVE_ERRORS = (OSError, ValueError, KeyError, TypeError)

st.set_page_config(page_title="Foundry Town", layout="wide")


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


cloud = cloud_client()
cloud_session = st.session_state.get("cloud_session")
cloud_store = CloudSave(cloud, cloud_session) if cloud and cloud_session else None


def load_game():
    town, revision = cloud_store.load() if cloud_store else (Town(), 0)
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
        if cloud_store:
            st.session_state.revision = cloud_store.save(candidate, st.session_state.revision)
    except SaveConflict:
        st.session_state.cloud_conflict = True
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
    floor = b64encode((ROOT / "street" / "scenes" / "lisbon_exchange.webp").read_bytes()).decode("ascii")
    st.html(f"""<style>
        .st-key-exchange_floor {{
            background-image: linear-gradient(180deg, #0a1623bf, transparent 38%, #0a162366),
                              url("data:image/webp;base64,{floor}");
        }}
    </style>""")
    with st.container(key="exchange_floor"):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.title("Bolsa de Lisboa", anchor=False, width="content")
            st.button("Leave exchange", key="exchange_leave", shortcut="Escape", on_click=leave_building)
        quotes_column, ticket_column = st.columns((1.45, 1), gap="large")
        with quotes_column:
            with st.container(key="exchange_quotes"):
                st.subheader("All stocks", anchor=False)
                st.caption(f"Day {town.day} · Current prices per share")
                st.dataframe([
                    {"Symbol": row["symbol"], "Stock": row["name"],
                     "Buy": f"${row['ask']:,}", "Sell": f"${row['bid']:,}",
                     "Day change": f"${row['day_change']:+d}",
                     "Change %": f"{row['day_change_percent']:+.2f}%"}
                    for row in rows
                ], hide_index=True, width="stretch")
                st.caption("Day change compares the buy price with the previous close. "
                           "Prices update at the end of each game day.")
        with ticket_column:
            with st.container(key="exchange_ticket"):
                st.subheader("Trade shares", anchor=False)
                asset = st.selectbox("Investment", exchange.ASSETS, format_func=lambda item: item.name)
                quantity = st.number_input("Shares", 1, asset.cap)
                selected = next(row for row in rows if row["symbol"] == asset.symbol)
                st.markdown(f"Buy **\\${selected['ask']:,}** · Sell **\\${selected['bid']:,}** per share  \n"
                            f"**{selected['owned']} owned** · Purchase total **\\${selected['ask'] * quantity:,}**")
                with st.container(key="exchange_actions"):
                    buy, sell = st.columns(2)
                    buy.button("Buy shares", width="stretch", type="primary", on_click=inside,
                               args=(exchange.buy_shares, asset.symbol, quantity))
                    sell.button("Sell shares", width="stretch", on_click=inside,
                                args=(exchange.sell_shares, asset.symbol, quantity))
                if reply := st.session_state.get("reply"):
                    st.info(reply.replace("$", "\\$"))
                with st.expander("Share prices and holdings"):
                    st.dataframe(
                        [{"Investment": row["name"], "Buy": row["ask"], "Sell": row["bid"],
                          "Owned": row["owned"], "Cost basis": row["cost_basis"], "Last dividend": row["last_payout"]}
                         for row in rows], hide_index=True,
                    )


def production_batches(town):
    """Uncollected batches, separate from the items already in the bag."""
    orders = [(trade.product, order) for trade, order in zip(TRADES, town.orders)]
    orders.append(("Precision machinery", town.tier2_order))
    orders.extend((INDUSTRIES[role].product, order) for role, order in town.industry_orders.items())
    batches = [{"product": product, "quantity": order.quantity,
             "seconds": max(0.0, order.ready_at - town.elapsed)}
            for product, order in orders if order is not None]
    for recipe in innovation.TIER3_RECIPES:
        order = town.innovation["orders"][recipe.key]
        if order:
            batches.append({"product": recipe.product, "quantity": order["quantity"],
                            "seconds": max(0.0, order["remaining"])})
    return batches


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
        if st.session_state.town.pending_level is not None:
            return
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
        night=town.market_elapsed % DAY_SECONDS >= DAYLIGHT_SECONDS, facing=town.facing,
        vehicle=town.vehicle, stowed_vehicle=town.stowed_vehicle, hint=hint,
        speed=town.movement_speed, collision=COLLISION_MAP, life=STREET_LIFE,
        cash=town.cash, on_bridge=town.bridge_journey is not None, ferry=st.session_state.get("ferry"),
        station_bounds=ORIENTE_BOUNDS,
        alert=st.session_state.get("alert"),
        production=production_batches(town),
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
            {"name": pier.name, "x": pier.x, "y": pier.y, "color": "#91dfff", "label_on_map": True}
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
    site_inside = PLACES.get(name, MONASTERY) if name else None
    if site_inside is not None and site_inside != MONASTERY and site_inside.role == "EXCHANGE":
        district_exchange()
        return
    with st.container(key="foundry_route"):
        # One row: the latest message, then Destination, Show route and the hints switch.
        feedback, choose, route_button, hints = st.columns((4, 2, 2, 1), vertical_alignment="center")
        destination = choose.selectbox("Destination", [DEFAULT_DESTINATION, *PLACES, MONASTERY],
                                       format_func=place_name, key="destination", label_visibility="collapsed")
        hints.toggle("💡 Show hints", value=True, key="show_hints")
        hint = next_move(town, name)
        target = hint and hint["target"]
        route_button.button(f"Show route to {place_name(target)}" if target else "Show route", width="stretch",
                            disabled=not (st.session_state.show_hints and target and target != destination),
                            on_click=st.session_state.update, kwargs={"destination": target})
        if town.message:
            feedback.info(localize_place_names(town.message))
    if site_inside is not None:
        building(site_inside)
    play_street(site_inside)


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
        "PASTELARIA": "Bake, collect or sell pastries",
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
    """Render information and controls alongside the building scene."""
    if site == MONASTERY:
        st.caption(f"Casino luck +{town.casino_luck}% · Maximum +20%")
        return
    if site.role == "CASINO":
        st.caption(f"Monastery luck: your odds are {town.casino_luck}% better")


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
    x, y, width, height = ORIENTE_BOUNDS
    st.html(f'<div style="position:relative"><img src="data:image/webp;base64,{map_art}" '
            'alt="Foundry Town · Lisbon and Almada" style="width:100%;display:block">'
            f'<img src="data:image/svg+xml;base64,{station}" alt="Gare do Oriente" '
            f'style="position:absolute;left:{x/2400*100}%;top:{y/1780*100}%;width:{width/2400*100}%;'
            f'height:{height/1780*100}%">'
            f'<img src="data:image/svg+xml;base64,{city}" alt="City buildings" '
            'style="position:absolute;inset:0;width:100%;height:100%"></div>')
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
     "You start in Lisbon with **$60** and a 12-slot bag. Grow your business to **$500** by running trade routes: "
     "buy materials, turn them into products, and sell the products for more than they cost."),
    ("1 · Buy materials", "buy.webp",
     "Walk with **WASD** or the **arrow keys** to a store with a yellow **BUY MATERIALS** sign and press **E** at "
     "its door. Inside, **E** buys one unit and **Q** buys up to four. Goldenfield Farm sells wheat for $4."),
    ("2 · Make products", "make.webp",
     "Take the materials to a store with a blue **MAKE PRODUCTS** sign. Press **E** to drop them off. Production "
     "takes a few seconds while you play; press **E** again to collect the finished products."),
    ("3 · Sell products", "sell.webp",
     "Bring the products to a green **SELL PRODUCTS** market and press **E** to sell everything you carry. Bread "
     "made from $4 wheat sells for $14. Repeat with bigger batches to grow faster."),
    ("Getting around", "garage.webp",
     "The only car **DEALERSHIP** is in Cacilhas, across the Tagus: take the ferry ($2) from Cais do Sodré "
     "to get there. Vehicles are faster and carry more, and by car the bridges charge a $3 toll toward Lisbon. "
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


def close_tutorial():
    st.session_state.show_tutorial = False
    st.session_state.tutorial_step = 0


@st.dialog("Foundry Town · Lisbon", width="large", dismissible=False)
def start_menu():
    with st.container(key="foundry_waterfront"):
        st.video(
            str(ROOT / "street" / "lisbon_waterfront.webm"),
            format="video/webm",
            autoplay=True,
            loop=True,
            muted=True,
        )
    st.html("""<script>
        (() => {
            const setSpeed = () => {
                const video = document.querySelector(".st-key-foundry_waterfront video");
                if (video) {
                    video.playbackRate = 0.5;
                    observer.disconnect();
                }
            };
            const observer = new MutationObserver(setSpeed);
            observer.observe(document.body, { childList: true, subtree: true });
            setSpeed();
        })();
    </script>""", unsafe_allow_javascript=True)
    with st.container(key="foundry_start"):
        fullscreen_control("menu")
        st.title("Foundry Town")
        st.caption("Build your fortune in Lisbon")
        play, rules = st.tabs(["Play", "Rules & How to Play"])
        with play:
            start_menu_card()
        with rules:
            start_menu_rules()


def start_menu_card():
    if notice := st.session_state.pop("sign_out_notice", ""):
        st.warning(notice)
    town = st.session_state.town
    can_continue = bool(st.session_state.revision or st.session_state.get("started"))
    if st.button("New Game", key="foundry_new_game", width="stretch", type="primary"):
        if can_continue:
            st.session_state.confirm_restart = True
        elif not cloud_store or save_town(Town()):
            enter_game(new_game=True)
        else:
            st.error(st.session_state.save_error)
    if st.button("Continue", key="foundry_continue", width="stretch", disabled=not can_continue):
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
    if cloud:
        cloud_account()
    if can_continue:
        st.caption(f"Continue with ${town.cash:,} in cash.")


def start_menu_rules():
    st.markdown(
        "**Goal** · Start with $60 and grow to $500, then keep growing through trading, vehicles and "
        "business ownership.\n\n"
        "**Controls** · Move with **WASD** or the **arrow keys**. Press **E** at a door to go inside and **Esc** "
        "to leave. Inside: **E** buys, makes or sells, **Q** buys up to four.\n\n"
        "**Trade route** · Buy materials at a yellow store, make products at a blue store, sell them at a green "
        "market. Example: wheat at Goldenfield Farm → bread at Sunrise Bakery → Daily Bread Market.\n\n"
        "**Getting around** · The ferry crosses the Tagus for $2 on foot; with a vehicle the bridges charge "
        "$3 toward Lisbon. Choose a **Destination** next to the message above the map to see the route.".replace("$", "\\$"))


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

    with st.expander("Sign in / Create account", icon=":material/cloud:", key="foundry_account"):
        st.caption("Signing in opens your cloud save. A new account can save your current guest game.")
        with st.form("cloud_account", clear_on_submit=True):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            sign_in = st.form_submit_button("Sign in", type="primary")
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
  [data-testid="stMainBlockContainer"]:has(.st-key-foundry_play) {{
    padding-inline: clamp(0.375rem, 1vw, 1rem);
    padding-top: 0.375rem;
    padding-bottom: 0.5rem;
  }}
  body:has(.st-key-foundry_play) [data-testid="stHeader"] {{
    display: none;
  }}
  [data-testid="stMainBlockContainer"]:has(.st-key-foundry_play) > [data-testid="stVerticalBlock"],
  .st-key-foundry_play,
  .st-key-foundry_hud {{
    gap: 0.35rem;
  }}
  .st-key-foundry_play iframe {{
    display: block;
  }}
  .st-key-foundry_play [data-testid="stAlertContainer"] {{
    padding-block: 0.25rem;
  }}
  .st-key-exchange_floor {{
    min-height: calc(100dvh - 4.5rem);
    padding: clamp(1rem, 3vw, 2.5rem);
    border-radius: 0.875rem;
    background-color: #132231;
    background-position: 35% center;
    background-size: cover;
    color: #f5f8fc;
  }}
  .st-key-exchange_floor h1 {{
    padding: 0;
    color: #fff3d4;
    font-size: clamp(1.3rem, 4vw, 2.5rem);
    text-shadow: 0 2px 6px #09131d;
  }}
  .st-key-exchange_quotes {{
    margin-top: clamp(1.75rem, 8dvh, 5rem);
    padding: 1rem;
    border: 1px solid #587482;
    border-radius: 0.875rem;
    background: #102331f2;
    color: #e7eff5;
  }}
  .st-key-exchange_quotes h2, .st-key-exchange_quotes [data-testid="stCaptionContainer"] p {{
    color: #e7eff5;
  }}
  .st-key-exchange_ticket {{
    max-width: 26rem;
    margin: clamp(1.75rem, 8dvh, 5rem) 0 0 auto;
    padding: clamp(1rem, 2.5vw, 1.5rem);
    border: 1px solid #587482;
    border-radius: 0.875rem;
    background: #102331f7;
    box-shadow: 0 12px 35px #07111b73;
  }}
  .st-key-exchange_ticket h2 {{
    padding: 0;
    color: #ffd997;
    font-size: 1.375rem;
  }}
  .st-key-exchange_ticket [data-testid="stWidgetLabel"] p,
  .st-key-exchange_ticket summary,
  .st-key-exchange_ticket .stMarkdown p {{ color: #e7eff5; }}
  .st-key-exchange_ticket .stMarkdown strong {{ color: #ffd997; }}
  .st-key-exchange_ticket details {{ border-color: #587482; }}
  .st-key-exchange_floor button[data-testid="stBaseButton-secondary"] {{
    border-color: #819eaf;
    background: #244254;
    color: #f5f8fc;
  }}
  .st-key-exchange_floor button[data-testid="stBaseButton-secondary"]:hover {{
    background: #36576c;
    color: #fff;
  }}
  .st-key-exchange_actions button[data-testid="stBaseButton-primary"] {{
    border-color: #eac280;
    background: #eac280;
    color: #132231;
  }}
  .st-key-exchange_actions button[data-testid="stBaseButton-primary"]:hover {{
    background: #ffda98;
    color: #132231;
  }}
  .st-key-exchange_floor button[data-testid^="stBaseButton"]:focus-visible {{
    outline: 2px solid #ffd997;
    outline-offset: 3px;
  }}
  @media (max-width: 640px) {{
    .st-key-exchange_floor {{
      background-position: center, 30% center;
      background-size: cover, auto calc(100% + 12rem);
    }}
    .st-key-exchange_ticket {{
      max-width: none;
      margin-top: clamp(4rem, 24vw, 8rem);
    }}
    .st-key-exchange_actions [data-testid="stHorizontalBlock"] {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem;
    }}
    .st-key-exchange_actions [data-testid="stColumn"] {{ width: auto !important; min-width: 0; }}
  }}
  body:has(.st-key-exchange_floor) .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
    grid-template-columns: minmax(0, 1fr) auto auto;
  }}
  body:has(.st-key-exchange_floor) .st-key-foundry_hud [data-testid="stColumn"]:is(:nth-child(1), :nth-child(3), :nth-child(4), :nth-child(5), :nth-child(6)) {{
    display: none;
  }}
  body:has(.st-key-exchange_floor) .st-key-foundry_hud [data-testid="stColumn"]:is(:nth-child(2), :nth-child(7), :nth-child(8)) {{
    grid-row: 1;
    grid-column: auto;
  }}
  .st-key-foundry_hud [data-testid="stProgress"] {{
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 0.5rem;
  }}
  .st-key-foundry_hud [data-testid="stProgress"] > div {{
    padding-bottom: 0;
  }}
  /* Centre the level-complete box on screen. (Moving the box itself pushed its top out of view.) */
  [data-testid="stDialog"]:has(.st-key-level_complete) {{
    align-items: center;
  }}
  section[role="dialog"]:has(.st-key-foundry_start) {{
    position: fixed !important;
    inset: 0 !important;
    transform: none !important;
    width: 100vw !important;
    max-width: none !important;
    height: 100dvh !important;
    max-height: none !important;
    overflow-y: auto;
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
    width: min(100%, 43rem);
    margin: clamp(1.75rem, 45dvh - 10rem, 18rem) auto 1rem;
    padding: clamp(1rem, 4vw, 1.5rem) clamp(1rem, 7vw, 7rem);
    border-radius: 1rem;
    background: #132231;
    color: #f5f8fc;
    color-scheme: dark;
  }}
  .st-key-foundry_start:has(.st-key-foundry_account details[open]) {{ margin-top: 2rem; }}
  .st-key-foundry_start:has([role="tab"]:nth-child(2)[aria-selected="true"]) {{
    margin-top: clamp(2rem, 24dvh - 5rem, 8rem);
  }}
  .st-key-foundry_start h1 {{
    padding: 0;
    color: #f7d390;
    font-size: clamp(1.5rem, 5vw, 1.875rem);
    text-align: center;
    text-transform: uppercase;
    letter-spacing: normal;
    font-family: system-ui, sans-serif;
  }}
  .st-key-foundry_start [data-testid="stCaptionContainer"] p {{
    color: #c3d6e0;
    opacity: 1;
    text-align: center;
  }}
  .st-key-foundry_start [data-testid="stCaptionContainer"]:not([role="tabpanel"] *) p {{
    text-transform: uppercase;
  }}
  .st-key-foundry_start [role="tablist"] {{ justify-content: center; }}
  .st-key-foundry_start [role="tab"] {{ color: #c3d6e0; }}
  .st-key-foundry_start [role="tab"][aria-selected="true"],
  .st-key-foundry_start [role="tabpanel"] strong {{ color: #f7d390; }}
  .st-key-foundry_start [role="tab"][aria-selected="true"] {{ box-shadow: inset 0 -2px #ddb679; }}
  .st-key-foundry_start .react-aria-SelectionIndicator {{ visibility: hidden; }}
  .st-key-foundry_start [role="tabpanel"] > [data-testid="stVerticalBlock"] {{ gap: 0.625rem; }}
  :is(.st-key-foundry_new_game, .st-key-foundry_continue) button,
  .st-key-foundry_account summary {{
    min-height: 4rem;
    border: 1px solid #819eaf;
    border-radius: 1rem;
    background: #264153;
    color: #f5f8fc;
    text-transform: uppercase;
  }}
  :is(.st-key-foundry_new_game, .st-key-foundry_continue) button p,
  .st-key-foundry_account summary p {{
    font-family: system-ui, sans-serif;
    font-size: clamp(0.875rem, 3.75vw, 1.125rem);
    font-weight: 650;
  }}
  .st-key-foundry_new_game button {{
    background: #ddb679;
    border-color: #ddb679;
    color: #132231;
  }}
  .st-key-foundry_new_game button:hover {{ background: #f0cc91; color: #132231; }}
  .st-key-foundry_continue button:hover:not(:disabled) {{ background: #36576c; color: #fff; }}
  .st-key-foundry_continue button:disabled {{
    background: #203546;
    border-color: #587182;
    color: #a7bbc7;
  }}
  .st-key-foundry_account details {{ border: 0; }}
  .st-key-foundry_account summary {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.25rem;
    min-height: 5.625rem;
    background: #334a59;
    border-color: #ddb679;
    text-align: center;
  }}
  .st-key-foundry_account summary:hover {{ background: #3c5667; color: #fff; }}
  .st-key-foundry_account summary > span {{ justify-content: center; }}
  .st-key-foundry_account summary > span > div {{ flex: 0 1 auto; min-width: 0; width: auto; }}
  .st-key-foundry_account summary [data-testid="stExpanderIcon"] {{ color: #f7d390; }}
  .st-key-foundry_account summary::after {{
    content: "Save your game across devices";
    color: #c3d6e0;
    font-size: 0.875rem;
    text-transform: none;
  }}
  .st-key-foundry_account [data-testid="stForm"] {{
    border-color: #587182;
  }}
  .st-key-foundry_account [data-testid="stWidgetLabel"] p {{
    color: #f5f8fc;
  }}
  .st-key-foundry_account [data-testid="stTextInputRootElement"] {{
    background: #f0f4f8;
    color-scheme: light;
  }}
  .st-key-foundry_account [data-testid="stTextInputRootElement"] :is(input, button) {{
    color: #132231;
  }}
  .st-key-foundry_account [data-testid="stBaseButton-primaryFormSubmit"] {{
    background: #ddb679;
    border-color: #ddb679;
    color: #132231;
  }}
  .st-key-foundry_account [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    background: #f0cc91;
  }}
  .st-key-foundry_account [data-testid="stBaseButton-secondaryFormSubmit"] {{
    background: #264153;
    border-color: #819eaf;
    color: #f5f8fc;
  }}
  .st-key-foundry_account [data-testid="stBaseButton-secondaryFormSubmit"]:hover {{
    background: #36576c;
  }}
  .st-key-foundry_account [data-testid="stTextInputRootElement"]:focus-within,
  .st-key-foundry_account [data-testid="stFormSubmitButton"] button:focus-visible {{
    outline: 2px solid #f7d390;
    outline-offset: 3px;
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
    min-height: 2rem;
    white-space: nowrap;
  }}
  .st-key-foundry_hud {{
    background: #101f28;
    border: 1px solid #31515d;
    border-radius: 8px;
    padding: 0.25rem 0.5rem;
    color: #fff3dc;
  }}
  .st-key-foundry_hud h1 {{
    color: #ffda86;
    font-size: 1rem;
    padding: 0;
  }}
  .st-key-foundry_hud [data-testid="stHeading"] [data-testid="stMarkdownContainer"] {{
    margin-bottom: 0;
  }}
  .st-key-foundry_hud [data-testid="stMetric"] {{
    display: flex;
    flex-direction: row;
    align-items: baseline;
    gap: 0.35rem;
    white-space: nowrap;
  }}
  .st-key-foundry_hud [data-testid="stMetricLabel"] p {{ color: #b7cacb; }}
  .st-key-foundry_hud [data-testid="stMetricValue"] {{
    color: #ffda86;
    font-size: 1rem;
    font-weight: 700;
  }}
  .st-key-foundry_hud [data-testid="stPopoverButton"] {{
    color: #fff3dc;
    background: #16303a;
    border-color: #577480;
  }}
  .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
  .st-key-foundry_route > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
    display: grid;
    align-items: center;
    gap: 0.375rem 0.75rem;
  }}
  .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
    grid-template-columns: repeat(4, auto) minmax(8rem, 1fr) auto auto auto;
    column-gap: 1.25rem;
  }}
  /* More room between the groups: title | cash, bag, day | goal bar and Inventory | Fullscreen, Menu */
  .st-key-foundry_hud [data-testid="stColumn"]:nth-child(1) {{ margin-right: 1rem; }}
  .st-key-foundry_hud [data-testid="stColumn"]:nth-child(5) {{ margin-left: 1rem; }}
  .st-key-foundry_hud [data-testid="stColumn"]:nth-child(7) {{ margin-left: 1rem; }}
  /* The Inventory button shows its key, I, as a small keyboard key */
  .st-key-inventory [data-testid="stPopoverButton"] [data-testid="stMarkdownContainer"] p::after {{
    content: "I";
    display: inline-block;
    margin-left: 0.5rem;
    min-width: 1.15rem;
    padding: 0 0.3rem;
    border-radius: 4px;
    background: #f4f1ea;
    color: #2b2f36;
    box-shadow: 0 2px 0 #a9a49a;
    font: 700 0.72rem/1.15rem system-ui, sans-serif;
    text-align: center;
  }}
  .st-key-foundry_route > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
    grid-template-columns: minmax(0, 1fr) minmax(10rem, 15rem) auto auto;
  }}
  .st-key-foundry_route [data-testid="stAlert"] > div {{  /* A slim message, as tall as the controls beside it */
    padding-block: 0.4rem;
  }}
  :is(.st-key-foundry_hud, .st-key-foundry_route) [data-testid="stColumn"] {{
    width: auto !important;
    min-width: 0;
  }}
  :is(.st-key-foundry_hud, .st-key-foundry_route) :is([data-testid="stPopoverButton"], [data-testid="stBaseButton-secondary"]) {{
    min-height: 2rem;
    padding-block: 0.125rem;
  }}
  @media (max-width: 740px) {{
    .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
      grid-template-columns: repeat(4, auto) minmax(0, 1fr) auto auto;
    }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(5) {{ grid-row: 2; grid-column: 1 / 6; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(6) {{ grid-row: 2; grid-column: 6 / -1; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(7) {{ grid-row: 1; grid-column: 6; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(8) {{ grid-row: 1; grid-column: 7; }}
    .st-key-foundry_hud [data-testid="stColumn"] {{ margin: 0 !important; }}  /* Less room on small screens */
    .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{ column-gap: 0.9rem; }}
  }}
  @media (max-width: 560px) {{
    .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
    .st-key-foundry_route > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
      column-gap: 0.375rem;
    }}
    .st-key-foundry_hud > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
      grid-template-columns: minmax(0, 1fr) auto auto;
    }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(1) {{ grid-row: 1; grid-column: 1; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(2) {{ grid-row: 2; grid-column: 1; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(3) {{ grid-row: 2; grid-column: 2; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(4) {{ grid-row: 2; grid-column: 3; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(5) {{ grid-row: 3; grid-column: 1 / 3; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(6) {{ grid-row: 3; grid-column: 3; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(7) {{ grid-row: 1; grid-column: 2; }}
    .st-key-foundry_hud [data-testid="stColumn"]:nth-child(8) {{ grid-row: 1; grid-column: 3; }}
    .st-key-foundry_route > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
      grid-template-columns: minmax(0, 1fr) auto;
    }}
    /* Phones: the message, then Destination with the hints switch, then Show route */
    .st-key-foundry_route [data-testid="stColumn"]:nth-child(1) {{ grid-column: 1 / -1; }}
    .st-key-foundry_route [data-testid="stColumn"]:nth-child(2) {{ grid-row: 2; grid-column: 1; }}
    .st-key-foundry_route [data-testid="stColumn"]:nth-child(4) {{ grid-row: 2; grid-column: 2; }}
    .st-key-foundry_route [data-testid="stColumn"]:nth-child(3) {{ grid-row: 3; grid-column: 1 / -1; }}
  }}
  body:has(.st-key-foundry_start) #foundry-fullscreen-game {{ display: none; }}
</style>
""")
page = st.session_state.get("town_page", "Game")
PAGES = {"Game": places, "Market & recipes": market, "Landmarks": landmarks}
if page not in PAGES:  # A page from an older version of the game
    page = st.session_state.town_page = "Game"
with st.container(key="foundry_hud"):
    title, cash, cargo, day, goal_bar, bag, display, menu = st.columns(8, vertical_alignment="center")
    title.title("Foundry Town")
    cash.metric("Cash", f"${town.cash:,}")
    cargo.metric("Bag", f"{town.cargo} / {town.carry_capacity}")
    with bag.popover("Inventory", key="inventory"):  # Next to the goal bar; I opens it (street.js)
        st.caption(f"{town.reserved} slots reserved for goods awaiting collection.")
        items = [(trade.supply, town.supplies[i]) for i, trade in enumerate(TRADES)]
        items += [(trade.product, town.goods[i]) for i, trade in enumerate(TRADES)]
        items += [("Eggs", town.eggs), ("Precision machinery", town.tier2_goods)]
        items += [(INDUSTRIES[role].product, quantity) for role, quantity in town.industry_goods.items()]
        items += [(recipe.product, town.innovation["goods"][recipe.key]) for recipe in innovation.TIER3_RECIPES]
        for name, quantity in items:
            st.text(f"{name}: {quantity}")
    day.metric("Day", town.day)
    with display:
        fullscreen_control("game")
    goal, fraction = town.level_progress()
    goal_bar.progress(float(fraction), text=goal.replace("$", "\\$"))
    with menu.popover("Menu", key=f"town_menu_{page}", width="stretch"):
        for label in PAGES:
            st.button(label, type="primary" if page == label else "secondary", width="stretch",
                      on_click=st.session_state.update, kwargs={"town_page": label})
        st.button("Start menu", width="stretch",
                  on_click=st.session_state.update, kwargs={"show_menu": True})
        if cloud_store:
            if st.button("Save progress", width="stretch"):
                if save_town(town):
                    st.toast("Progress saved.")
            if st.button("Reload cloud progress", width="stretch"):
                try:
                    load_game()
                    st.rerun()
                except SAVE_ERRORS:
                    st.session_state.save_error = "Could not reload progress. Check your save settings and try again."

def play_notices():
    if st.session_state.save_error:
        st.error(st.session_state.save_error)


@st.dialog("Level complete", dismissible=False)
def level_complete():
    level = town.pending_level
    with st.container(key="level_complete"):
        st.subheader(f"Level {level} complete!")
        st.write({
            1: "You sold your first product! Next: reach $500 cash to complete Level 2.",
            2: "You reached $500 cash! Continue to Level 3 and reach $2,000 cash?",
            3: "You successfully completed the game! Good job!",
        }[level].replace("$", "\\$"))  # A pair of $ signs would otherwise show as a maths formula
        label = {1: "Continue to Level 2", 2: "Continue to Level 3", 3: "Keep playing"}[level]
        if st.button(label, type="primary"):
            act(Town.acknowledge_level)
            st.rerun()
        if st.button("Return to start menu"):
            if save_town(town):
                st.session_state.show_menu = True
                st.rerun()
        if st.session_state.save_error:
            st.error(st.session_state.save_error)


if page == "Game":
    with st.container(key="foundry_play"):
        play_notices()
        places()
else:
    play_notices()
    PAGES[page]()
    if town.message:
        st.info(localize_place_names(town.message))

if st.session_state.get("show_menu", True):
    start_menu()
elif st.session_state.get("show_tutorial"):
    tutorial()

elif town.pending_level is not None:
    level_complete()
