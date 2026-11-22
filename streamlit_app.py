"""Foundry Town's Streamlit interface."""
from base64 import b64encode
from copy import deepcopy
from functools import lru_cache
from html import escape
import os
from pathlib import Path
import sqlite3
from time import monotonic

import streamlit as st
from streamlit.components.v1 import declare_component

import businesses
import contracts
import exchange
import innovation
import logistics
from browser_game import (COLLISION_MAP, MONASTERY, STREET_LIFE, LocalSave, building_at, greeting, scene_for,
                          SaveConflict, entrance, place_vehicle_on_road, street_event, street_input)
from journal_market import market_snapshot
from journal_recipes import RECIPE_BY_KEY
from lisbon_landmarks import LANDMARKS
from ferry import FERRY_PIERS, nearby_pier
from lisbon_scene import RIVER_BOTTOM
from tourism import monument_description
from tycoon import DAY_SECONDS, INDUSTRIES, SITES, TRADES, ROULETTE_POCKETS, Town, roulette_color
from vehicles import VEHICLES
from navigation import directions


PLACES = {site.name: site for site in SITES}
ROOT = Path(__file__).resolve().parent
street_map = declare_component("foundry_street", path=str(ROOT / "street"))
START_MESSAGE = "Buy materials, turn them into products, and sell them to grow your business."
SAVE_ERRORS = (OSError, sqlite3.Error, ValueError, KeyError, TypeError)

st.set_page_config(page_title="Foundry Town", layout="wide")
save_path = os.environ.get("FOUNDRY_LOCAL_DB")
store = LocalSave(save_path) if save_path else None


def load_game():
    town, revision = store.load() if store else (Town(), 0)
    if not revision:
        town.message = START_MESSAGE
    st.session_state.town = town
    st.session_state.revision = revision
    st.session_state.save_error = ""


if "town" not in st.session_state:
    try:
        load_game()
    except SAVE_ERRORS:
        st.error("Could not open the local save. Check file permissions or restore the database, then reload.")
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
    if (before.y >= RIVER_BOTTOM) != (candidate.y >= RIVER_BOTTOM) and before.vehicle is None:
        # On foot, changing banks means a ferry ride: the street map plays the crossing.
        previous = st.session_state.get("ferry", {}).get("id", 0)
        st.session_state.ferry = {"id": previous + 1, "heading": 1 if candidate.y >= RIVER_BOTTOM else -1}
    saved = save_town(candidate)
    return result if operation is street_event and saved else saved


def save_town(candidate):
    try:
        if store:
            st.session_state.revision = store.save(candidate, st.session_state.revision)
    except SaveConflict:
        st.session_state.save_error = "Another tab updated this save. Reload progress before continuing."
        return
    except SAVE_ERRORS:
        st.session_state.save_error = "Could not save this action. Check local storage and try again."
        return
    st.session_state.town = candidate
    st.session_state.save_error = ""
    return True


def button(label, operation, *args, key=None, **options):
    st.button(label, key=key, on_click=act, args=(operation, *args), **options)


def interact(town, bulk=False):
    town.interact(bulk)


def eggs(town, bulk=False):
    town.buy_eggs(bulk)


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


def travel(position, label, *, key):
    if (town.x-position[0])**2 + (town.y-position[1])**2 <= contracts.DELIVERY_REACH**2:
        return True
    st.button(f"Show directions to {label}", key=key, on_click=show_directions, args=(label,))
    return False


