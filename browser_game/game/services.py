"""Browser menus use the same town transactions and prices as the desktop."""

from functools import partial
import time
import businesses_panel as business_text
import contracts_panel as contract_text
import exchange_panel as exchange_text
import research_panel as research_text
import logistics_panel as fleet_text
import journal_panel as journal_text
from journal_market import market_snapshot
import businesses
import contracts
import exchange
import ferry
import innovation
import logistics
import tycoon as m
from journal_lore import LANDMARK_LORE, TEJO_LORE
from places_menu import directory_entries


def service_options(g):
    t, panel = g.t, g.panel
    role = g.site.role if g.site else ""
    ctx = g.context

    qty = ctx["quantity"]
    amount = (f"Quantity · {qty} · change", partial(g.subpage, "Quantity"))

    def details(title, fn, *args):
        return (title, lambda: g.read(title, fn(*args)))

    def act(fn, *args):
        fn(*args)
        g.reply = t.message
        g.save()

    def link(menu, **values):
        ctx.update(values)
        g.subpage(menu)

    def guide(entry):
        g.target = entry
        g.leave()

    def reassign(route):
        if route["phase"] != "idle" or route["load"]:
            info("Wait for the empty vehicle to reach its depot.")
            return
        g.restore_route()
        ctx["paused_route"] = (route["id"], route["enabled"])
        t.set_delivery_enabled(route["id"], False)
        link("Choose supplier", route=route["id"])

    def assign(factory):
        supplier = ctx["supplier"].name
        if ctx["route"] is None:
            success = t.create_delivery_route(ctx["kind"], supplier, factory)
        else:
            success = t.reassign_delivery_route(ctx["route"], supplier, factory)
        message = t.message
        if success:
            g.restore_route()
            while g.panel != "Deliveries" and g.history:
                g.back()
        g.reply = message
        g.save()

    def warehouse():
        price = 300 + t.warehouse_level * 250
        if t.cash < price:
            t.message = f"You need ${price} to expand storage."
            return
        t.cash -= price
        t.other_expenses_today += price
        t.warehouse_level += 1
        t.bag_size += 12
        t.message = f"Warehouse expanded to {t.bag_size} personal slots."

    def sail():
        trip = ferry.ride_ferry(t)
        if trip:
            g.scenes.ferry = (
                time.monotonic(),
                1 if trip[0].north else -1,
                t.market_elapsed % 300 >= 180,
            )
            g.open("Crossing")
            g.save()
        else:
            g.reply = t.message

    def info(text):
        g.reply = text

    def toggle_traffic():
        g.traffic = not g.traffic

    def acknowledge():
        t.continue_after_milestone()
        g.leave()

    if panel == "Cash milestone":
        return [
            (
                "You reached $500! Continue to research and advanced production.",
                acknowledge,
            )
        ]
    if panel == "Quantity":
        return [
            (
                f"{g.profile_name or 'Type a number'} · Enter to apply",
                partial(g.key, "return"),
            )
        ]
    if panel == "New game":

        def restart():
            profile = dict(t.profile)
            g.t = m.Town()
            g.t.set_profile(profile)
            g.started = time.time()
            g.target = None
            g.leave()

        return [
            ("Keep this town", g.leave),
            ("Replace saved progress and start a new town", restart),
        ]
    if panel == "Player name":
        return [
            (
                g.profile_name + "  ·  Type a name and press Enter",
                lambda: g.key("return"),
            )
        ]
    if panel == "Character":
        rows = [("Player name · " + t.profile["name"], partial(g.open, "Player name"))]
        for field, choices in (
            ("costume", m.COSTUMES),
            ("body", m.BODY_COLORS),
            ("hair", m.HAIR_COLORS),
        ):
            values = list(choices)
            next_value = values[(values.index(t.profile[field]) + 1) % len(values)]
            rows.append(
                (
                    f"{field.title()} · {t.profile[field]} · change",
                    partial(t.set_profile, {field: next_value}),
                )
            )
        return rows + [("Play as " + t.profile["name"], g.leave)]
    if panel == "Inventory":
        rows = [
            f"Bag {t.cargo}/{t.carry_capacity} · {t.reserved} slots reserved for orders"
        ]
        rows.extend(
            f"{trade.supply}: {t.supplies[i]} · {trade.product}: {t.goods[i]}"
            for i, trade in enumerate(m.TRADES)
        )
        rows.extend([f"Eggs: {t.eggs}", f"Precision Machinery: {t.tier2_goods}"])
        rows.extend(
            f"{r.product}: {t.innovation['goods'][r.key]}"
            for r in innovation.TIER3_RECIPES
        )
        rows.extend(
            f"{m.INDUSTRIES[k].product}: {v}" for k, v in t.industry_goods.items() if v
        )
        return [(r, partial(info, r)) for r in rows]
    if panel == "Finances":
        rows = [
            f"Day {t.day} · revenue ${t.daily_revenue} · expenses ${t.daily_expenses} · net ${t.daily_net_profit}",
            f"Tax rate {innovation.tax_rate(t)}% · taxes paid ${t.taxes_paid_total} · tolls paid ${t.tolls_paid_total}",
        ]
        rows.extend(
            f"{trade.product} · {t.sales_today[i]} sold today · lifetime {t.total_sold[i]} · revenue ${t.revenue_today[i]}"
            for i, trade in enumerate(m.TRADES)
        )
        rows.extend(
            f"{r.product} · revenue ${t.industry_revenue_today[k]}"
            for k, r in m.INDUSTRIES.items()
        )
        rows.extend(
            f"{r.product} · revenue ${t.innovation['revenue_today'][r.key]}"
            for r in innovation.TIER3_RECIPES
        )
        rows.append(f"Precision Machinery · revenue ${t.tier2_revenue_today}")
        if t.last_day_summary:
            last = t.last_day_summary
            rows.append(
                f"Day {last['day']} settled · profit ${last['profit']} · tax ${last['tax']}"
            )
        return [(v, partial(info, v)) for v in rows]
    if panel == "Settings":
        return [
            (f"Music · {'on' if g.music else 'off'}", g.toggle_music),
            (f"Traffic · {'on' if g.traffic else 'off'}", toggle_traffic),
            (
                f"Ambient activity · {'on' if g.actors_enabled else 'off'}",
                partial(setattr, g, "actors_enabled", not g.actors_enabled),
            ),
            (
                f"Camera zoom · {g.zoom}×",
                partial(setattr, g, "zoom", {1: 1.25, 1.25: 1.5, 1.5: 1}[g.zoom]),
            ),
            ("Character and appearance", partial(g.subpage, "Character")),
            ("Finances and profit", partial(g.subpage, "Finances")),
            ("Return to start menu", lambda: (g.leave(), g.open("Welcome"))),
            (
                "Save progress in this browser",
                lambda: (g.save(), info(g.warning or "Progress saved.")),
            ),
            ("How to play", partial(g.read, "Foundry Town rules", m.RULES_TEXT)),
        ]
    if panel == "Places":
        return [
            (e.name + " · " + e.neighborhood, partial(guide, e))
            for entries in directory_entries(m.SITES, town=t).values()
            for e in entries
        ]
    if panel == "Journal":
        return [
            (name, partial(link, name))
            for name in ("Recipes", "Landmarks", "Tejo", "Markets")
        ]
    if panel == "Recipes":
        from journal_recipes import RECIPES

        sites = [t.business_site(site) for site in m.SITES]
        return [
            details(
                r.title
                + (
                    " · discovered"
                    if r.key in t.discovered_recipes
                    else " · undiscovered"
                ),
                journal_text.recipe_text,
                r,
                r.key in t.discovered_recipes,
                sites,
            )
            for r in RECIPES
        ]
    if panel in ("Landmarks", "Tejo"):
        return [
            (
                e.title,
                partial(
                    g.read,
                    e.title,
                    e.body
                    + "\n\n"
                    + "\n".join(src.title + " · " + src.url for src in e.sources),
                ),
            )
            for e in (LANDMARK_LORE if panel == "Landmarks" else TEJO_LORE)
        ]
    if panel == "Markets":
        snap = market_snapshot(t)
        return [
            details(
                f"{r.product} · ${r.price} · {r.remaining_buyers} buyers · sold {r.sold_today}",
                journal_text.market_text,
                r,
                snap,
            )
            for r in snap.rows
        ]
    if role == "WAREHOUSE":
        return [
            (
                f"Add 12 slots · ${300 + t.warehouse_level * 250}",
                partial(act, warehouse),
            )
        ]
    if role == "EXCHANGE":
        return [
            (
                f"{row['name']} · buy ${row['ask']} / sell ${row['bid']} · own {row['owned']}",
                partial(link, "Trade shares", symbol=row["symbol"]),
            )
            for row in exchange.portfolio_rows(t)
        ] + [
            details("Portfolio", exchange_text.portfolio_text, exchange.summary(t)),
            details(
                "Dividends and activity",
                exchange_text.activity_text,
                exchange.portfolio_rows(t),
                exchange.summary(t),
            ),
            details("Exchange rules", exchange_text.exchange_rules),
        ]
    if panel == "Trade shares":
        return [
            (
                f"{action} {qty} share(s) of {ctx['symbol']}",
                partial(act, fn, t, ctx["symbol"], qty),
            )
            for action, fn in (
                ("Buy", exchange.buy_shares),
                ("Sell", exchange.sell_shares),
            )
        ] + [
            amount,
            details(
                "Investment details",
                exchange_text.asset_text,
                next(
                    r
                    for r in exchange.portfolio_rows(t)
                    if r["symbol"] == ctx["symbol"]
                ),
            ),
        ]
    if role == "RESEARCH":
        rows = [
            (
                f"Research {b.name} · level {innovation.research_level(t, b.key)}/3 · next {innovation.research_quote(t, b.key) or 0} dollars",
                partial(act, t.start_research, b.key),
            )
            for b in innovation.RESEARCH_BRANCHES
        ]
        for recipe in innovation.unlocked_recipes(t):
            rows.extend(
                [
                    (f"{verb} {recipe.product}", partial(act, fn, recipe.key, qty))
                    for verb, fn in (
                        ("Craft", t.start_fabrication),
                        ("Collect", t.collect_research_products),
                        ("Sell", t.sell_research_products),
                    )
                ]
            )
        rows.extend(
            details(b.name + " · requirements", research_text.branch_text, t, b)
            for b in innovation.RESEARCH_BRANCHES
        )
        rows.extend(
            details(r.product + " · recipe", research_text.recipe_text, t, r)
            for r in innovation.TIER3_RECIPES
        )
        return rows + [
            amount,
            details("Current research project", research_text.project_text, t),
        ]
    if panel == "Ferry":
        pier = ferry.nearby_pier(t.x, t.y)
        return [(f"Cross to {ferry.other_pier(pier).name} · ${ferry.FERRY_FARE}", sail)]
    if panel == "Mosteiro dos Jerónimos":
        return [(f"Casino luck +{t.casino_luck} percentage points", g.leave)]
    if panel == "Businesses":
        return [
            (
                s.name
                + " · "
                + ("owned" if businesses.is_owned(t, s) else "available"),
                partial(link, "Property", building=s),
            )
            for s in m.SITES
            if s.role in ("PUBLIC SHOP", "FACTORY")
        ]
    if panel == "Property":
        s = ctx["building"]
        if not businesses.is_owned(t, s):
            return [
                (
                    f"Buy {s.name} · ${businesses.PURCHASE_PRICES[s.role]}",
                    partial(act, t.purchase_business, s.name),
                ),
                details(
                    "Property details", business_text.property_text, t, s, m.TRADES
                ),
            ]
        rows = [
            (
                f"Upgrade {kind} · ${price}",
                partial(act, t.upgrade_business, s.name, kind),
            )
            for kind in ("equipment", "storage")
            if (price := businesses.upgrade_cost(t, s, kind)) is not None
        ]
        rows.extend(
            (
                f"Specialize in {trade.product}",
                partial(act, t.specialize_business, s.name, i),
            )
            for i, trade in enumerate(m.TRADES)
        )
        if s.role == "PUBLIC SHOP":
            rows.extend(
                (f"{verb} stock at {s.name}", partial(act, fn, s.name, qty))
                for verb, fn in (
                    ("Deposit", t.stock_business),
                    ("Withdraw", t.withdraw_business),
                    ("Sell carried", t.sell_business_carried),
                )
            )
        return rows + [
            amount,
            details("Property details", business_text.property_text, t, s, m.TRADES),
        ]
    if panel == "Abandon order?":

        def abandon():
            t.abandon_contract(ctx["identifier"])
            g.back()
            g.reply = t.message

        return [
            ("Keep this order", g.back),
            ("Abandon order and forfeit delivered goods", abandon),
        ]
    if panel == "Contracts":
        rows = [
            (
                f"Accept · {o.title} · {o.quantity} items · ${o.cash}",
                partial(act, t.accept_contract, o.key),
            )
            for o in contracts.available_offers(t)
        ]
        for r in t.contracts["active"]:
            o = contracts.active_offer(r)
            rows.append(
                (
                    f"Deliver {o.title} · {o.location.name}",
                    partial(act, t.deliver_contract, r["id"], qty),
                )
            )
            rows.append(
                (
                    f"Abandon {o.title}",
                    partial(link, "Abandon order?", identifier=r["id"]),
                )
            )
            rows.append(
                details(o.title + " · order status", contract_text.active_text, t, r)
            )
            from places_menu import DirectoryEntry

            target = DirectoryEntry(
                o.location.name,
                "",
                "",
                "Deliver here",
                o.location.x,
                o.location.y,
                "C",
                "#ffc66c",
            )
            rows.append(("Guide to " + o.location.name, partial(guide, target)))
        rows.extend(
            details(o.title + " · terms", contract_text.offer_text, t, o)
            for o in contracts.available_offers(t)
        )
        rows.extend(
            (
                " · ".join(map(str, contract_text.history_values(h))),
                partial(info, h["status"]),
            )
            for h in t.contracts["history"]
        )
        return rows + [
            amount,
            details("Supplier reputation", contract_text.reputation_text, t),
        ]
    if panel == "Deliveries":
        rows = [
            (
                f"Purchase {v.label} · ${v.price}",
                partial(link, "Choose supplier", kind=k, route=None),
            )
            for k, v in logistics.FLEET_VEHICLES.items()
        ]
        for r in t.logistics["routes"]:
            rows.extend(
                [
                    (
                        f"Pause / resume {r['source']} → {r['destination']}",
                        partial(act, t.set_delivery_enabled, r["id"], not r["enabled"]),
                    ),
                    ("Reassign " + r["source"], partial(reassign, r)),
                    (
                        "Remove " + r["source"],
                        partial(act, t.remove_delivery_route, r["id"]),
                    ),
                ]
            )
        for name, stock in t.logistics["factories"].items():
            if stock["output"]:
                rows.append(
                    (
                        f"Collect {stock['output']} products at {name}",
                        partial(act, t.collect_delivery_products, name, qty),
                    )
                )
        rows.extend(
            details(f"Route {r['id']} · status", fleet_text.route_text, r, m.TRADES)
            for r in t.logistics["routes"]
        )
        return rows + [amount, details("Delivery rules", fleet_text.logistics_rules)]
    if panel == "Choose supplier":
        return [
            (s.name, partial(link, "Choose factory", supplier=s))
            for s in m.SITES
            if s.role == "SUPPLIER"
        ]
    if panel == "Choose factory":
        supplier = ctx["supplier"]
        return [
            (s.name, partial(assign, s.name))
            for s in m.SITES
            if s.role == "FACTORY" and t.business_site(s).trade == supplier.trade
        ]
    return []
