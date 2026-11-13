"""Property purchases, business upgrades and on-site shop stock management."""
import tkinter as tk
from tkinter import ttk

from businesses import (MAX_LEVEL, PURCHASE_PRICES, RETAIL_INTERVAL,
                        SUPPORTED_ROLES, batch_size, effective_site,
                        near_business, production_seconds, record_for,
                        sale_price, specialization_block_reason,
                        storage_capacity, trade_for, upgrade_cost)
from research_panel import (BG, GOLD, MUTED, TEXT, _reader, _write, duration_text,
                            quantity_value)


def properties(sites):
    return tuple(sorted((site for site in sites if site.role in SUPPORTED_ROLES),
                        key=lambda site: site.name.casefold()))


def property_values(town, site, trades):
    record = record_for(town, site)
    return (site.name, "Factory" if site.role == "FACTORY" else "Shop",
            trades[trade_for(town, site)].product, "Owned" if record else "For sale",
            "Owned" if record else f"${PURCHASE_PRICES[site.role]:,}")


def shop_actions_allowed(town, site):
    return (site is not None and site.role == "PUBLIC SHOP" and
            record_for(town, site) is not None and near_business(town, site))


def upgrade_label(town, site, kind):
    cost = upgrade_cost(town, site, kind)
    title = "Storage" if kind == "storage" else "Equipment"
    if cost is None:
        return f"{title} fully upgraded"
    record = record_for(town, site)
    level = record[f"{kind}_level"]+1
    return f"{title} level {level} · ${cost:,}"


def factory_stock_text(town, site, trades):
    record = record_for(town, site)
    trade = trades[trade_for(town, site)]
    capacity = storage_capacity(town, site)
    stock = town.logistics["factories"][site.name]
    order = stock["order"]
    automatic = (f'{order["quantity"]} {trade.product} · {duration_text(order["remaining"])} remaining'
                 if order else "None")
    manual = record["manual_order"]
    carried_order = (f'{manual["quantity"]} {trades[manual["trade"]].product} · '
                     f'{duration_text(max(0, manual["ready_at"]-town.elapsed))} remaining'
                     if manual else "None")
    return (f'Automated material buffer: {stock["input"]}/{capacity} {trade.supply}\n'
            f'Automated batch: {automatic}\n'
            f'Automated output: {stock["output"]}/{capacity} {trade.product}\n'
            f'Produced automatically: {stock["produced"]} · Collected: {stock["collected"]}\n'
            f'Manual order from carried materials: {carried_order}\n\n'
            'Visit the factory entrance and use E for production and collection. '
            'Automated factory storage is separate from your cargo. Use Deliveries (L) '
            'to purchase supply routes and collect output while visiting the factory.')


def management_text(town, site, trades):
    record = record_for(town, site)
    if record is None:
        return "Buy a property in the Properties tab to manage its upgrades and specialization."
    trade = trades[trade_for(town, site)]
    capacity = storage_capacity(town, site)
    lines = [f'{site.name} · {"Factory" if site.role == "FACTORY" else "Shop"}', "",
             f'Specialization: {trade.product} · Raw material: {trade.supply}',
             f'Storage level {record["storage_level"]}/{MAX_LEVEL} · Capacity {capacity}',
             f'Equipment level {record["equipment_level"]}/{MAX_LEVEL}',
             f'Total cash invested: ${record["invested"]:,}',
             'Each storage level adds 24 spaces: 48 → 72 → 96 → 120.', ""]
    if site.role == "FACTORY":
        seconds = production_seconds(town, site, trade.seconds)
        lines.extend((f'Production time: {seconds:g}s per batch · Automated batch up to {batch_size(town, site)} products.',
                      'Equipment levels use 100%, 85%, 70% and 55% of base production time and add two batch slots per level.',
                      'Storage capacity applies to each automated material and output store.', "",
                      factory_stock_text(town, site, trades)))
    else:
        buyers = town.buyer_status(effective_site(town, site))
        lines.extend((f'Stored products: {record["stock"]}/{capacity} {trade.product}',
                      f'Current selling quote: ${sale_price(town, site):,} each',
                      'Each equipment level adds 5% to the selling quote and one customer per sale interval.',
                      f'NPC sale attempts: up to {2+record["equipment_level"]} customers every {RETAIL_INTERVAL} focused seconds.',
                      f'Available buyers: {buyers}',
                      f'Sold today: {record["sales_today"]} · Revenue today: ${record["revenue_today"]:,}',
                      f'Sold in total: {record["total_sold"]} · Total revenue: ${record["total_revenue"]:,}', "",
                      'Visit this shop to deposit stock, withdraw unsold products or sell carried products immediately. '
                      'Depositing products earns no cash. NPC customers pay only when real available buyers '
                      'purchase your stored stock. Market supply, shared buyers and nearby tourism still apply.'))
    reason = specialization_block_reason(town, site)
    lines.extend(("", "CHANGE SPECIALIZATION", reason if reason else "This business is empty and ready to change specialization.",
                  "Choose Tools / Iron ore, Furniture / Timber, Pottery / Clay or Bread / Wheat.",
                  'Changing a factory requires empty automated materials, output and orders, no manual order, '
                  'and no delivery route assigned to it. Pause assigned routes in Deliveries (L), wait for '
                  'empty returns and use Reassign empty vehicle to move them to another factory for free. '
                  'A shop must have no stored stock. Upgrades remain with the property.'))
    return "\n".join(lines)


