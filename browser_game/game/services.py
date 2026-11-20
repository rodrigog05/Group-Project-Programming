"""Browser menus use the same town transactions and prices as the desktop."""
from functools import partial
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

    def act(fn,*args):
        fn(*args)
        g.reply = t.message
        g.save()

    def link(menu, **values):
        ctx.update(values)
        g.site = None
        g.open(menu)

    def guide(entry):
        g.target = entry
        g.leave()

    def warehouse():
        price = 300+t.warehouse_level*250
        if t.cash<price:
            t.message = f"You need ${price} to expand storage."
            return
        t.cash -= price
        t.other_expenses_today += price
        t.warehouse_level += 1
        t.bag_size += 12
        t.message = f"Warehouse expanded to {t.bag_size} personal slots."

    def sail():
        if ferry.ride_ferry(t):
            g.leave()
        else:
            g.reply=t.message

    def bet(color):
        stake=ctx.get("stake",5)
        if t.cash<stake:
            t.message=f"You need ${stake} to place this bet."
            return
        number=m.ROULETTE_POCKETS[t.roulette_pocket(color)]
        payout=t.bet_roulette(color,stake,number)
        if payout:
            t.add_cash(payout,business=True)
        t.message=f"{number} {m.roulette_color(number)} · paid ${payout}."

    def info(text):
        g.reply=text

    def toggle_traffic():
        g.traffic=not g.traffic

    def acknowledge():
        t.continue_after_milestone()
        g.leave()

    if panel=="Cash milestone":
        return [("You reached $500! Continue to research and advanced production.",acknowledge)]
    if panel=="Settings":
        return [(f"Music · {'on' if g.music else 'off'}",g.toggle_music),
                (f"Traffic · {'on' if g.traffic else 'off'}",toggle_traffic),
                ("Save progress in this browser",lambda:(g.save(),info(g.warning or "Progress saved."))),
                ("How to play",partial(info,"Walk with WASD or arrows. E opens a building. Buy raw materials, make products, then sell them. Esc returns outside."))]
    if panel=="Places":
        return [(e.name+" · "+e.neighborhood,partial(guide,e))
                for entries in directory_entries(m.SITES,town=t).values() for e in entries]
    if panel=="Journal":
        rows=[(recipe.title,partial(info,f"{recipe.ingredients} → {recipe.product} · {recipe.seconds}s"))
              for key in t.discovered_recipes if (recipe:=m.RECIPE_BY_KEY.get(key))]
        rows += [(entry.title,partial(info,entry.body)) for entry in (*LANDMARK_LORE,*TEJO_LORE)]
        rows += [(f"{trade.product} · ${t.prices[i]} · {t.goods[i]} in bag · {t.demand[i]} buyers",partial(info,t.market_event or "Today's regular market."))
                 for i,trade in enumerate(m.TRADES)]
        return rows
    if role=="GARAGE":
        return [(f"{ride.label} · ${ride.price} · +{ride.trunk} cargo",partial(act,t.purchase_vehicle,key)) for key,ride in m.VEHICLES.items()]+[("Delivery fleet",partial(link,"Deliveries"))]
    if role=="WAREHOUSE":
        return [(f"Add 12 slots · ${300+t.warehouse_level*250}",partial(act,warehouse))]
    if role=="EXCHANGE":
        return [(f"{row['name']} · buy ${row['ask']} / sell ${row['bid']} · own {row['owned']}",partial(link,"Trade shares",symbol=row["symbol"])) for row in exchange.portfolio_rows(t)]
    if panel=="Trade shares":
        return [(f"{action} 1 share of {ctx['symbol']}",partial(act,fn,t,ctx["symbol"],1)) for action,fn in (("Buy",exchange.buy_shares),("Sell",exchange.sell_shares))]
    if role=="RESEARCH":
        rows=[(f"Research {b.name} · level {innovation.research_level(t,b.key)}/3",partial(act,t.start_research,b.key)) for b in innovation.RESEARCH_BRANCHES]
        for recipe in innovation.unlocked_recipes(t):
            rows.extend([(f"{verb} {recipe.product}",partial(act,fn,recipe.key,1)) for verb,fn in
                         (("Craft",t.start_fabrication),("Collect",t.collect_research_products),("Sell",t.sell_research_products))])
        return rows
    if role=="CASINO":
        return [(f"Bet ${ctx.get('stake',5)} on {color}",partial(act,bet,color)) for color in m.ROULETTE_PAYOUTS]+[(f"Choose ${chip} chip",partial(ctx.update,stake=chip)) for chip in (5,10,25,50,100)]
    if panel=="Ferry":
        pier=ferry.nearby_pier(t.x,t.y)
        return [(f"Cross to {ferry.other_pier(pier).name} · ${ferry.FERRY_FARE}",sail)]
    if panel=="Mosteiro dos Jerónimos":
        return [(f"Casino luck +{t.casino_luck} percentage points",g.leave)]
    if panel=="Businesses":
        return [(s.name+" · "+("owned" if businesses.is_owned(t,s) else "available"),partial(link,"Property",building=s)) for s in m.SITES if s.role in ("PUBLIC SHOP","FACTORY")]
    if panel=="Property":
        s=ctx["building"]
        if not businesses.is_owned(t,s):
            return [(f"Buy {s.name} · ${businesses.PURCHASE_PRICES[s.role]}",partial(act,t.purchase_business,s.name))]
        rows=[(f"Upgrade {kind} · ${businesses.upgrade_cost(t,s,kind)}",partial(act,t.upgrade_business,s.name,kind)) for kind in ("equipment","storage")]
        rows.extend((f"Specialize in {trade.product}",partial(act,t.specialize_business,s.name,i)) for i,trade in enumerate(m.TRADES))
        if s.role=="PUBLIC SHOP":
            rows.extend((f"{verb} stock at {s.name}",partial(act,fn,s.name)) for verb,fn in (("Deposit",t.stock_business),("Withdraw",t.withdraw_business),("Sell carried",t.sell_business_carried)))
        return rows
    if panel=="Contracts":
        rows=[(f"Accept · {o.title} · {o.quantity} items · ${o.cash}",partial(act,t.accept_contract,o.key)) for o in contracts.available_offers(t)]
        for r in t.contracts["active"]:
            o=contracts.active_offer(r)
            rows.append((f"Deliver {o.title} · {o.location.name}",partial(act,t.deliver_contract,r["id"])))
            rows.append((f"Abandon {o.title}",partial(act,t.abandon_contract,r["id"])))
        return rows
    if panel=="Deliveries":
        rows=[("Purchase "+v.label,partial(link,"Choose supplier",kind=k,route=None)) for k,v in logistics.FLEET_VEHICLES.items()]
        for r in t.logistics["routes"]:
            rows.extend([(f"Pause / resume {r['source']} → {r['destination']}",partial(act,t.set_delivery_enabled,r['id'],not r['enabled'])),
                         ("Reassign "+r['source'],partial(link,"Choose supplier",route=r["id"])),
                         ("Remove "+r['source'],partial(act,t.remove_delivery_route,r["id"]))])
        return rows
    if panel=="Choose supplier":
        return [(s.name,partial(link,"Choose factory",supplier=s)) for s in m.SITES if s.role=="SUPPLIER"]
    if panel=="Choose factory":
        supplier=ctx["supplier"]
        fn=partial(t.reassign_delivery_route,ctx["route"]) if ctx["route"] else partial(t.create_delivery_route,ctx["kind"])
        return [(s.name,partial(act,fn,supplier.name,s.name)) for s in m.SITES if s.role=="FACTORY" and t.business_site(s).trade==supplier.trade]
    return []