def research():
    for branch in innovation.RESEARCH_BRANCHES:
        quote = innovation.research_quote(town, branch.key)
        if quote is None:
            st.write(f"{branch.name} · Complete")
        else:
            node = innovation.next_research(town, branch.key)
            button(f"{branch.name} · Level {node.level} · ${quote:,} · {node.seconds}s",
                   Town.start_research, branch.key)
    project = town.innovation["project"]
    if project:
        st.info(f"Research underway · {project['remaining']:.0f}s remaining")
    for recipe in innovation.unlocked_recipes(town):
        with st.expander(recipe.product):
            st.write(", ".join(f"{item.quantity} × {item.label}" for item in recipe.ingredients))
            lab = town.innovation
            key = recipe.key
            st.write(f"{lab['goods'][key]} in bag · ${lab['prices'][key]} each · {lab['demand'][key]} buyers")
            if order := lab["orders"][key]:
                st.caption(f"{order['quantity']} ordered · {order['remaining']:.0f}s remaining")
            quantity = st.number_input("Quantity", 1, 999, key=f"craft-{recipe.key}")
            button("Fabricate", Town.start_fabrication, recipe.key, quantity, key=f"make-{recipe.key}")
            button("Collect", Town.collect_research_products, recipe.key, key=f"collect-{recipe.key}")
            button("Sell", Town.sell_research_products, recipe.key, key=f"sell-{recipe.key}")


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


def play_street():
    place_vehicle_on_road(town)
    nearby = town.nearby()
    pier = nearby_pier(town.x, town.y)
    hint = "Follow the marked entrances to buy, make, and sell."
    if nearby:
        hint = f"{nearby.name} · {site_status(nearby)}"
    if pier:
        hint = f"{pier.name} · Take the ferry for $2"

    def play():
        event = st.session_state.get("street_map")
        if not isinstance(event, dict):
            return
        name = act(street_event, event)
        if name:
            enter_building(name)

    last_input = st.session_state.get("street_map")
    ack = last_input.get("id") if isinstance(last_input, dict) else None
    street_map(
        key="street_map", on_change=play, x=town.x, y=town.y, ack=ack,
        night=town.market_elapsed % DAY_SECONDS >= 180, facing=town.facing,
        vehicle=town.vehicle, stowed_vehicle=town.stowed_vehicle, hint=hint, message=town.message,
        speed=town.movement_speed, collision=COLLISION_MAP, life=STREET_LIFE,
        cash=town.cash, on_bridge=town.bridge_journey is not None, ferry=st.session_state.get("ferry"),
        route=directions(town, destination_point(st.session_state.get("destination", "Goldenfield Farm"))),
        suppliers=[{"x": site.door[0], "y": site.door[1], "trade": site.trade,
                    "cost": town.costs[site.trade]} for site in SITES if site.role == "SUPPLIER"],
        free_slots=town.carry_capacity-town.cargo-town.reserved,
        locations=[
            {"name": site.name, "x": site.door[0], "y": site.door[1], "color": site.color}
            for site in SITES
        ] + [
            {"name": pier.name, "x": pier.x, "y": pier.y, "color": "#91dfff"}
            for pier in FERRY_PIERS
        ],
    )


def site_status(site):
    status = town.site_status(site)
    for shortcut in (" · B Manage", " · L Deliveries", " (F / R)", "E · ", "E "):
        status = status.replace(shortcut, "")
    return status


def destination_point(name):
    if name == MONASTERY:
        left, _, right, bottom = LANDMARKS[0].bounds
        return (left+right)/2, bottom+16
    if name in PLACES:
        return entrance(PLACES[name])
    location = next(location for location in contracts.LOCATIONS if location.name == name)
    return location.x, location.y


def places():
    name = st.session_state.get("inside")
    if not (name and building_at(town) == name):
        st.session_state.inside = name = None
    destination = st.selectbox("Destination", [*PLACES, MONASTERY, *(location.name for location in contracts.LOCATIONS)],
                              index=list(PLACES).index("Goldenfield Farm"),
                              key="destination")
    if name is None:
        play_street()
        st.caption(directions(town, destination_point(destination))["instruction"])
    if name:
        building(PLACES.get(name, MONASTERY))


def enter_building(name):
    st.session_state.inside = name
    st.session_state.reply = None
    st.session_state.focus_building = True
    if name == MONASTERY:
        st.session_state.reply = st.session_state.town.message


def leave_building():
    st.session_state.inside = None


def inside(operation, *args):
    """Run a building action; the vendor answers with the result."""
    saved = act(operation, *args)
    st.session_state.reply = st.session_state.town.message
    return saved


