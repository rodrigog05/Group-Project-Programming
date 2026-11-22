"""Foundry Town's Streamlit interface."""
from base64 import b64encode
from copy import deepcopy
import os
from pathlib import Path
import sqlite3

import streamlit as st
from streamlit.components.v1 import declare_component

import businesses
import contracts
import exchange
import innovation
import logistics
from browser_game import COLLISION_MAP, STREET_LIFE, LocalSave, SaveConflict, entrance, street_input, visit
from journal_market import market_snapshot
from journal_recipes import RECIPE_BY_KEY
from lisbon_landmarks import LANDMARKS
from ferry import FERRY_PIERS, nearby_pier
from lisbon_scene import RIVER_BOTTOM
from tourism import monument_description
from tycoon import DAY_SECONDS, INDUSTRIES, SITES, TRADES, ROULETTE_POCKETS, Town, roulette_color
from vehicles import VEHICLES


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
    candidate = deepcopy(st.session_state.town)
    if operation is not street_input:
        candidate.message = ""
    if operation(candidate, *args) is False and operation is street_input:
        return
    return save_town(candidate)


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


def roulette(town, choice, stake):
    if town.cash < stake:
        town.message = f"You need ${stake} for this bet."
        return
    number = ROULETTE_POCKETS[town.roulette_pocket(choice)]
    payout = town.bet_roulette(choice, stake, number)
    if payout:
        town.add_cash(payout)
    town.message = f"The wheel landed on {number} ({roulette_color(number)}). Payout ${payout:,}."


def travel(position, label, *, key):
    if (town.x, town.y) == position:
        return True
    if (town.y >= RIVER_BOTTOM) != (position[1] >= RIVER_BOTTOM):
        if town.vehicle:
            st.caption("Ponte 25 de Abril · $3 toll toward Lisboa, free toward Almada.")
        else:
            st.caption("Cross the Tejo by ferry for $2.")
    button(f"Visit {label}", visit, position, label, key=key)
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
        act(street_input, event)
        if event.get("action") == "interact":
            site = st.session_state.town.nearby()
            if site and site.role in ("GARAGE", "WAREHOUSE", "EXCHANGE", "RESEARCH", "CASINO"):
                st.session_state.destination = site.name

    last_input = st.session_state.get("street_map")
    ack = last_input.get("id") if isinstance(last_input, dict) else None
    street_map(
        key="street_map", on_change=play, x=town.x, y=town.y, ack=ack,
        night=town.market_elapsed % DAY_SECONDS >= 180, facing=town.facing,
        vehicle=town.vehicle, hint=hint, message=town.message,
        speed=town.movement_speed, collision=COLLISION_MAP, life=STREET_LIFE,
        cash=town.cash, on_bridge=town.bridge_journey is not None,
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


def places():
    play_street()
    site = PLACES[st.selectbox("Destination", list(PLACES), index=list(PLACES).index("Goldenfield Farm"),
                              key="destination")]
    st.write(site_status(site))
    if town.nearby() != site and not travel(entrance(site), site.name, key="visit-site"):
        return
    if site.role == "RESEARCH":
        research()
    elif site.role == "EXCHANGE":
        district_exchange()
    elif site.role == "GARAGE":
        for key, vehicle in VEHICLES.items():
            button(f"Buy {vehicle.label} · ${vehicle.price:,} · +{vehicle.trunk} slots",
                   Town.purchase_vehicle, key, key=f"vehicle-{key}")
    elif site.role == "WAREHOUSE":
        button(f"Add 12 slots · ${300 + town.warehouse_level * 250:,}", warehouse)
    elif site.role == "CASINO":
        choice = st.selectbox("Color", ("red", "black", "green"))
        stake = st.selectbox("Stake ($)", (5, 10, 25, 50, 100))
        button("Spin", roulette, choice, stake)
    elif site.role == "SUPPLIER":
        trade = TRADES[site.trade]
        button(f"Buy 1 {trade.supply}", interact)
        button(f"Buy up to 4 {trade.supply}", interact, True)
        if site.trade == 3:
            button("Buy 1 egg", eggs)
            button("Buy up to 4 eggs", eggs, True)
    else:
        labels = {
            "FACTORY": "Produce or collect",
            "PUBLIC SHOP": "Stock shop" if businesses.is_owned(town, site) else "Sell carried goods",
            "TIER2": "Craft, collect or sell machinery",
            "PASTELARIA": "Bake, collect or sell pastéis",
            "SHIPYARD": "Start repair or collect payment",
        }
        button(labels[site.role], interact)


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
        position = (monument.map_point[0], monument.bounds[3] + 15)
        if travel(position, monument.name, key="monastery"):
            button("Visit monastery", Town.visit_monastery)


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
    .st-key-foundry_nav [data-testid="stHorizontalBlock"] {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
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
    game, recipes, advanced, settings = st.columns(4, vertical_alignment="center")
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

with settings.popover("Time & progress", width="stretch"):
    seconds = int(town.market_elapsed % DAY_SECONDS)
    st.caption(f"{DAY_SECONDS - seconds}s until market reset")
    st.caption("The clock runs while the game map has focus.")
    if store:
        st.caption("Local progress autosaves.")
        if st.button("Reload local progress"):
            try:
                load_game()
                st.rerun()
            except SAVE_ERRORS:
                st.session_state.save_error = "Could not read local progress. Check the save file."
    else:
        st.caption("Progress lasts for this browser session.")

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
