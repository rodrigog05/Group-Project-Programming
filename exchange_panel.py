"""The in-game Bolsa de Lisboa portfolio and trading window."""
import tkinter as tk
from tkinter import ttk

from exchange import (ASSET_BY_SYMBOL, ASSETS, BID_PERCENT, CITY_TICK_SECONDS,
                      buy_shares, portfolio_rows, sell_shares, summary)


BG, PANEL, TEXT, MUTED, GOLD = "#142c36", "#203f4b", "#f5efd9", "#c8d6d5", "#e2bd68"


def money_cents(value):
    """Display the ledger's integer cents without floating-point rounding."""
    sign = "-" if value < 0 else ""
    dollars, cents = divmod(abs(value), 100)
    return f"{sign}${dollars:,}.{cents:02}"


def share_quantity(value):
    """An entry accepts positive whole units, never decimal or signed amounts."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 6 or not value.isascii() or not value.isdecimal():
        return None
    quantity = int(value)
    return quantity if quantity > 0 else None


def portfolio_values(row):
    return (row["name"], f'${row["ask"]:,}', f'${row["bid"]:,}', row["owned"],
            f'${row["cost_basis"]:,}', f'${row["value"]:,}',
            money_cents(row["pending_cents"]), row["activity"])


def portfolio_text(snapshot):
    return (f'Cash ${snapshot["cash"]:,}  ·  Shares {snapshot["owned"]:,}  ·  '
            f'Cost basis ${snapshot["cost_basis"]:,}  ·  Exit value ${snapshot["value"]:,}\n'
            f'Pending dividends {money_cents(snapshot["pending_cents"])} before tax  ·  '
            f'Dividends received ${snapshot["total_dividends"]:,}')


def trade_preview(row, quantity, cash):
    if quantity is None:
        return "Enter a positive whole number of shares."
    cost, proceeds = row["ask"] * quantity, row["bid"] * quantity
    buy = (f'Buy {quantity}: ${cost:,}' if quantity + row["owned"] <= row["cap"]
           else f'Buy: maximum {row["cap"]} shares per investment')
    if quantity + row["owned"] <= row["cap"] and cost > cash:
        buy += f' (need ${cost-cash:,} more)'
    sell = (f'Sell {quantity}: ${proceeds:,}' if quantity <= row["owned"]
            else f'Sell: you own {row["owned"]}')
    return f"{buy}  ·  {sell}"


def asset_text(row):
    asset = ASSET_BY_SYMBOL[row["symbol"]]
    return (f'{row["name"]} · {row["kind"]}\n\n{row["description"]}\n\n'
            f'You own {row["owned"]}/{row["cap"]} shares. '
            f'Your cost basis is ${row["cost_basis"]:,}; selling all now returns ${row["value"]:,}.\n'
            f'Each activity unit earns {money_cents(row["dividend_cents"])} per share you hold at that moment. '
            f'The wider city generates {asset.city_units} units every {CITY_TICK_SECONDS} active seconds; '
            'your relevant sales or paid journeys add extra units.\n'
            f'Today: {row["city_activity"]} city units + {row["player_activity"]} from you '
            f'= {row["activity"]} total units.\n'
            f'Your pending dividends: {money_cents(row["pending_cents"])} before tax. '
            f'Your latest payout: ${row["last_payout"]:,}.\n\n'
            'Only activity after buying shares earns dividends. Sell before the day closes and '
            'the dividends already earned remain pending. Payment is automatic at day close.')


def activity_text(rows, snapshot):
    lines = ["CITY ACTIVITY & DIVIDENDS", "",
             "City activity includes simulated customers and journeys, plus your own relevant actions. "
             "It does not use up the buyers shown in your shop menus.", ""]
    for row in rows:
        lines.extend((f'{row["name"]}',
                      f'  Today: {row["city_activity"]} city + {row["player_activity"]} yours '
                      f'= {row["activity"]} activity units',
                      f'  Your pending: {money_cents(row["pending_cents"])}  ·  '
                      f'Latest payout: ${row["last_payout"]:,}  ·  '
                      f'Received in total: ${row["total_dividends"]:,}', ""))
    statement = snapshot.get("last_statement") or {}
    if snapshot["last_settlement"] > 0 and statement:
        lines.extend((f'LATEST DAY CLOSE · Day {statement["day"]}',
                      f'Dividends paid: ${snapshot["last_payout"]:,} before the daily profit tax.', ""))
        paid = statement.get("by_asset", {})
        lines.extend(f'  {asset.name}: ${paid.get(asset.symbol, 0):,}' for asset in ASSETS)
    else:
        lines.append("Your first dividend statement appears when the current day closes.")
    lines.extend(("", "Each investment pays its whole dollars; its remaining cents carry forward. "
                  "Paid dividends become ordinary income; "
                  "the normal daily tax applies to positive net profit. "
                  "Activity and pending earnings save with your game. There is no offline activity."))
    return "\n".join(lines)


def exchange_rules():
    rates = "\n".join(f'• {asset.name}: {asset.city_units} activity units every '
                      f'{CITY_TICK_SECONDS} active seconds; '
                      f'{money_cents(asset.dividend_cents)} per held share per unit.' for asset in ASSETS)
    return ("INVEST IN YOUR CITY\n\n"
            "Choose a district business or a city service in the Shares tab, enter a quantity, "
            "then buy or sell. Cash pays for shares immediately. The holding limit shown for each "
            "investment applies to the number you own.\n\n"
            "Buy is the price you pay per share. Sell is what you receive per share: "
            f'{BID_PERCENT}% of the buy quote, rounded down to whole dollars. '
            "Quotes change at day close with city activity. A sale can return less than you paid. "
            "Exit value uses the current sell quote. Cost basis tracks the purchase money still "
            "invested in your remaining shares.\n\n"
            "HOW DIVIDENDS GROW\n\n"
            f'The wider city adds activity every {CITY_TICK_SECONDS} seconds of focused play, '
            "including while this window is open. Your completed shop sales and boat repairs "
            "add activity to their districts. Paid return journeys across 25 de Abril add bridge "
            "activity; paid tram trips add tram activity. Vasco da Gama tolls do not belong to "
            "the 25 de Abril investment.\n\n"
            "You earn only on the shares you hold when the activity occurs. Buying later does "
            "not collect earlier earnings. Selling preserves dividends already earned.\n\n"
            f'{rates}\n\n'
            "PAYMENT, TAX & SAVING\n\n"
            "Dividends pay automatically at the end of each five-minute game day. Whole dollars "
            "from each investment are paid once; that investment's remaining cents carry forward. "
            "Dividends and realized share profits count as "
            "income for the normal daily profit tax. Buying shares is an investment, not a "
            "business expense; selling returns your cost basis and realizes the gain or loss.\n\n"
            "Your shares, cost basis and pending dividends save with your progress. Activity "
            "stops when the game is unfocused or closed. Time away does not create dividends. "
            "All prices and earnings here belong to the Foundry Town game economy.")


def _write(widget, value):
    if widget.get("1.0", "end-1c") == value:
        return
    position = widget.yview()[0]
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")
    widget.yview_moveto(position)


def _reader(master):
    frame = ttk.Frame(master)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    reader = tk.Text(frame, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                     font=("Segoe UI", 10), padx=12, pady=10, relief="flat", borderwidth=0,
                     state="disabled", width=40, height=3, takefocus=True)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=reader.yview)
    reader.configure(yscrollcommand=scrollbar.set)
    reader.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    return frame, reader


class ExchangePanel:
    def __init__(self, game):
        self.game, self.root = game, game.root
        self.closed, self.timer = False, None
        self.rows, self.snapshot = (), None
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.exchange_controller = self
        panel.title("Foundry Town · Bolsa de Lisboa")
        panel.transient(self.root)
        panel.configure(bg=BG)
        panel.resizable(True, True)
        panel.minsize(680, 500)
        available_width = self.root.winfo_width() if self.root.winfo_width() > 100 else self.root.winfo_screenwidth()
        available_height = self.root.winfo_height() if self.root.winfo_height() > 100 else self.root.winfo_screenheight()
        width, height = min(1080, max(680, available_width-80)), min(700, max(500, available_height-80))
        x = self.root.winfo_rootx()+max(0, (available_width-width)//2)
        y = self.root.winfo_rooty()+max(0, (available_height-height)//2)
        panel.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(panel, bg=BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="BOLSA DE LISBOA", bg=BG, fg=GOLD,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.heading = tk.Label(body, text="Baixa-Chiado · Own a share of the city's activity",
                                bg=BG, fg=MUTED, font=("Segoe UI", 10), anchor="w", justify="left")
        self.heading.pack(fill="x", pady=(0, 5))
        self.portfolio = tk.Label(body, bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold"),
                                  justify="left", anchor="w")
        self.portfolio.pack(fill="x", pady=(0, 8))
        footer = tk.Frame(body, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Button(footer, text="Return to town", command=self.close, bg=GOLD, fg="#172c33",
                   activebackground="#f0d591", relief="flat", padx=16, pady=7,
                   cursor="hand2", font=("Segoe UI", 10, "bold")).pack(side="right")
        self.footer_note = tk.Label(footer, text="Day-close payouts · Escape closes", bg=BG,
                                    fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left")
        self.footer_note.pack(side="left", fill="x", expand=True)
        style = ttk.Style(panel)
        style.configure("Exchange.Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Exchange.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_trading()
        activity_frame, self.activity_reader = _reader(self.notebook)
        self.notebook.add(activity_frame, text="Dividends & activity")
        rules_frame, self.rules_reader = _reader(self.notebook)
        self.notebook.add(rules_frame, text="How it works")
        _write(self.rules_reader, exchange_rules())
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        panel.grab_set()
        self.tree.focus_set()

    def _build_trading(self):
        page = ttk.Frame(self.notebook, padding=7)
        self.notebook.add(page, text="Shares")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        table = ttk.Frame(page)
        table.grid(row=0, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        columns = (("asset", "Investment", 195), ("ask", "Buy $", 62),
                   ("bid", "Sell $", 62), ("owned", "Owned", 62),
                   ("basis", "Cost basis", 82), ("value", "Exit value", 82),
                   ("pending", "Pending $", 85), ("activity", "Activity", 70))
        self.tree = ttk.Treeview(table, columns=tuple(col[0] for col in columns),
                                 show="headings", selectmode="browse", height=4,
                                 style="Exchange.Treeview")
        for name, title, width in columns:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=width, stretch=name == "asset",
                              anchor="w" if name == "asset" else "e")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self._select())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)
        actions = ttk.Frame(controls)
        actions.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(actions, text="Quantity").pack(side="left", padx=(0, 5))
        self.quantity = tk.StringVar(self.panel, "1")
        self.quantity_entry = ttk.Spinbox(actions, from_=1, to=max(asset.cap for asset in ASSETS),
                                         textvariable=self.quantity, width=7)
        self.quantity_entry.pack(side="left", padx=(0, 10))
        ttk.Button(actions, text="Buy shares", command=lambda: self._trade(True)).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Sell shares", command=lambda: self._trade(False)).pack(side="left")
        self.preview = ttk.Label(controls, anchor="w", justify="left")
        self.preview.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.status = ttk.Label(controls, text="Select an investment, then choose how many shares to trade.",
                                anchor="w", justify="left")
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        detail, self.asset_reader = _reader(self.notebook)
        self.notebook.add(detail, text="Investment details")
        self.quantity.trace_add("write", lambda *args: self._select())

    def _selected_row(self):
        selected = self.tree.selection()
        return next((row for row in self.rows if selected and row["symbol"] == selected[0]), None)

    def _select(self):
        row = self._selected_row()
        if row is not None:
            _write(self.asset_reader, asset_text(row))
            self.preview.configure(text=trade_preview(row, share_quantity(self.quantity.get()), self.game.town.cash))

    def _trade(self, buying):
        row = self._selected_row()
        quantity = share_quantity(self.quantity.get())
        if row is None:
            self.status.configure(text="Select an investment first.")
        elif quantity is None:
            self.status.configure(text="Enter a positive whole number of shares, such as 1 or 5.")
        else:
            action = buy_shares if buying else sell_shares
            action(self.game.town, row["symbol"], quantity)
            self.status.configure(text=self.game.town.message)
            self.refresh()
        return "break"

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        self.rows, self.snapshot = portfolio_rows(self.game.town), summary(self.game.town)
        self.portfolio.configure(text=portfolio_text(self.snapshot))
        for row in self.rows:
            values = portfolio_values(row)
            if self.tree.exists(row["symbol"]):
                if tuple(self.tree.item(row["symbol"], "values")) != tuple(map(str, values)):
                    self.tree.item(row["symbol"], values=values)
            else:
                self.tree.insert("", "end", iid=row["symbol"], values=values)
        if not self.tree.selection() and self.rows:
            self.tree.selection_set(self.rows[0]["symbol"])
            self.tree.focus(self.rows[0]["symbol"])
        self._select()
        _write(self.activity_reader, activity_text(self.rows, self.snapshot))
        self.timer = self.panel.after(1000, self.refresh)

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-62)
            self.heading.configure(wraplength=width)
            self.portfolio.configure(wraplength=width)
            self.preview.configure(wraplength=width)
            self.status.configure(wraplength=width)

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


def open_exchange(game):
    if getattr(game, "profile_window", None) is not None:
        return None
    return ExchangePanel(game).panel
