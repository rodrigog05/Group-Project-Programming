"""Manage purchased delivery vehicles, supply routes and factory storage."""
import tkinter as tk
from tkinter import ttk

import businesses
from logistics import BUFFER_LIMIT, FLEET_VEHICLES, MAX_ROUTES, OUTPUT_LIMIT
from research_panel import (BG, GOLD, MUTED, TEXT, _reader, _write, duration_text,
                            quantity_value)


def supplier_options(sites):
    return tuple(sorted((site for site in sites if site.role == "SUPPLIER"),
                        key=lambda site: site.name.casefold()))


def destination_options(sites, source, town=None):
    """Only factories that consume this supplier's material may be assigned."""
    return tuple(sorted((site for site in sites if source is not None and
                         site.role == "FACTORY" and
                         (businesses.trade_for(town, site) if town is not None else site.trade) == source.trade),
                        key=lambda site: site.name.casefold()))


def collection_allowed(town, factory_name):
    nearby = town.nearby()
    return nearby is not None and nearby.role == "FACTORY" and nearby.name == factory_name


def route_state(route):
    if route["phase"] == "outbound":
        return "Delivering" if route["enabled"] else "Finishing load"
    if route["phase"] == "returning":
        return "Returning" if route["enabled"] else "Return / paused"
    return "Waiting" if route["enabled"] else "Paused"


def route_values(route):
    remaining = max(0, route["duration"]-route["elapsed"])
    return (f'#{route["id"]} {FLEET_VEHICLES[route["kind"]].label}', route["source"],
            route["destination"], route_state(route), route["load"],
            duration_text(remaining) if route["phase"] != "idle" else "—")


def operating_cost(route):
    return route["materials_spent"]+route["running_spent"]+route["tolls_spent"]


def route_text(route, trades):
    vehicle = FLEET_VEHICLES[route["kind"]]
    trade = trades[route["trade"]]
    return (f'ROUTE #{route["id"]} · {vehicle.label}\n\n'
            f'{route["source"]} → {route["destination"]}\n'
            f'{trade.supply} → automated {trade.product} production\n\n'
            f'{route_state(route)} · {route["status"]}\n'
            f'Cargo on this vehicle: {route["load"]}/{vehicle.capacity}\n'
            f'Materials delivered: {route["delivered"]} · Completed deliveries: {route["trips"]}\n\n'
            f'Operating spend: ${operating_cost(route):,}\n'
            f'  Materials ${route["materials_spent"]:,} · Trip fees ${route["running_spent"]:,}'
            f' · Bridge tolls ${route["tolls_spent"]:,}\n'
            f'Vehicle purchase: ${vehicle.price:,} · Fee per departure: ${vehicle.running_cost}\n\n'
            'Each vehicle belongs to this route. Materials and trip fees are paid from your cash '
            'at departure; delivered materials stay in this factory’s separate storage. '
            'The factory makes products automatically while space is available.\n\n'
            'Pausing stops future departures. Paid cargo already travelling finishes its delivery '
            'and the vehicle returns. Remove only an empty vehicle waiting at its supplier; '
            'removing it gives no refund. '
            'Products stay at the factory until you visit to collect them. Sell collected products '
            'at the normal matching shops.')


def purchase_text(town, kind, source, destination, trades, reassigning=False):
    vehicle = FLEET_VEHICLES[kind]
    lines = [f'{vehicle.label} · Reassign existing vehicle for $0' if reassigning else
             f'{vehicle.label} · ${vehicle.price:,} to buy and assign',
             f'Cargo {vehicle.capacity} · Speed {vehicle.speed} · ${vehicle.running_cost} per departure', '']
    if source is None or destination is None:
        return '\n'.join(lines+["Choose a supplier and a compatible factory."])
    trade = trades[source.trade]
    material_cost = town.costs[source.trade]
    full_cost = vehicle.capacity*material_cost+vehicle.running_cost
    lines.extend((f'{source.name} → {destination.name}',
                  f'Buy {trade.supply} → deliver → automatically make {trade.product}',
                  f'Current {trade.supply} cost: ${material_cost} each.',
                  f'Full-load departure: ${full_cost} for materials and trip fee, before any bridge toll.', '',
                  (f'Cash after reassignment: ${town.cash:,}. No vehicle purchase is charged.' if reassigning else
                   f'Cash after vehicle purchase: ${town.cash-vehicle.price:,}.'),
                  'Keep cash available for future material purchases and trip fees. '
                  'Affordable partial loads can depart. A route waits when cash or factory storage is unavailable. '
                  'This fleet vehicle is separate from the vehicle you drive.'))
    return '\n'.join(lines)


