"""The player's recipe, history and market journal. Reading works offline."""
import tkinter as tk
from tkinter import ttk
import webbrowser

from journal_lore import GAME_MAP_NOTE, LANDMARK_LORE, TEJO_LORE
from journal_market import market_snapshot


BG, PANEL, TEXT, MUTED, GOLD = "#142c36", "#203f4b", "#f5efd9", "#c8d6d5", "#e2bd68"


def recipe_text(recipe, discovered, sites):
    """Format a recipe without exposing an undiscovered ingredient list."""
    makers = [site.name for site in sites if site.role == recipe.role
              and (recipe.role != "FACTORY" or site.trade == recipe.trade)]
    locations = ", ".join(makers) or "the matching production building"
    if not discovered:
        if recipe.role == "RESEARCH":
            return (f"{recipe.title}\n\nNot recorded yet.\n\n"
                    f"Complete Advanced Metallurgy level {recipe.research_level} at Nova SBE in Carcavelos "
                    "to unlock and record this tier-3 recipe. Press E at the campus to open the research menu. "
                    "Research costs cash and active play time.")
        return (f"{recipe.title}\n\nNot recorded yet.\n\n"
                f"Visit {locations} and press E to add this recipe to your journal. "
                "You can record it even before you have its ingredients.")
    inputs = "\n".join(f"• {amount} × {name}" for name, amount in recipe.ingredients)
    text = (f"{recipe.title}\n\nRECORDED RECIPE\n\nIngredients\n{inputs}\n\n"
            f"{'Service' if recipe.service else 'Output'}: 1 × {recipe.product}\n"
            f"Production time: {recipe.seconds} seconds\n\nMake at: {locations}\n\n")
    if recipe.service:
        return text+"Return when the work finishes to collect the agreed payment. Boats are service jobs and do not occupy cargo space."
    if recipe.role == "RESEARCH":
        return text+(f"Unlocked by Advanced Metallurgy level {recipe.research_level}. "
                     "Press E at Nova SBE in Carcavelos and choose Advanced Workshop. "
                     "Set Quantity and use Fabricate to start a batch, Collect when it finishes, and Sell here at the same workshop. "
                     "Production uses active play time; stock and reserved output share your normal cargo capacity.")
    if recipe.role == "FACTORY":
        markets = [site.name for site in sites if site.role == "PUBLIC SHOP" and site.trade == recipe.trade]
        return text+f"Collect the finished goods, then sell at: {', '.join(markets) or 'the matching market'}."
    return text+"Press E to make the product, return to collect it, then press E again at the same building to sell it."


def market_values(row):
    return (row.product, f"${row.price}", row.stock_label, row.orders, row.sold_today,
            row.ordinary_buyers, row.tourist_buyers, f"${row.revenue_today:,}")


def market_text(row, snapshot):
    cost = f"${row.raw_cost}" if row.raw_cost is not None else "No direct raw-material quote"
    text = (f"{row.product}\n\nRecipe inputs in your inventory: {row.raw_stock}\n"
            f"Current input quote per unit/job: {cost}\nCurrent sale/payment quote: ${row.price}\n"
            f"Your stock: {row.stock_label} · Your orders: {row.orders}\n"
            f"Sold/completed today: {row.sold_today} · Revenue today: ${row.revenue_today:,}\n"
            f"Remaining ordinary {row.demand_label.lower()}: {row.ordinary_buyers}\n"
            f"Remaining local tourists: {row.tourist_buyers}\n"
            f"Total remaining {row.demand_label.lower()}: {row.remaining_buyers}\n\n{row.notes}")
    shops = [shop for shop in snapshot.tourist_shops if shop.product == row.product]
    if shops:
        text += "\n\nTourism by shop\n"+"\n".join(
            f"• {shop.name}: {shop.remaining}/{shop.maximum} extra buyers remaining" for shop in shops)
    return text+f"\n\nReading these figures\n{snapshot.notes}"


def _write(widget, value):
    if widget.get("1.0", "end-1c") != value:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def _reader(master):
    frame = ttk.Frame(master)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    text = tk.Text(frame, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                   font=("Segoe UI", 11), padx=14, pady=12, relief="flat", borderwidth=0,
                   state="disabled", width=40, height=10, takefocus=True)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    text.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    return frame, text


def _table(master, columns, height=8):
    frame = ttk.Frame(master)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    names = tuple(name for name, title, width in columns)
    tree = ttk.Treeview(frame, columns=names, show="headings", height=height,
                        selectmode="browse", style="Journal.Treeview")
    for name, title, width in columns:
        tree.heading(name, text=title)
        tree.column(name, width=width, minwidth=min(width, 85), stretch=True)
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    return frame, tree