def action(label, operation, *args, key=None, shortcut=None, primary=True, **options):
    st.button(label, key=key, on_click=inside, args=(operation, *args), shortcut=shortcut,
              type="primary" if primary else "secondary", **options)


@lru_cache(maxsize=32)
def scene_image(name):
    return b64encode((ROOT / "street" / "scenes" / f"{name}.webp").read_bytes()).decode("ascii")


def scene(name, layout, speech="", board="", overlay=""):
    """An illustrated scene from the desktop game, with the speech bubble and chalkboard text on top."""
    width, height = layout["size"]

    def box(bounds, text, size, color, extra=""):
        if not bounds or not text:
            return ""
        left, top, right, bottom = bounds
        return (f'<div style="position:absolute;left:{left/width*100}%;top:{top/height*100}%;'
                f'width:{(right-left)/width*100}%;height:{(bottom-top)/height*100}%;display:flex;'
                f'align-items:center;justify-content:center;text-align:center;padding:0 2%;box-sizing:border-box;'
                f'font:700 {size/width*100}cqw system-ui,sans-serif;color:{color};{extra}">{escape(text)}</div>')

    board_box = layout["board"] and (layout["board"][0] + 6, layout["board"][1] + 22,
                                     layout["board"][2] - 6, layout["board"][3] - 4)
    st.html(f"""
      <div style="position:relative;container-type:inline-size;max-width:1100px;margin:auto;border-radius:10px;
                  overflow:hidden;box-shadow:0 6px 18px #0005">
        <img src="data:image/webp;base64,{scene_image(name)}" alt="" style="display:block;width:100%">
        {box(layout["bubble"], speech, 12, "#1f2a30")}
        {box(board_box, board, 8.5, "#eef3ea", "font-weight:500")}
        {overlay}
      </div>""")


def building(site):
    """Inside a building: its illustrated scene, the vendor's answer and the building's actions."""
    head, leave = st.columns((4, 1), vertical_alignment="center")
    head.subheader(site if site == MONASTERY else site.name)
    leave.button("Leave", key="leave_building", on_click=leave_building, shortcut="Escape", width="stretch")
    if st.session_state.pop("focus_building", False):
        # The map that had the keyboard is gone. Give it to this building so its keys work at once.
        st.html("""<script>
            // A held E that opened the door keeps repeating; ignore repeats briefly so it doesn't buy.
            const swallow = (event) => { if (event.repeat) { event.preventDefault(); event.stopImmediatePropagation(); } };
            window.addEventListener("keydown", swallow, true);
            setTimeout(() => window.removeEventListener("keydown", swallow, true), 700);
            let tries = 0;
            const claim = () => {
                const leave = document.querySelector(".st-key-leave_building button");
                if (leave) leave.focus({ preventScroll: true });
                else if (tries++ < 40) setTimeout(claim, 50);
            };
            claim();
        </script>""", unsafe_allow_javascript=True)
    speech = st.session_state.get("reply") or greeting(town, site)
    found = scene_for(town, site)
    if site != MONASTERY and site.role == "CASINO":
        casino(found)
        return
    if found:
        board = site_status(site) if site != MONASTERY else ""
        scene(*found, speech=speech, board=board)
    else:
        st.info(speech)
    if site == MONASTERY:
        st.caption(f"Casino luck +{town.casino_luck} percentage points · Maximum +20")
        return
    role = site.role
    if role == "SUPPLIER":
        trade = TRADES[site.trade]
        cols = st.columns(4 if site.trade == 3 else 2)
        with cols[0]:
            action(f"Buy 1 {trade.supply}", interact, shortcut="e", width="stretch")
        with cols[1]:
            action(f"Buy up to 4 {trade.supply}", interact, True, shortcut="q", width="stretch")
        if site.trade == 3:
            with cols[2]:
                action("Buy 1 egg", eggs, shortcut="f", width="stretch")
            with cols[3]:
                action("Buy up to 4 eggs", eggs, True, shortcut="Shift+F", width="stretch")
    elif role == "GARAGE":
        for column, (key, ride) in zip(st.columns(len(VEHICLES)), VEHICLES.items()):
            with column:
                current = town.vehicle == key
                owned = key in town.owned_vehicles or current
                st.image(str(ROOT / "street" / "vehicles" / f"{key}.svg"), width="stretch")
                status = "Your ride" if current else "Owned · Free collection" if owned else f"${ride.price:,}"
                st.markdown(f"**{ride.label}** · {status}")
                st.caption(f"Trunk +{ride.trunk} · {town.bag_size + ride.trunk} cargo · "
                           f"Road {ride.road_speed} · Off-road {ride.offroad_speed}")
                number = str(list(VEHICLES).index(key) + 1)
                label = f"Drive {ride.label} · Free" if owned else f"Buy {ride.label} · ${ride.price:,} · +{ride.trunk} slots"
                action(label, Town.purchase_vehicle, key,
                       key=f"vehicle-{key}", shortcut=number, disabled=current, width="stretch")
    elif role == "WAREHOUSE":
        st.write(f"Personal storage {town.bag_size} · Total cargo {town.carry_capacity}")
        action(f"Add 12 slots · ${300 + town.warehouse_level * 250:,}", warehouse, shortcut="e")
    elif role == "RESEARCH":
        research()
    elif role == "EXCHANGE":
        district_exchange()
    else:
        labels = {
            "FACTORY": "Produce or collect",
            "PUBLIC SHOP": "Stock shop" if businesses.is_owned(town, site) else "Sell carried goods",
            "TIER2": "Craft, collect or sell machinery",
            "PASTELARIA": "Bake, collect or sell pastéis",
            "SHIPYARD": "Start repair or collect payment",
        }
        action(labels[role], interact, shortcut="e")


