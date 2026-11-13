"""A live order board for timed contracts and permanent Lisbon city projects."""
import tkinter as tk
from tkinter import ttk

from contracts import (ACTIVE_LIMIT, CYCLE_SECONDS, OFFER_BY_KEY, PRODUCT_NAMES,
                       PROJECTS, UPGRADE_DESCRIPTIONS, UPGRADE_NAMES, active_offer,
                       available_offers, inventory_amount, near_destination,
                       rank_name, remaining_seconds)
from research_panel import (BG, GOLD, MUTED, TEXT, _reader, _write, duration_text,
                            quantity_value)


def reward_text(cash, reputation, upgrade=None):
    parts = [f"${cash:,} fixed payment", f"+{reputation} reputation"]
    if upgrade:
        parts.append(UPGRADE_DESCRIPTIONS[upgrade])
    return " · ".join(parts)


def project_state(town, offer):
    state = town.contracts
    if offer.key in state["completed_projects"]:
        return "Completed"
    if any(record["key"] == offer.key for record in state["active"]):
        return "In progress"
    if offer.minimum_reputation > state["reputation"]:
        return f"Needs {offer.minimum_reputation} reputation"
    return "Available" if offer in available_offers(town) else "Unavailable"


def offer_values(offer):
    return (offer.title, PRODUCT_NAMES[offer.product_key], offer.quantity,
            duration_text(offer.seconds), f"${offer.cash:,}", f"+{offer.reputation}")


def offer_text(town, offer):
    product = PRODUCT_NAMES[offer.product_key]
    state = project_state(town, offer) if offer.kind == "project" else "Recurring contract"
    lines = [f"{offer.title} · {state}", "", offer.description, "",
             f"Deliver {offer.quantity} {product} to {offer.location.name}.",
             f"Time limit after accepting: {duration_text(offer.seconds)} of focused play.",
             f"Reward on full completion: {reward_text(offer.cash, offer.reputation, offer.upgrade)}.",
             f"You currently carry {inventory_amount(town, offer.product_key)} {product}."]
    if offer.minimum_reputation:
        lines.append(f"Requires {offer.minimum_reputation} reputation; you have {town.contracts['reputation']}.")
    lines.extend(("", "Accept first, then visit the marked client location and deliver from your cargo. "
                  "You can make partial deliveries. Payment and reputation arrive only after the full "
                  "quantity is delivered before the deadline. Contract payments do not use shop buyers.", "",
                  f"You can hold {ACTIVE_LIMIT} active orders, including city projects. "
                  "Accepting is free. Delivered goods are committed to the order: "
                  "they are not returned if you miss the deadline or abandon it."))
    if offer.kind == "project":
        lines.extend(("", "This city project can be completed once. Its upgrade is permanent "
                      "and saves with your game."))
    else:
        lines.extend(("", f"The recurring board rotates every {CYCLE_SECONDS//60} minutes of focused play. "
                      "Rotation replaces available offers; accepted orders keep their own deadlines."))
    return "\n".join(lines)


def active_values(town, record):
    offer = active_offer(record)
    return (offer.title, f'{record["delivered"]}/{record["required"]}',
            inventory_amount(town, offer.product_key), duration_text(remaining_seconds(town, record)),
            f'${record["cash"]:,}')


def delivery_allowed(town, record):
    offer = active_offer(record)
    return (remaining_seconds(town, record) > 0 and near_destination(town, offer)
            and inventory_amount(town, offer.product_key) > 0)


def active_text(town, record):
    offer = active_offer(record)
    product = PRODUCT_NAMES[offer.product_key]
    remaining = record["required"]-record["delivered"]
    location = ("You are at the client location. Choose a quantity and deliver."
                if near_destination(town, offer) else
                "Travel to this client to deliver. Guide to client marks the destination.")
    return (f'{offer.title}\n\n{offer.description}\n\n'
            f'Client: {offer.location.name}\n'
            f'Delivered: {record["delivered"]}/{record["required"]} {product} · Still needed: {remaining}\n'
            f'In your cargo: {inventory_amount(town, offer.product_key)} {product}\n'
            f'Time remaining: {duration_text(remaining_seconds(town, record))} of focused play\n'
            f'Reward: {reward_text(record["cash"], record["reputation"], record.get("upgrade"))}\n\n'
            f'{location}\n\n'
            'Partial deliveries are accepted up to the order’s remaining requirement and your carried stock. '
            'Factory storage, warehouse storage and goods in production must be collected into your cargo first. '
            'The fixed payment and reputation are awarded once, when the order is complete.\n\n'
            'Missing the deadline or abandoning the order forfeits all goods already delivered. '
            'Partial deliveries are not refunded and earn no partial payment. '
            'The timer pauses when the game is closed or unfocused, and continues while menus are open.')