def property_text(town, site, trades):
    record = record_for(town, site)
    if record:
        return management_text(town, site, trades)
    trade = trades[trade_for(town, site)]
    kind = "factory" if site.role == "FACTORY" else "shop"
    purpose = ('Own this factory to expand its automated stores, speed up production and increase '
               'its automated batch size. Manual orders belong to this factory.' if kind == "factory" else
               'Own this shop to store products for NPC customers, expand shelf capacity and improve '
               'its selling quote and customer throughput.')
    return (f'{site.name} · {kind.capitalize()} for sale\n\n'
            f'Purchase: ${PURCHASE_PRICES[site.role]:,} · Your cash: ${town.cash:,}\n'
            f'Current product: {trade.product} · Material: {trade.supply}\n\n{purpose}\n\n'
            'You can already use unowned factories and shops as before. Ownership adds storage, '
            'equipment upgrades and a choice of the four basic production chains. '
            'The specialized Pastéis de Belém, shipyard, tier-2 works and university retain their own recipes.\n\n'
            'After buying, open Owned management to upgrade or change specialization. '
            'Use Shop counter while physically at an owned shop to deposit, withdraw or sell products. '
            'Deposited stock pays only when NPC buyers purchase it; ownership does not create unlimited demand.')


def shop_text(town, site, trades):
    record = record_for(town, site)
    trade_index = trade_for(town, site)
    trade = trades[trade_index]
    location = ("You are at this shop. Choose a quantity and an action."
                if near_business(town, site) else "Visit this shop entrance to move or sell products. Use Guide to shop.")
    return (f'{site.name} · {trade.product}\n\n'
            f'Your carried stock: {town.goods[trade_index]} {trade.product}\n'
            f'Shop storage: {record["stock"]}/{storage_capacity(town, site)} {trade.product}\n'
            f'Current selling quote: ${sale_price(town, site):,} per product\n'
            f'Buyers: {town.buyer_status(effective_site(town, site))}\n\n'
            f'{location}\n\n'
            'Deposit moves carried products onto the shop’s shelves. It gives no immediate payment. '
            'NPC customers buy stored stock during focused play, including while menus are open. '
            'The shop consumes the same daily and tourist buyers as direct selling.\n\n'
            'Withdraw returns unsold stock to available bag or trunk space. Sell carried now makes '
            'an immediate sale from your cargo, limited by remaining buyers. Neither action sells stock '
            'twice. Each action uses the entered quantity, up to available stock or space.\n\n'
            f'Sold today: {record["sales_today"]} · Revenue today: ${record["revenue_today"]:,}\n'
            f'Total sold: {record["total_sold"]} · Revenue in total: ${record["total_revenue"]:,}')