def factory_values(town, site, trades):
    stock = town.logistics["factories"][site.name]
    order = stock["order"]
    making = (f'{order["quantity"]} · {duration_text(order["remaining"])}' if order else "—")
    capacity = businesses.storage_capacity(town, site)
    return (site.name, trades[businesses.trade_for(town, site)].product, f'{stock["input"]}/{capacity}',
            making, f'{stock["output"]}/{capacity}', stock["collected"])


def factory_text(town, site, trades):
    stock = town.logistics["factories"][site.name]
    trade = trades[businesses.trade_for(town, site)]
    capacity = businesses.storage_capacity(town, site)
    order = stock["order"]
    making = (f'{order["quantity"]} {trade.product} · {duration_text(order["remaining"])} remaining'
              if order else "No batch in progress")
    location = ("You are at this factory. Choose a quantity and collect output."
                if collection_allowed(town, site.name)
                else "Visit this factory entrance to collect output. Use Guide to factory.")
    return (f'{site.name} · {trade.supply} → {trade.product}\n\n'
            f'Factory materials: {stock["input"]}/{capacity} {trade.supply}\n'
            f'Automatic production: {making}\n'
            f'Ready output: {stock["output"]}/{capacity} {trade.product}\n'
            f'Produced in total: {stock["produced"]} · Collected in total: {stock["collected"]}\n\n'
            f'{location}\n\n'
            'These materials, production orders and finished goods use factory storage, '
            'separate from your bag and personal production orders. Collection moves output '
            'into your available cargo space; it never sells products automatically. '
            f'Owned equipment can produce up to {businesses.batch_size(town, site)} products per batch. '
            'Storage and equipment upgrades are managed in Businesses (B). '
            'Paused delivery routes do not stop work on materials already at the factory.')


def logistics_rules():
    rates = '\n'.join(f'• {vehicle.label}: ${vehicle.price} purchase, cargo {vehicle.capacity}, '
                       f'speed {vehicle.speed}, ${vehicle.running_cost} per departure.'
                       for vehicle in FLEET_VEHICLES.values())
    return (f'AUTOMATE YOUR SUPPLY CHAIN\n\nBuy and assign up to {MAX_ROUTES} fleet vehicles. '
            'Each route links a raw-material supplier to a factory that uses that material. '
            'For example, Goldenfield Farm delivers Wheat to Sunrise Bakery; '
            'Pine Mill or Marvila Timber Depot delivers Timber to Oak Workshop.\n\n'
            f'{rates}\n\n'
            'The purchase pays for one vehicle on one route. Fleet vehicles do not change '
            'the vehicle you drive or your bag capacity. Dispatches buy materials at the current '
            'market price and charge a trip fee from your cash. Affordable partial loads can depart. '
            'There is no charge when the vehicle cannot buy even one unit. Keep money available '
            'for the next trip. Vans pay normal bridge tolls when returning north to Lisbon; '
            'drones avoid bridge tolls. Vehicles wait when cash or destination storage is unavailable.\n\n'
            f'Each factory starts with {BUFFER_LIMIT} spaces for delivered raw materials and '
            f'{OUTPUT_LIMIT} spaces for finished output. Ownership storage upgrades expand both, '
            'and equipment upgrades speed production and increase batch size. It starts batches of up to six products '
            'before upgrades, producing automatically '
            'from its delivered materials when output storage has room. These stores and '
            'production orders are separate from your bag and personal factory orders.\n\n'
            'COLLECT, THEN SELL\n\nVisit the assigned factory entrance to collect completed products '
            'into your bag or vehicle trunk. Collection respects cargo reservations. '
            'The Factory storage tab can collect only while you are near that factory. '
            'Use Guide to factory to find it, then sell collected products at the usual shops. '
            'Deliveries do not sell products or create free materials.\n\n'
            'PAUSE, REMOVE & SAVE\n\nPause prevents future departures. A paid load already in flight '
            'finishes its delivery, then the vehicle returns. Factory production continues '
            'using materials already delivered. Remove only an empty vehicle waiting at its supplier. Removing a '
            'route gives no vehicle refund and preserves its factory’s materials and output.\n\n'
            'REASSIGN WITHOUT REBUYING\n\nSelect an idle, empty vehicle and choose Reassign empty vehicle. '
            'Choose another supplier and a matching current factory specialization, then Apply reassignment. '
            'This costs no vehicle purchase and keeps its operating history. Assigned routes must be moved '
            'away before a factory changes product. Paid loads cannot be reassigned.\n\n'
            'Routes and automated production run during focused play, including while this '
            'menu is open. Progress saves with your game. Closing or unfocusing the game '
            'pauses the fleet; there is no offline delivery catch-up.')