CHIPS = (5, 10, 25, 50, 100)
POCKET_COLORS = {"red": "#c8313c", "black": "#1b1d22", "green": "#1f8a4c"}
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


def wheel_svg(spin_state, remaining):
    """European roulette wheel. A new spin animates once from the last angle to the winning pocket."""
    from math import cos, radians, sin
    seg = 360 / len(ROULETTE_POCKETS)
    parts = []
    for index, number in enumerate(ROULETTE_POCKETS):
        a0, a1 = radians(index * seg - seg / 2 - 90), radians(index * seg + seg / 2 - 90)
        outer, inner = 190, 140
        path = (f"M{200 + outer * cos(a0):.1f},{200 + outer * sin(a0):.1f} "
                f"A{outer},{outer} 0 0 1 {200 + outer * cos(a1):.1f},{200 + outer * sin(a1):.1f} "
                f"L{200 + inner * cos(a1):.1f},{200 + inner * sin(a1):.1f} "
                f"A{inner},{inner} 0 0 0 {200 + inner * cos(a0):.1f},{200 + inner * sin(a0):.1f} Z")
        parts.append(f'<path d="{path}" fill="{POCKET_COLORS[roulette_color(number)]}" stroke="#c9a24a" '
                     'stroke-width="1"/>')
        mid = radians(index * seg - 90)
        parts.append(f'<text x="{200 + 166 * cos(mid):.1f}" y="{200 + 166 * sin(mid):.1f}" fill="#fff" '
                     f'font-size="13" font-weight="700" text-anchor="middle" dominant-baseline="central" '
                     f'transform="rotate({index * seg:.1f} {200 + 166 * cos(mid):.1f} {200 + 166 * sin(mid):.1f})">'
                     f'{number}</text>')
    angle = spin_state["angle"] if spin_state else 0
    css = ".wheel,.ball{transform-box:view-box;transform-origin:200px 200px}"
    if remaining:
        delay = remaining - SPIN_SECONDS
        css += (f"@keyframes wheel{{from{{transform:rotate({spin_state['from']}deg)}}to{{transform:rotate({angle}deg)}}}}"
                "@keyframes ball{from{transform:rotate(1440deg)}to{transform:rotate(0deg)}}"
                f".wheel{{animation:wheel {SPIN_SECONDS}s cubic-bezier(.12,.6,.2,1) {delay}s both}}"
                f".ball{{animation:ball {SPIN_SECONDS}s cubic-bezier(.2,.5,.25,1) {delay}s both}}")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><style>{css}</style>
        <circle cx="200" cy="200" r="198" fill="#4a2614"/><circle cx="200" cy="200" r="192" fill="#7a4424"/>
        <g class="wheel" style="transform:rotate({angle}deg)">{''.join(parts)}
          <circle cx="200" cy="200" r="140" fill="#6b3d22" stroke="#c9a24a"/>
          <circle cx="200" cy="200" r="100" fill="#8a5a33"/><circle cx="200" cy="200" r="55" fill="#b07a45"/>
          <path d="M200 140V260M140 200H260" stroke="#ffc66c" stroke-width="6" stroke-linecap="round"/>
          <circle cx="200" cy="200" r="16" fill="#ffc66c"/></g>
        <g class="ball"><circle cx="200" cy="{200 - 152 if spin_state else 200 - 178}" r="7" fill="#f7f7f2"
           stroke="#9aa3a6"/></g>
        <path d="M192 4 L208 4 L200 18 Z" fill="#ffc66c"/></svg>"""
    # Streamlit's HTML sanitiser drops inline SVG, so the wheel is an SVG image (CSS animation still runs).
    return f'<img alt="Roulette wheel" style="width:100%;display:block" src="data:image/svg+xml;base64,{b64encode(svg.encode()).decode()}">'


def casino(found):
    name, layout = found
    spin_state = st.session_state.get("spin")
    remaining = spin_remaining()
    wheel = wheel_svg(spin_state, remaining)
    message = st.session_state.get("reply") or greeting(town, PLACES["Foundry Casino"])
    # The result appears when the ball stops.
    reveal = f"animation:reveal 0s {remaining}s both;" if remaining else ""
    result = (f'<style>@keyframes reveal{{from{{opacity:0}}to{{opacity:1}}}}</style>'
              f'<div style="position:absolute;left:0;right:0;top:82%;{reveal}'
              f'text-align:center;font:700 2.6cqw system-ui;color:#fff7e6;text-shadow:0 2px 4px #000">'
              f'{escape(message)}</div>')
    overlay = f'<div style="position:absolute;left:30%;top:4%;width:40%">{wheel}</div>{result}'
    scene(name, layout, overlay=overlay)
    st.caption(f"Monastery luck +{town.casino_luck} percentage points")
    if remaining:
        waiting_for_spin()
    else:
        bet_controls()


@st.fragment(run_every=0.25)
def waiting_for_spin():
    if not spin_remaining():
        st.rerun()
    st.caption("Wait for the wheel to stop before betting again.")
    bet_controls(disabled=True)


def bet_controls(*, disabled=False):
    st.html("""<style>
        .st-key-bet_green button {background:#1f8a4c;color:#fff;border-color:#46be79;}
        .st-key-bet_green button:hover {background:#176b3a;color:#fff;border-color:#8ae4ad;}
        .st-key-bet_green button:focus-visible {outline:3px solid #b5ffd2;outline-offset:2px;}
        .st-key-bet_green button:disabled {background:#1f8a4c;color:#fff;opacity:.5;}
    </style>""")
    st.segmented_control("Chip", CHIPS, default=10, key="chip", format_func=lambda value: f"${value}",
                         disabled=disabled)
    for column, (label, colour, shortcut) in zip(st.columns(3), (
        ("Red · pays 2×", "red", "1"),
        ("Black · pays 2×", "black", "2"),
        ("Green 0 · pays 36×", "green", "3"),
    )):
        column.button(label, on_click=spin, args=(colour,), shortcut=shortcut, width="stretch",
                      type="primary" if colour == "red" else "secondary", disabled=disabled,
                      key="bet_green" if colour == "green" else None)


def market():
    snapshot = market_snapshot(town, TRADES, INDUSTRIES, SITES)
    if snapshot.event_title:
        st.info(f"{snapshot.event_title} · {snapshot.event_detail}")
    st.dataframe([{
        "Product": row.product, "Materials held": row.raw_stock, "Material cost": row.raw_cost,
        "Sale price": row.price, "Stock": row.stock_label, "In production": row.orders,
        "Buyers / jobs": row.remaining_buyers, "Sold today": row.sold_today,
    } for row in snapshot.rows], hide_index=True)
    st.write(f"Revenue ${town.daily_revenue:,} · Expenses ${town.daily_expenses:,} · Net ${town.daily_net_profit:,}")
    if town.last_day_summary:
        summary = town.last_day_summary
        st.caption(f"Day {summary['day']} settled · Tax ${summary['tax']:,} · Dividends ${summary['dividends']:,}")
    st.subheader("Discovered recipes")
    if not town.discovered_recipes:
        st.caption("Operate a production site to discover its recipe.")
    for key in town.discovered_recipes:
        recipe = RECIPE_BY_KEY[key]
        ingredients = ", ".join(f"{quantity} × {name}" for name, quantity in recipe.ingredients)
        st.write(f"**{recipe.title}** · {ingredients} · {recipe.seconds}s")


def contract_board():
    st.caption(f"{contracts.rank_name(town)} · {town.contracts['reputation']} reputation")
    active = town.contracts["active"]
    if active:
        record = st.selectbox("Active contract", active,
                              format_func=lambda row: contracts.active_offer(row).title)
        offer = contracts.active_offer(record)
        left = contracts.remaining_seconds(town, record)
        st.write(f"{record['delivered']} / {record['required']} delivered · {left:.0f}s remaining")
        location = offer.location
        if travel((location.x, location.y), location.name, key="contract-travel"):
            quantity = st.number_input("Delivery quantity", 1, record["required"] - record["delivered"])
            button("Deliver", Town.deliver_contract, record["id"], quantity)
        if st.checkbox("Confirm abandonment (deposited goods are forfeited)", key=f"abandon-{record['id']}"):
            button("Abandon contract", Town.abandon_contract, record["id"])
    offers = contracts.available_offers(town)
    if offers:
        offer = st.selectbox("Available offer", offers, format_func=lambda item: item.title)
        product = contracts.PRODUCT_NAMES[offer.product_key]
        st.write(f"{offer.quantity} × {product} · ${offer.cash:,} · {offer.seconds}s")
        st.caption(offer.location.name)
        button("Accept contract", Town.accept_contract, offer.key)
    else:
        st.caption("No offers available. New recurring offers appear as game time advances.")


def deliveries():
    factories = [site for site in SITES if site.role == "FACTORY"]
    factory = st.selectbox("Factory", factories, format_func=lambda item: item.name)
    effective = town.business_site(factory)
    suppliers = [site.name for site in SITES if site.role == "SUPPLIER" and site.trade == effective.trade]
    source = st.selectbox("Supplier", suppliers)
    kind = st.selectbox("Fleet vehicle", tuple(logistics.FLEET_VEHICLES),
                        format_func=lambda key: logistics.FLEET_VEHICLES[key].label)
    vehicle = logistics.FLEET_VEHICLES[kind]
    button(f"Buy route · ${vehicle.price:,}", Town.create_delivery_route, kind, source, factory.name)
    stock = town.logistics["factories"][factory.name]
    st.write(f"{factory.name} · {stock['output']} finished units ready")
    routes = town.logistics["routes"]
    if not routes:
        st.caption("No delivery routes yet.")
        return
    route = st.selectbox("Manage route", routes,
                         format_func=lambda item: f"#{item['id']} · {item['source']} to {item['destination']}")
    identifier = route["id"]
    st.write(logistics.route_status(route))
    button("Pause route" if route["enabled"] else "Resume route",
           Town.set_delivery_enabled, identifier, not route["enabled"])
    button("Reassign to selected supplier and factory", Town.reassign_delivery_route,
           identifier, source, factory.name)
    button("Remove empty route", Town.remove_delivery_route, identifier)


def manage_businesses():
    sites = [site for site in SITES if site.role in ("FACTORY", "PUBLIC SHOP")]
    site = st.selectbox("Business", sites, format_func=lambda item: item.name)
    if not businesses.is_owned(town, site):
        price = businesses.PURCHASE_PRICES[site.role]
        button(f"Buy business · ${price:,}", Town.purchase_business, site.name)
        return
    for upgrade in ("storage", "equipment"):
        price = businesses.upgrade_cost(town, site, upgrade)
        if price is None:
            st.caption(f"{upgrade.title()} fully upgraded.")
        else:
            button(f"Upgrade {upgrade} · ${price:,}", Town.upgrade_business, site.name, upgrade)
    index = st.selectbox("Specialization", range(len(TRADES)),
                         index=town.business_site(site).trade,
                         format_func=lambda trade: TRADES[trade].product)
    button("Apply specialization", Town.specialize_business, site.name, index)
    if site.role == "PUBLIC SHOP" and travel(entrance(site), site.name, key="shop-travel"):
        button("Stock from bag", Town.stock_business, site.name)
        button("Withdraw stock", Town.withdraw_business, site.name)
        button("Sell from bag", Town.sell_business_carried, site.name)


def landmarks():
    st.image(str(ROOT / "street" / "world_100_day.webp"), caption="Foundry Town · Lisboa and Almada")
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
    town = st.session_state.town
    can_continue = bool(st.session_state.revision or st.session_state.get("started"))
    st.caption(f"Continue with ${town.cash:,} in cash." if can_continue else "Start with $60 and a 12-slot bag.")
    new, resume = st.columns(2)
    if new.button("New Game", width="stretch", type="primary"):
        if can_continue:
            st.session_state.confirm_restart = True
        else:
            enter_game(new_game=True)
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
    with st.expander("Rules & How to Play"):
        st.write("Click the map to focus it. Move with WASD or the arrow keys and press E to interact.")
        st.write("Buy wheat at Goldenfield Farm, make bread at Sunrise Bakery, then sell it at Daily Bread Market.")
        st.write("Reach $500, then keep growing through research, contracts, and business ownership.")


def enter_game(*, new_game=False):
    if new_game:
        st.session_state.town_page = "Game"
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
    padding: clamp(1rem, 3vw, 2rem);
    border: 2px solid #ffc66c;
    border-radius: 12px;
    background: #16303a;
    color: #fff7e6;
    color-scheme: dark;
  }}
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

page = st.session_state.get("town_page", "Game")
with st.container(key="foundry_nav"):
    game, recipes, advanced = st.columns(3, vertical_alignment="center")
    for column, label in ((game, "Game"), (recipes, "Market & recipes")):
        column.button(
            label, type="primary" if page == label else "secondary", width="stretch",
            on_click=st.session_state.update, kwargs={"town_page": label},
        )
    with advanced.popover("More", width="stretch"):
        for label in ("Contracts", "Deliveries", "Businesses", "Landmarks"):
            st.button(
                label, type="primary" if page == label else "secondary", width="stretch",
                on_click=st.session_state.update, kwargs={"town_page": label},
            )
        if store and st.button("Reload local progress", width="stretch"):
            try:
                load_game()
                st.rerun()
            except SAVE_ERRORS:
                st.session_state.save_error = "Could not read local progress. Check the save file."

if st.session_state.save_error:
    st.error(st.session_state.save_error)
if town.won and not town.milestone_acknowledged:
    st.success("You reached the $500 cash milestone.")
    button("Continue building", Town.continue_after_milestone)

{
    "Game": places, "Market & recipes": market, "Contracts": contract_board,
    "Deliveries": deliveries, "Businesses": manage_businesses, "Landmarks": landmarks,
}[page]()

if town.message:
    st.info(town.message)

if st.session_state.get("show_menu", True):
    start_menu()