class BusinessesPanel:
    def __init__(self, game, sites, trades):
        self.game, self.root = game, game.root
        self.sites, self.trades = properties(sites), tuple(trades)
        self.by_name = {site.name: site for site in self.sites}
        self.closed, self.timer = False, None
        self.updating_choices = False
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.businesses_controller = self
        panel.title("Foundry Town · Business Ownership")
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
        tk.Label(body, text="YOUR LISBON BUSINESSES", bg=BG, fg=GOLD,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.heading = tk.Label(body, text="Buy property · Expand storage · Choose your production chain",
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
        self.footer_note = tk.Label(footer, text="B manages businesses · Escape closes",
                                    bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left")
        self.footer_note.pack(side="left", fill="x", expand=True)
        style = ttk.Style(panel)
        style.configure("Businesses.Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Businesses.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_properties()
        self._build_management()
        self._build_counter()
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        panel.grab_set()
        self.property_tree.focus_set()

    def _page(self, title):
        page = ttk.Frame(self.notebook, padding=7)
        self.notebook.add(page, text=title)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        return page

    def _build_properties(self):
        page = self._page("Properties")
        table = ttk.Frame(page)
        table.grid(row=0, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        columns = (("name", "Property", 190), ("kind", "Type", 70), ("product", "Product", 100),
                   ("status", "Ownership", 90), ("price", "Purchase", 80))
        self.property_tree = tree = ttk.Treeview(table, columns=tuple(col[0] for col in columns),
            show="headings", height=5, selectmode="browse", style="Businesses.Treeview")
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=width, stretch=name == "name",
                         anchor="e" if name == "price" else "w")
        vertical = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.bind("<<TreeviewSelect>>", lambda event: self._select_property())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        self.purchase_button = ttk.Button(actions, text="Buy property", command=self._purchase)
        self.purchase_button.pack(side="left", padx=(0, 7))
        self.manage_button = ttk.Button(actions, text="Manage selected", command=self._manage_selected)
        self.manage_button.pack(side="left", padx=(0, 7))
        self.property_guide = ttk.Button(actions, text="Guide to business", command=lambda: self._guide(self._property()))
        self.property_guide.pack(side="left")
        self.property_status = ttk.Label(controls, text="Select a property to review its purchase and current product.",
                                        anchor="w", justify="left")
        self.property_status.pack(fill="x", pady=(4, 0))
        frame, self.property_reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")

    def _chooser(self, page, text, variable):
        frame = ttk.Frame(page)
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=(0, 10), sticky="w")
        combo = ttk.Combobox(frame, textvariable=variable, state="readonly")
        combo.grid(row=0, column=1, sticky="ew", pady=(2, 8))
        return combo

    def _build_management(self):
        page = self._page("Owned management")
        self.owned_choice = tk.StringVar(self.panel)
        self.owned_combo = self._chooser(page, "Owned business", self.owned_choice)
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        upgrades = ttk.Frame(controls)
        upgrades.pack(anchor="w")
        self.storage_button = ttk.Button(upgrades, text="Upgrade storage", command=lambda: self._upgrade("storage"))
        self.storage_button.pack(side="left", padx=(0, 7))
        self.equipment_button = ttk.Button(upgrades, text="Upgrade equipment", command=lambda: self._upgrade("equipment"))
        self.equipment_button.pack(side="left", padx=(0, 7))
        self.management_guide = ttk.Button(upgrades, text="Guide to business", command=lambda: self._guide(self._owned()))
        self.management_guide.pack(side="left")
        specialization = ttk.Frame(controls)
        specialization.pack(fill="x", pady=(8, 0))
        specialization.grid_columnconfigure(1, weight=1)
        ttk.Label(specialization, text="Product / input").grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.specialization = tk.StringVar(self.panel)
        self.product_labels = {f'{trade.product} · {trade.supply}': index for index, trade in enumerate(self.trades)}
        self.specialization_combo = ttk.Combobox(specialization, textvariable=self.specialization,
                                               values=tuple(self.product_labels), state="readonly")
        self.specialization_combo.grid(row=0, column=1, sticky="ew")
        self.retool_button = ttk.Button(specialization, text="Change specialization", command=self._specialize)
        self.retool_button.grid(row=0, column=2, padx=(8, 0))
        self.management_status = ttk.Label(controls, text="Choose an upgrade, or clear stock and routes to change products.",
                                          anchor="w", justify="left")
        self.management_status.pack(fill="x", pady=(5, 0))
        frame, self.management_reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")
        self.owned_choice.trace_add("write", lambda *args: self._owned_changed())
        self.specialization.trace_add("write", lambda *args: self._select_owned())

    def _build_counter(self):
        page = self._page("Shop counter")
        self.shop_choice = tk.StringVar(self.panel)
        self.shop_combo = self._chooser(page, "Owned shop", self.shop_choice)
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        ttk.Label(actions, text="Quantity").pack(side="left", padx=(0, 5))
        self.quantity = tk.StringVar(self.panel, "1")
        self.quantity_entry = ttk.Spinbox(actions, from_=1, to=999999, textvariable=self.quantity, width=6)
        self.quantity_entry.pack(side="left", padx=(0, 8))
        self.deposit_button = ttk.Button(actions, text="Deposit", command=lambda: self._stock_action("deposit"))
        self.deposit_button.pack(side="left", padx=(0, 6))
        self.withdraw_button = ttk.Button(actions, text="Withdraw", command=lambda: self._stock_action("withdraw"))
        self.withdraw_button.pack(side="left", padx=(0, 6))
        self.sell_button = ttk.Button(actions, text="Sell carried now", command=lambda: self._stock_action("sell"))
        self.sell_button.pack(side="left", padx=(0, 6))
        self.shop_guide = ttk.Button(actions, text="Guide to shop", command=lambda: self._guide(self._shop()))
        self.shop_guide.pack(side="left")
        self.shop_status = ttk.Label(controls, text="Visit an owned shop to move or sell products.",
                                    anchor="w", justify="left")
        self.shop_status.pack(fill="x", pady=(5, 0))
        frame, self.shop_reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")
        self.shop_choice.trace_add("write", lambda *args: self._select_shop())

    def _property(self):
        selected = self.property_tree.selection()
        return self.by_name.get(selected[0]) if selected else None

    def _owned(self):
        return self.by_name.get(self.owned_choice.get())

    def _shop(self):
        return self.by_name.get(self.shop_choice.get())

    def _select_property(self):
        site = self._property()
        record = record_for(self.game.town, site) if site else None
        self.purchase_button.configure(state="normal" if site and not record else "disabled",
            text=f'Buy property · ${PURCHASE_PRICES[site.role]:,}' if site and not record else "Property owned")
        self.manage_button.configure(state="normal" if record else "disabled")
        self.property_guide.configure(state="normal" if site else "disabled")
        if site:
            _write(self.property_reader, property_text(self.game.town, site, self.trades))

    def _owned_changed(self):
        if self.updating_choices:
            return
        site = self._owned()
        if site:
            index = trade_for(self.game.town, site)
            self.specialization.set(next(label for label, trade in self.product_labels.items() if trade == index))
        self._select_owned()

    def _select_owned(self):
        if self.updating_choices:
            return
        town, site = self.game.town, self._owned()
        record = record_for(town, site) if site else None
        for kind, button in (("storage", self.storage_button), ("equipment", self.equipment_button)):
            cost = upgrade_cost(town, site, kind) if record else None
            button.configure(state="normal" if cost is not None else "disabled",
                             text=upgrade_label(town, site, kind) if record else f"Upgrade {kind}")
        self.management_guide.configure(state="normal" if record else "disabled")
        self.specialization_combo.configure(state="readonly" if record else "disabled")
        index = self.product_labels.get(self.specialization.get())
        change = record is not None and index is not None and index != trade_for(town, site)
        reason = specialization_block_reason(town, site) if record else None
        self.retool_button.configure(state="normal" if change and not reason else "disabled")
        _write(self.management_reader, management_text(town, site, self.trades) if record else
               "You do not own a business yet. Choose a factory or shop in Properties and buy it.")

    def _select_shop(self):
        if self.updating_choices:
            return
        town, site = self.game.town, self._shop()
        record = record_for(town, site) if site else None
        allowed = shop_actions_allowed(town, site)
        stock = record["stock"] if record else 0
        carried = town.goods[trade_for(town, site)] if record else 0
        room = storage_capacity(town, site)-stock if record else 0
        self.deposit_button.configure(state="normal" if allowed and carried > 0 and room > 0 else "disabled")
        self.withdraw_button.configure(state="normal" if allowed and stock > 0 else "disabled")
        self.sell_button.configure(state="normal" if allowed and carried > 0 else "disabled")
        self.shop_guide.configure(state="normal" if record else "disabled")
        _write(self.shop_reader, shop_text(town, site, self.trades) if record else
               "Buy a public shop in Properties to stock its shelves and serve NPC customers.")

    def _purchase(self):
        site = self._property()
        if site:
            success = self.game.town.purchase_business(site.name)
            message = self.game.town.message
            self.refresh()
            self.property_status.configure(text=message)
            if success:
                self.owned_choice.set(site.name)
                self.management_status.configure(text=message)
                self.notebook.select(1)
        return "break"

    def _manage_selected(self):
        site = self._property()
        if site and record_for(self.game.town, site):
            self.owned_choice.set(site.name)
            self.notebook.select(1)
        return "break"

    def _upgrade(self, kind):
        site = self._owned()
        if site:
            self.game.town.upgrade_business(site.name, kind)
            message = self.game.town.message
            self.refresh()
            self.management_status.configure(text=message)
        return "break"

    def _specialize(self):
        site = self._owned()
        index = self.product_labels.get(self.specialization.get())
        if site and index is not None:
            self.game.town.specialize_business(site.name, index)
            message = self.game.town.message
            self.refresh()
            self.management_status.configure(text=message)
        return "break"

    def _stock_action(self, kind):
        site, quantity = self._shop(), quantity_value(self.quantity.get())
        if quantity is None:
            self.shop_status.configure(text="Enter a positive whole number of products.")
        elif site:
            actions = {"deposit": self.game.town.stock_business, "withdraw": self.game.town.withdraw_business,
                       "sell": self.game.town.sell_business_carried}
            actions[kind](site.name, quantity)
            message = self.game.town.message
            self.refresh()
            self.shop_status.configure(text=message)
        return "break"

    def _guide(self, site):
        if site:
            x, y = site.door
            self.game.world_view.set_destination(site.name, x, y+18, action="E to use business · B to manage")
            return self.close()
        return "break"

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        town = self.game.town
        owned = [site for site in self.sites if record_for(town, site)]
        shops = [site for site in owned if site.role == "PUBLIC SHOP"]
        invested = sum(record_for(town, site)["invested"] for site in owned)
        self.summary.configure(text=f'Cash ${town.cash:,} · Owned {len(owned)} properties · Investment ${invested:,}\n'
            'Factory $600 · Shop $450 · Unowned businesses remain usable')
        for site in self.sites:
            values = property_values(town, site, self.trades)
            if self.property_tree.exists(site.name):
                if tuple(self.property_tree.item(site.name, "values")) != tuple(map(str, values)):
                    self.property_tree.item(site.name, values=values)
            else:
                self.property_tree.insert("", "end", iid=site.name, values=values)
        if not self.property_tree.selection() and self.sites:
            self.property_tree.selection_set(self.sites[0].name)
        old_owned = self.owned_choice.get()
        self.updating_choices = True
        for combo, variable, choices in ((self.owned_combo, self.owned_choice, owned),
                                         (self.shop_combo, self.shop_choice, shops)):
            names = tuple(site.name for site in choices)
            combo.configure(values=names)
            if variable.get() not in names:
                variable.set(names[0] if names else "")
        self.updating_choices = False
        if old_owned != self.owned_choice.get():
            self._owned_changed()
        self._select_property()
        self._select_owned()
        self._select_shop()
        self.timer = self.panel.after(1000, self.refresh)

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-62)
            for label in (self.heading, self.summary, self.property_status, self.management_status, self.shop_status):
                label.configure(wraplength=width)
            self.footer_note.configure(wraplength=max(230, event.width-220))

    def _release(self):
        if self.closed:
            return
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


def open_businesses(game, sites, trades):
    if getattr(game, "profile_window", None) is not None:
        return None
    return BusinessesPanel(game, sites, trades).panel