class JournalPanel:
    def __init__(self, game, trades, industries, sites):
        from journal_recipes import RECIPES
        self.game, self.root = game, game.root
        self.trades, self.industries, self.sites = trades, industries, tuple(sites)
        self.recipes = tuple(RECIPES)
        self.recipe_lookup = {recipe.key: recipe for recipe in self.recipes}
        self.closed, self.timer, self.snapshot = False, None, None
        self.last_discovered = None
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.journal_controller = self
        panel.title("Foundry Town · Journal")
        panel.transient(self.root)
        panel.configure(bg=BG)
        panel.resizable(True, True)
        panel.minsize(640, 440)
        available_width = self.root.winfo_width() if self.root.winfo_width() > 100 else self.root.winfo_screenwidth()
        available_height = self.root.winfo_height() if self.root.winfo_height() > 100 else self.root.winfo_screenheight()
        width, height = min(1080, max(640, available_width-80)), min(700, max(440, available_height-80))
        x = self.root.winfo_rootx()+max(0, (available_width-width)//2)
        y = self.root.winfo_rooty()+max(0, (available_height-height)//2)
        panel.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(panel, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="LISBOA JOURNAL", bg=BG, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(body, text="Recipes you have found · Lisbon stories · Your market observations",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 10))
        controls = tk.Frame(body, bg=BG)
        controls.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Button(controls, text="Close journal", command=self.close, bg=GOLD, fg="#172c33",
                   activebackground="#f0d591", relief="flat", padx=18, pady=7,
                   cursor="hand2", font=("Segoe UI", 10, "bold")).pack(side="right")
        tk.Label(controls, text="Discoveries save with your progress. Escape closes this panel.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        style = ttk.Style(panel)
        style.configure("Journal.Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Journal.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_recipes()
        self.lore_views = []
        self._build_lore("Landmarks", LANDMARK_LORE)
        self._build_lore("Tejo", TEJO_LORE)
        self._build_markets()
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        panel.grab_set()
        self.recipe_tree.focus_set()

    def _build_recipes(self):
        page = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(page, text="Recipes")
        self.recipe_progress = ttk.Label(page, font=("Segoe UI", 11, "bold"))
        self.recipe_progress.pack(anchor="w", pady=(0, 3))
        ttk.Label(page, text="Visit a production building and press E to record its recipe.").pack(anchor="w", pady=(0, 8))
        panes = ttk.Panedwindow(page, orient="horizontal")
        panes.pack(fill="both", expand=True)
        table, self.recipe_tree = _table(panes, (("recipe", "Recipe", 220), ("status", "Journal", 115)))
        reader, self.recipe_reader = _reader(panes)
        panes.add(table, weight=2)
        panes.add(reader, weight=3)
        self.recipe_tree.tag_configure("locked", foreground="#65766f")
        self.recipe_tree.bind("<<TreeviewSelect>>", lambda event: self._select_recipe())

    def _select_recipe(self):
        selected = self.recipe_tree.selection()
        if selected:
            recipe = self.recipe_lookup[selected[0]]
            _write(self.recipe_reader, recipe_text(recipe, recipe.key in self.game.town.discovered_recipes, self.sites))

    def _build_lore(self, title, entries):
        page = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(page, text=title)
        ttk.Label(page, text="Bundled notes work offline. References open only when you choose them.").pack(anchor="w", pady=(0, 8))
        panes = ttk.Panedwindow(page, orient="horizontal")
        panes.pack(fill="both", expand=True)
        table, tree = _table(panes, (("entry", "Entry", 240),))
        detail = ttk.Frame(panes)
        reader_frame, reader = _reader(detail)
        source_frame, source_tree = _table(detail, (("source", "Primary references", 400),), height=3)
        source_button = tk.Button(detail, text="Open selected reference", cursor="hand2", padx=10, pady=5)
        source_button.pack(side="bottom", anchor="e", pady=(7, 0))
        source_frame.pack(side="bottom", fill="x", pady=(8, 0))
        reader_frame.pack(fill="both", expand=True)
        panes.add(table, weight=2)
        panes.add(detail, weight=4)
        lookup = {entry.key: entry for entry in entries}
        sources = {}
        for entry in entries:
            tree.insert("", "end", iid=entry.key, values=(entry.title,))

        def select(event=None):
            selection = tree.selection()
            if not selection:
                return
            entry = lookup[selection[0]]
            _write(reader, f"{entry.title}\n\n{entry.body}\n\nAbout the game\n{GAME_MAP_NOTE}")
            source_tree.delete(*source_tree.get_children())
            sources.clear()
            for index, source in enumerate(entry.sources):
                key = str(index)
                sources[key] = source
                source_tree.insert("", "end", iid=key, values=(source.title,))
            if sources:
                source_tree.selection_set(next(iter(sources)))
            source_button.configure(state="normal" if sources else "disabled")

        def open_reference(event=None):
            selection = source_tree.selection()
            if selection and selection[0] in sources:
                url = sources[selection[0]].url
                if url.startswith(("https://", "http://")):
                    try:
                        webbrowser.open(url, new=2)
                    except (webbrowser.Error, OSError):
                        _write(reader, reader.get("1.0", "end-1c")+f"\n\nReference address: {url}")

        tree.bind("<<TreeviewSelect>>", select)
        source_button.configure(command=open_reference)
        source_tree.bind("<Return>", open_reference)
        if entries:
            tree.selection_set(entries[0].key)
            tree.focus(entries[0].key)
            select()
        self.lore_views.append((tree, reader, source_tree, source_button))

    def _build_markets(self):
        page = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(page, text="Markets")
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 4))
        self.market_status = ttk.Label(bar, font=("Segoe UI", 11, "bold"))
        self.market_status.pack(side="left")
        ttk.Button(bar, text="Refresh now", command=self.refresh).pack(side="right")
        self.market_event = ttk.Label(page, wraplength=900)
        self.market_event.pack(anchor="w", fill="x", pady=(0, 7))
        self.market_note = ttk.Label(page, text="Stock and orders are yours. Base buyers are counted once per product; tourists belong to local shops.",
                                     wraplength=900)
        self.market_note.pack(anchor="w", fill="x", pady=(0, 7))
        panes = ttk.Panedwindow(page, orient="vertical")
        panes.pack(fill="both", expand=True)
        table, self.market_tree = _table(panes, (
            ("product", "Product / service", 180), ("quote", "Price", 65), ("stock", "Your stock", 75),
            ("orders", "Your orders", 80), ("sold", "Sold today", 75), ("ordinary", "Base buyers/jobs", 115),
            ("tourists", "Tourists", 65), ("revenue", "Revenue today", 100)), height=7)
        reader_frame, self.market_reader = _reader(panes)
        panes.add(table, weight=3)
        panes.add(reader_frame, weight=2)
        panes.bind("<Configure>", lambda event: panes.sashpos(0, round(event.height*.58)))
        self.market_tree.bind("<<TreeviewSelect>>", lambda event: self._select_market())

    def _select_market(self):
        selected = self.market_tree.selection()
        if self.snapshot is not None and selected:
            row = next((row for row in self.snapshot.rows if row.key == selected[0]), None)
            if row is not None:
                _write(self.market_reader, market_text(row, self.snapshot))

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        discovered = tuple(self.game.town.discovered_recipes)
        if discovered != self.last_discovered:
            for recipe in self.recipes:
                values = (recipe.title, "Recorded" if recipe.key in discovered else "Undiscovered")
                tags = () if recipe.key in discovered else ("locked",)
                if self.recipe_tree.exists(recipe.key):
                    self.recipe_tree.item(recipe.key, values=values, tags=tags)
                else:
                    self.recipe_tree.insert("", "end", iid=recipe.key, values=values, tags=tags)
            self.recipe_progress.configure(text=f"Recorded recipes: {sum(recipe.key in discovered for recipe in self.recipes)} / {len(self.recipes)}")
            if not self.recipe_tree.selection() and self.recipes:
                first = next((recipe for recipe in self.recipes if recipe.key in discovered), self.recipes[0])
                self.recipe_tree.selection_set(first.key)
                self.recipe_tree.focus(first.key)
            self.last_discovered = discovered
            self._select_recipe()
        self.snapshot = market_snapshot(self.game.town, trades=self.trades, industries=self.industries, sites=self.sites)
        minutes, seconds = divmod(self.snapshot.seconds_to_reset, 60)
        self.market_status.configure(text=f"Day {self.snapshot.day} · New customers in {minutes}:{seconds:02}")
        event = self.snapshot.event_title or "No special market event"
        if self.snapshot.event_detail:
            event += f" · {self.snapshot.event_detail}"
        self.market_event.configure(text=event)
        for row in self.snapshot.rows:
            values = market_values(row)
            if self.market_tree.exists(row.key):
                self.market_tree.item(row.key, values=values)
            else:
                self.market_tree.insert("", "end", iid=row.key, values=values)
        if not self.market_tree.selection() and self.snapshot.rows:
            self.market_tree.selection_set(self.snapshot.rows[0].key)
            self.market_tree.focus(self.snapshot.rows[0].key)
        self._select_market()
        self.timer = self.panel.after(1000, self.refresh)

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

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-72)
            self.market_event.configure(wraplength=width)
            self.market_note.configure(wraplength=width)

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


def open_journal(game, trades, industries, sites):
    if getattr(game, "profile_window", None) is not None:
        return None
    return JournalPanel(game, trades, industries, sites).panel