class LogisticsPanel:
    def __init__(self, game, sites, trades):
        self.game, self.root = game, game.root
        self.sites, self.trades = tuple(sites), tuple(trades)
        self.by_name = {site.name: site for site in self.sites}
        self.suppliers = supplier_options(self.sites)
        self.factories = tuple(sorted((site for site in self.sites if site.role == "FACTORY"),
                                      key=lambda site: site.name.casefold()))
        self.closed, self.timer = False, None
        self.reassigning = None
        self.reassign_was_enabled = None
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.logistics_controller = self
        panel.title("Foundry Town · Delivery Network")
        panel.transient(self.root)
        panel.configure(bg=BG)
        panel.resizable(True, True)
        panel.minsize(680, 500)
        available_width = self.root.winfo_width() if self.root.winfo_width() > 100 else self.root.winfo_screenwidth()
        available_height = self.root.winfo_height() if self.root.winfo_height() > 100 else self.root.winfo_screenheight()
        width, height = min(1080, max(680, available_width-80)), min(740, max(500, available_height-80))
        x = self.root.winfo_rootx()+max(0, (available_width-width)//2)
        y = self.root.winfo_rooty()+max(0, (available_height-height)//2)
        panel.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(panel, bg=BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="DELIVERY NETWORK", bg=BG, fg=GOLD,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.heading = tk.Label(body, text="Supplier → factory → collect → sell · L opens this menu",
                                bg=BG, fg=MUTED, font=("Segoe UI", 10), anchor="w", justify="left")
        self.heading.pack(fill="x", pady=(0, 5))
        self.summary = tk.Label(body, bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold"),
                                justify="left", anchor="w")
        self.summary.pack(fill="x", pady=(0, 8))
        footer = tk.Frame(body, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Button(footer, text="Return to town", command=self.close, bg=GOLD, fg="#172c33",
                   activebackground="#f0d591", relief="flat", padx=16, pady=7,
                   cursor="hand2", font=("Segoe UI", 10, "bold")).pack(side="right")
        self.footer_note = tk.Label(footer, text="Fleet runs while focused · Escape closes",
                                    bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left")
        self.footer_note.pack(side="left", fill="x", expand=True)
        style = ttk.Style(panel)
        style.configure("Logistics.Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Logistics.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_routes()
        self._build_purchase()
        self._build_factories()
        rules, reader = _reader(self.notebook)
        self.notebook.add(rules, text="How it works")
        _write(reader, logistics_rules())
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if not game.town.logistics["routes"]:
            self.notebook.select(1)
        panel.grab_set()
        self.route_tree.focus_set()

    def _page(self, title):
        page = ttk.Frame(self.notebook, padding=7)
        self.notebook.add(page, text=title)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        return page

    def _table(self, page, columns, height):
        frame = ttk.Frame(page)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=tuple(col[0] for col in columns), show="headings",
                            selectmode="browse", height=height, style="Logistics.Treeview")
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=width, stretch=name == columns[1][0],
                         anchor="w" if name in (columns[0][0], columns[1][0], "factory", "state") else "e")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    def _build_routes(self):
        page = self._page("Fleet routes")
        self.route_tree = self._table(page, (("vehicle", "Fleet vehicle", 115),
            ("source", "Supplier", 120), ("factory", "Factory", 120),
            ("state", "Status", 110), ("load", "Load", 45), ("eta", "ETA", 55)), 4)
        self.route_tree.bind("<<TreeviewSelect>>", lambda event: self._select_route())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        self.pause_button = ttk.Button(actions, text="Pause route", command=self._toggle)
        self.pause_button.pack(side="left", padx=(0, 7))
        self.remove_button = ttk.Button(actions, text="Remove empty vehicle", command=self._remove)
        self.remove_button.pack(side="left", padx=(0, 7))
        self.reassign_button = ttk.Button(actions, text="Reassign empty vehicle", command=self._start_reassign)
        self.reassign_button.pack(side="left", padx=(0, 7))
        self.route_guide = ttk.Button(actions, text="Guide to factory", command=self._guide_route)
        self.route_guide.pack(side="left")
        self.route_status = ttk.Label(controls, text="Buy and assign a vehicle to create your first route.",
                                     anchor="w", justify="left")
        self.route_status.pack(fill="x", pady=(5, 0))
        detail, self.route_reader = _reader(page)
        detail.grid(row=2, column=0, sticky="nsew")

    def _build_purchase(self):
        page = self._page("Buy & assign")
        form = ttk.Frame(page)
        form.grid(row=0, column=0, sticky="ew")
        form.grid_columnconfigure(1, weight=1)
        self.source = tk.StringVar(self.panel)
        self.destination = tk.StringVar(self.panel)
        self.vehicle = tk.StringVar(self.panel)
        self.source_labels = {f'{site.name} · {self.trades[site.trade].supply}': site for site in self.suppliers}
        self.vehicle_labels = {f'{spec.label} · ${spec.price:,} · cargo {spec.capacity}': key
                               for key, spec in FLEET_VEHICLES.items()}
        for row, label, variable, values in (
                (0, "1  Supplier / material", self.source, tuple(self.source_labels)),
                (1, "2  Matching factory", self.destination, ()),
                (2, "3  Fleet vehicle", self.vehicle, tuple(self.vehicle_labels))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            combo = ttk.Combobox(form, textvariable=variable, values=values, state="readonly")
            combo.grid(row=row, column=1, sticky="ew", pady=4)
            if row == 1:
                self.destination_combo = combo
            elif row == 2:
                self.vehicle_combo = combo
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        self.purchase_button = ttk.Button(actions, text="Buy & assign vehicle", command=self._create)
        self.purchase_button.pack(side="left")
        self.cancel_reassign = ttk.Button(actions, text="Cancel reassignment", command=self._cancel_reassign)
        self.purchase_status = ttk.Label(controls, text="One purchase assigns one vehicle to this route.",
                                        anchor="w", justify="left")
        self.purchase_status.pack(fill="x", pady=(4, 0))
        preview, self.purchase_reader = _reader(page)
        preview.grid(row=2, column=0, sticky="nsew")
        self.source.trace_add("write", lambda *args: self._source_changed())
        self.destination.trace_add("write", lambda *args: self._purchase_preview())
        self.vehicle.trace_add("write", lambda *args: self._purchase_preview())
        if self.vehicle_labels:
            self.vehicle.set(next(iter(self.vehicle_labels)))
        if self.source_labels:
            self.source.set(next(iter(self.source_labels)))

    def _build_factories(self):
        page = self._page("Factory storage")
        self.factory_tree = self._table(page, (("name", "Factory", 140),
            ("product", "Product", 90), ("input", "Materials", 75), ("order", "Making", 100),
            ("output", "Output", 65), ("collected", "Collected", 70)), 4)
        self.factory_tree.bind("<<TreeviewSelect>>", lambda event: self._select_factory())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        ttk.Label(actions, text="Quantity").pack(side="left", padx=(0, 5))
        self.quantity = tk.StringVar(self.panel, "1")
        self.quantity_entry = ttk.Spinbox(actions, from_=1, to=120,
                                         textvariable=self.quantity, width=6)
        self.quantity_entry.pack(side="left", padx=(0, 10))
        self.collect_button = ttk.Button(actions, text="Collect nearby output", command=self._collect)
        self.collect_button.pack(side="left", padx=(0, 7))
        self.factory_guide = ttk.Button(actions, text="Guide to factory", command=self._guide_factory)
        self.factory_guide.pack(side="left")
        self.factory_status = ttk.Label(controls, text="Visit a factory entrance to collect its output.",
                                       anchor="w", justify="left")
        self.factory_status.pack(fill="x", pady=(5, 0))
        detail, self.factory_reader = _reader(page)
        detail.grid(row=2, column=0, sticky="nsew")

    def _source_changed(self):
        source = self.source_labels.get(self.source.get())
        options = destination_options(self.sites, source, self.game.town)
        names = tuple(site.name for site in options)
        self.destination_combo.configure(values=names)
        if self.destination.get() not in names:
            self.destination.set(names[0] if names else "")
        self._purchase_preview()

    def _purchase_preview(self):
        kind = self.vehicle_labels.get(self.vehicle.get())
        if kind:
            _write(self.purchase_reader, purchase_text(self.game.town, kind,
                self.source_labels.get(self.source.get()), self.by_name.get(self.destination.get()), self.trades,
                reassigning=self.reassigning is not None))

    def _route(self):
        selected = self.route_tree.selection()
        return next((route for route in self.game.town.logistics["routes"]
                     if selected and str(route["id"]) == selected[0]), None)

    def _factory(self):
        selected = self.factory_tree.selection()
        return self.by_name.get(selected[0]) if selected else None

    def _select_route(self):
        route = self._route()
        available = route is not None
        self.pause_button.configure(state="normal" if available else "disabled",
                                    text="Pause route" if available and route["enabled"] else "Resume route")
        removable = available and route["load"] == 0 and route["phase"] == "idle"
        self.remove_button.configure(state="normal" if removable else "disabled")
        self.reassign_button.configure(state="normal" if removable else "disabled")
        self.route_guide.configure(state="normal" if available else "disabled")
        _write(self.route_reader, route_text(route, self.trades) if route else
               "No delivery routes. Open Buy & assign to purchase your first fleet vehicle.")

    def _select_factory(self):
        site = self._factory()
        allowed = site is not None and collection_allowed(self.game.town, site.name)
        stock = self.game.town.logistics["factories"].get(site.name) if site else None
        self.collect_button.configure(state="normal" if allowed and stock["output"] > 0 else "disabled")
        self.factory_guide.configure(state="normal" if site else "disabled")
        if site:
            self.quantity_entry.configure(to=businesses.storage_capacity(self.game.town, site))
            _write(self.factory_reader, factory_text(self.game.town, site, self.trades))

    def _start_reassign(self):
        route = self._route()
        if route is None or route["phase"] != "idle" or route["load"]:
            return "break"
        self._restore_reassign_enabled()
        self.reassigning = route["id"]
        self.reassign_was_enabled = route["enabled"]
        if route["enabled"]:
            self.game.town.set_delivery_enabled(route["id"], False)
        for label, key in self.vehicle_labels.items():
            if key == route["kind"]:
                self.vehicle.set(label)
                break
        self.vehicle_combo.configure(state="disabled")
        for label, source in self.source_labels.items():
            if source.name == route["source"]:
                self.source.set(label)
                break
        self.destination.set(route["destination"])
        self.purchase_button.configure(text="Apply reassignment · $0", state="normal")
        self.cancel_reassign.pack(side="left", padx=(7, 0))
        self.purchase_status.configure(text="Reassign this empty fleet vehicle for $0. Departures pause while editing; Apply or Cancel restores its previous running state.")
        self._purchase_preview()
        self.notebook.select(1)
        return "break"

    def _cancel_reassign(self):
        self._restore_reassign_enabled()
        self.reassigning = None
        self.vehicle_combo.configure(state="readonly")
        self.purchase_button.configure(text="Buy & assign vehicle")
        self.cancel_reassign.pack_forget()
        self._purchase_preview()
        self.refresh()
        return "break"

    def _restore_reassign_enabled(self):
        if self.reassigning is not None and self.reassign_was_enabled is not None:
            route = next((route for route in self.game.town.logistics["routes"]
                          if route["id"] == self.reassigning), None)
            if route is not None and route["enabled"] != self.reassign_was_enabled:
                self.game.town.set_delivery_enabled(route["id"], self.reassign_was_enabled)
        self.reassign_was_enabled = None

    def _create(self):
        source = self.source_labels.get(self.source.get())
        kind = self.vehicle_labels.get(self.vehicle.get())
        destination = self.by_name.get(self.destination.get())
        if not source or not destination or not kind:
            self.purchase_status.configure(text="Choose a supplier, matching factory and fleet vehicle.")
        else:
            reassigned = self.reassigning
            success = (self.game.town.reassign_delivery_route(reassigned, source.name, destination.name)
                       if reassigned is not None else
                       self.game.town.create_delivery_route(kind, source.name, destination.name))
            self.purchase_status.configure(text=self.game.town.message)
            if success:
                route = next(route for route in self.game.town.logistics["routes"]
                             if route["id"] == reassigned) if reassigned is not None else self.game.town.logistics["routes"][-1]
                self._restore_reassign_enabled()
                self.reassigning = None
                self.vehicle_combo.configure(state="readonly")
                self.purchase_button.configure(text="Buy & assign vehicle")
                self.cancel_reassign.pack_forget()
                self.refresh()
                self.route_tree.selection_set(str(route["id"]))
                self.route_tree.focus(str(route["id"]))
                self.route_status.configure(text=self.game.town.message)
                self.notebook.select(0)
            else:
                self.refresh()
        return "break"

    def _toggle(self):
        route = self._route()
        if route:
            self.game.town.set_delivery_enabled(route["id"], not route["enabled"])
            self.route_status.configure(text=self.game.town.message)
            self.refresh()
        return "break"

    def _remove(self):
        route = self._route()
        if route:
            self.game.town.remove_delivery_route(route["id"])
            self.route_status.configure(text=self.game.town.message)
            self.refresh()
        return "break"

    def _collect(self):
        site, quantity = self._factory(), quantity_value(self.quantity.get())
        if quantity is None:
            self.factory_status.configure(text="Enter a positive whole number of products.")
        elif site:
            self.game.town.collect_delivery_products(site.name, quantity)
            self.factory_status.configure(text=self.game.town.message)
            self.refresh()
        return "break"

    def _guide(self, site):
        if site:
            x, y = site.door
            self.game.world_view.set_destination(site.name, x, y+18)
            return self.close()
        return "break"

    def _guide_route(self):
        route = self._route()
        return self._guide(self.by_name.get(route["destination"])) if route else "break"

    def _guide_factory(self):
        return self._guide(self._factory())

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        town = self.game.town
        routes = town.logistics["routes"]
        output = sum(stock["output"] for stock in town.logistics["factories"].values())
        self.summary.configure(text=f'Cash ${town.cash:,} · Fleet {len(routes)}/{MAX_ROUTES} · '
            f'Factory output ready {output}\nMaterials and trip fees are paid automatically at departure.')
        current = {str(route["id"]) for route in routes}
        for item in self.route_tree.get_children():
            if item not in current:
                self.route_tree.delete(item)
        for route in routes:
            self._put(self.route_tree, str(route["id"]), route_values(route))
        if not self.route_tree.selection() and routes:
            self.route_tree.selection_set(str(routes[0]["id"]))
        for site in self.factories:
            self._put(self.factory_tree, site.name, factory_values(town, site, self.trades))
        if not self.factory_tree.selection() and self.factories:
            self.factory_tree.selection_set(self.factories[0].name)
        self._select_route()
        self._select_factory()
        self._purchase_preview()
        self.purchase_button.configure(state="normal" if self.reassigning is not None or len(routes) < MAX_ROUTES else "disabled")
        self.timer = self.panel.after(1000, self.refresh)

    @staticmethod
    def _put(tree, key, values):
        if tree.exists(key):
            if tuple(tree.item(key, "values")) != tuple(map(str, values)):
                tree.item(key, values=values)
        else:
            tree.insert("", "end", iid=key, values=values)

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-62)
            for label in (self.heading, self.summary, self.route_status,
                          self.purchase_status, self.factory_status):
                label.configure(wraplength=width)
            self.footer_note.configure(wraplength=max(230, event.width-220))

    def _release(self):
        if self.closed:
            return
        self._restore_reassign_enabled()
        self.closed = True
        if self.timer is not None:
            try:
                self.panel.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        if self.game.profile_window is self.panel:
            self.game.profile_window = None
        self.game.keys.clear()
        try:
            self.panel.grab_release()
        except tk.TclError:
            pass

    def _destroyed(self, event):
        if event.widget is self.panel:
            self._release()

    def close(self, event=None):
        self._release()
        try:
            self.panel.destroy()
            if self.root.winfo_exists():
                self.root.focus_set()
        except tk.TclError:
            pass
        return "break"


def open_logistics(game, sites, trades):
    if getattr(game, "profile_window", None) is not None:
        return None
    return LogisticsPanel(game, sites, trades).panel