def history_values(record):
    offer = OFFER_BY_KEY[record["key"]]
    paid = record["status"] == "completed"
    return (offer.title, record["status"].capitalize(),
            f'{record["delivered"]}/{record["required"]}',
            f'${record["cash"]:,}' if paid else "$0",
            f'+{record["reputation"]}' if paid else "+0")


def reputation_text(town):
    state = town.contracts
    lines = [f'{rank_name(town)} · {state["reputation"]} reputation', "",
             f'Completed orders: {state["completed"]} · Failed: {state["failed"]} · Abandoned: {state["abandoned"]}',
             f'Contract payments earned: ${state["cash_earned"]:,} · Today: ${state["revenue_today"]:,}',
             "", "PERMANENT CITY UPGRADES"]
    for offer in PROJECTS:
        upgrade = offer.upgrade
        status = "UNLOCKED" if upgrade in state["upgrades"] else "Not yet unlocked"
        lines.extend((f"{UPGRADE_NAMES[upgrade]} · {status}",
                      f"  {UPGRADE_DESCRIPTIONS[upgrade]}", f"  Complete: {offer.title}", ""))
    lines.extend(("Reputation comes from fully completed orders. Higher reputation opens more demanding "
                  "offers on later board rotations. Permanent upgrades remain available after spending cash "
                  "or failing another order.", "", "Active orders, partial deliveries, deadlines, reputation "
                  "and city upgrades save with your progress. There is no offline deadline catch-up."))
    return "\n".join(lines)


class ContractsPanel:
    def __init__(self, game):
        self.game, self.root = game, game.root
        self.closed, self.timer = False, None
        self.pending_abandon = None
        self.offers = {}
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.contracts_controller = self
        panel.title("Foundry Town · Contracts & City Projects")
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
        tk.Label(body, text="CONTRACTS & CITY PROJECTS", bg=BG, fg=GOLD,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.heading = tk.Label(body, text="Supply the city · Meet deadlines · Earn permanent upgrades",
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
        self.footer_note = tk.Label(footer, text="Deadlines run while focused · Escape closes",
                                    bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left")
        self.footer_note.pack(side="left", fill="x", expand=True)
        style = ttk.Style(panel)
        style.configure("Contracts.Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Contracts.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_offers(False)
        self._build_offers(True)
        self._build_active()
        self._build_history()
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        panel.grab_set()
        self.offer_tree.focus_set()

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
                            selectmode="browse", height=height, style="Contracts.Treeview")
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=width, stretch=name == columns[0][0],
                         anchor="w" if name in (columns[0][0], "product", "status") else "e")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    def _build_offers(self, projects):
        page = self._page("City projects" if projects else "Available contracts")
        columns = (("title", "City project", 235), ("status", "Status", 125),
                   ("quantity", "Units", 50), ("time", "Deadline", 75), ("cash", "Payment", 80)) if projects else (
                   ("title", "Contract", 180), ("product", "Product", 105), ("quantity", "Units", 45),
                   ("time", "Deadline", 75), ("cash", "Payment", 75), ("rep", "Rep", 45))
        tree = self._table(page, columns, 3)
        tree.bind("<<TreeviewSelect>>", lambda event: self._select_offer(projects))
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        button = ttk.Button(controls, text="Accept city project" if projects else "Accept contract",
                            command=lambda: self._accept(projects))
        button.pack(anchor="w")
        status = ttk.Label(controls, text="Review the quantity, deadline and rewards before accepting.",
                           anchor="w", justify="left")
        status.pack(fill="x", pady=(4, 0))
        frame, reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")
        if projects:
            self.project_tree, self.project_reader = tree, reader
            self.project_button, self.project_status = button, status
        else:
            self.offer_tree, self.offer_reader = tree, reader
            self.offer_button, self.offer_status = button, status

    def _build_active(self):
        page = self._page("Active orders")
        self.active_tree = self._table(page, (("title", "Order", 210), ("delivered", "Delivered", 85),
            ("stock", "Carried", 65), ("time", "Time left", 90), ("cash", "Payment", 85)), 3)
        self.active_tree.bind("<<TreeviewSelect>>", lambda event: self._select_active())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        actions = ttk.Frame(controls)
        actions.pack(anchor="w")
        ttk.Label(actions, text="Quantity").pack(side="left", padx=(0, 5))
        self.quantity = tk.StringVar(self.panel, "1")
        self.quantity_entry = ttk.Spinbox(actions, from_=1, to=999999,
                                         textvariable=self.quantity, width=6)
        self.quantity_entry.pack(side="left", padx=(0, 8))
        self.deliver_button = ttk.Button(actions, text="Deliver to client", command=self._deliver)
        self.deliver_button.pack(side="left", padx=(0, 7))
        self.guide_button = ttk.Button(actions, text="Guide to client", command=self._guide)
        self.guide_button.pack(side="left", padx=(0, 7))
        self.abandon_button = ttk.Button(actions, text="Abandon…", command=self._ask_abandon)
        self.abandon_button.pack(side="left")
        self.active_status = ttk.Label(controls, text="Visit the client to deliver carried products.",
                                      anchor="w", justify="left")
        self.active_status.pack(fill="x", pady=(4, 0))
        self.confirmation = ttk.Frame(controls)
        self.abandon_warning = ttk.Label(self.confirmation, foreground="#a82e20", justify="left",
            text="Abandon this order? All delivered goods are lost. No payment or reputation is awarded.")
        self.abandon_warning.pack(fill="x", pady=(4, 3))
        confirmation_actions = ttk.Frame(self.confirmation)
        confirmation_actions.pack(anchor="w")
        ttk.Button(confirmation_actions, text="Confirm abandon", command=self._confirm_abandon).pack(side="left", padx=(0, 7))
        ttk.Button(confirmation_actions, text="Keep order", command=self._cancel_abandon).pack(side="left")
        frame, self.active_reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")

    def _build_history(self):
        page = self._page("History & reputation")
        self.history_tree = self._table(page, (("title", "Order", 200), ("status", "Result", 95),
            ("delivered", "Delivered", 85), ("cash", "Paid", 80), ("rep", "Rep earned", 80)), 3)
        heading = ttk.Label(page, text="Permanent upgrades and your latest completed, expired or abandoned orders.",
                            anchor="w", justify="left", padding=(0, 6))
        heading.grid(row=1, column=0, sticky="ew")
        self.history_heading = heading
        frame, self.reputation_reader = _reader(page)
        frame.grid(row=2, column=0, sticky="nsew")

    def _selected_offer(self, projects):
        tree = self.project_tree if projects else self.offer_tree
        selected = tree.selection()
        return OFFER_BY_KEY.get(selected[0]) if selected else None

    def _selected_active(self):
        selected = self.active_tree.selection()
        return next((record for record in self.game.town.contracts["active"]
                     if selected and str(record["id"]) == selected[0]), None)

    def _select_offer(self, projects):
        offer = self._selected_offer(projects)
        button = self.project_button if projects else self.offer_button
        reader = self.project_reader if projects else self.offer_reader
        town = self.game.town
        eligible = offer is not None and offer.key in self.offers
        capacity = len(town.contracts["active"]) < ACTIVE_LIMIT
        button.configure(state="normal" if eligible and capacity else "disabled",
                         text=("Active orders full" if eligible and not capacity else
                               "Accept city project" if projects else "Accept contract"))
        _write(reader, offer_text(town, offer) if offer else
               "No recurring offers are available right now. Check active orders or return after the next board rotation.")

    def _select_active(self):
        record = self._selected_active()
        if self.pending_abandon is not None and (record is None or record["id"] != self.pending_abandon):
            self._cancel_abandon()
        allowed = record is not None and delivery_allowed(self.game.town, record)
        self.deliver_button.configure(state="normal" if allowed else "disabled")
        self.guide_button.configure(state="normal" if record else "disabled")
        self.abandon_button.configure(state="normal" if record else "disabled")
        _write(self.active_reader, active_text(self.game.town, record) if record else
               "No active orders. Accept a contract or city project, gather its products and visit the client to deliver.")

    def _accept(self, projects):
        offer = self._selected_offer(projects)
        status = self.project_status if projects else self.offer_status
        if offer is None:
            status.configure(text="Select an offer first.")
        else:
            success = self.game.town.accept_contract(offer.key)
            message = self.game.town.message
            self.refresh()
            status.configure(text=message)
            if success:
                record = next(record for record in self.game.town.contracts["active"] if record["key"] == offer.key)
                self.active_tree.selection_set(str(record["id"]))
                self.active_tree.focus(str(record["id"]))
                self.active_status.configure(text=message)
                self.notebook.select(2)
        return "break"

    def _deliver(self):
        record, quantity = self._selected_active(), quantity_value(self.quantity.get())
        if record is None:
            self.active_status.configure(text="Select an active order first.")
        elif quantity is None:
            self.active_status.configure(text="Enter a positive whole number of products.")
        else:
            self.game.town.deliver_contract(record["id"], quantity)
            message = self.game.town.message
            self.refresh()
            self.active_status.configure(text=message)
        return "break"

    def _guide(self):
        record = self._selected_active()
        if record:
            offer = active_offer(record)
            self.game.world_view.set_destination(f"Contract · {offer.title}", offer.location.x,
                                                 offer.location.y, action="C to deliver contract")
            return self.close()
        return "break"

    def _ask_abandon(self):
        record = self._selected_active()
        if record:
            self.pending_abandon = record["id"]
            self.confirmation.pack(fill="x", pady=(3, 0))
        return "break"

    def _cancel_abandon(self):
        self.pending_abandon = None
        self.confirmation.pack_forget()
        return "break"

    def _confirm_abandon(self):
        if self.pending_abandon is not None:
            self.game.town.abandon_contract(self.pending_abandon)
            message = self.game.town.message
            self._cancel_abandon()
            self.refresh()
            self.active_status.configure(text=message)
        return "break"

    @staticmethod
    def _sync_rows(tree, rows):
        rows = tuple(rows)
        keys = {key for key, values in rows}
        for key in tree.get_children():
            if key not in keys:
                tree.delete(key)
        for index, (key, values) in enumerate(rows):
            if tree.exists(key):
                if tuple(tree.item(key, "values")) != tuple(map(str, values)):
                    tree.item(key, values=values)
            else:
                tree.insert("", "end", iid=key, values=values)
            tree.move(key, "", index)
        if not tree.selection() and rows:
            tree.selection_set(rows[0][0])
            tree.focus(rows[0][0])

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        town = self.game.town
        state = town.contracts
        rotation = CYCLE_SECONDS-state["elapsed"] % CYCLE_SECONDS
        self.summary.configure(text=f'Cash ${town.cash:,} · {rank_name(town)} · Reputation {state["reputation"]} · '
            f'Active {len(state["active"])}/{ACTIVE_LIMIT}\nNext recurring board in {duration_text(rotation)} of focused play')
        self.offers = {offer.key: offer for offer in available_offers(town)}
        self._sync_rows(self.offer_tree, ((offer.key, offer_values(offer))
                        for offer in self.offers.values() if offer.kind == "contract"))
        self._sync_rows(self.project_tree, ((offer.key, (offer.title, project_state(town, offer),
                        offer.quantity, duration_text(offer.seconds), f"${offer.cash:,}")) for offer in PROJECTS))
        self._sync_rows(self.active_tree, ((str(record["id"]), active_values(town, record))
                        for record in state["active"]))
        self._sync_rows(self.history_tree, ((str(record["id"]), history_values(record))
                        for record in reversed(state["history"])))
        self._select_offer(False)
        self._select_offer(True)
        self._select_active()
        _write(self.reputation_reader, reputation_text(town))
        self.timer = self.panel.after(1000, self.refresh)

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-62)
            for label in (self.heading, self.summary, self.offer_status, self.project_status,
                          self.active_status, self.abandon_warning, self.history_heading):
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


def open_contracts(game):
    if getattr(game, "profile_window", None) is not None:
        return None
    return ContractsPanel(game).panel
