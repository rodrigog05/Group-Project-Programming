"""Nova SBE's in-game research branches and advanced fabrication workshop."""
import math
import tkinter as tk
from tkinter import ttk

from contracts import research_cost
from innovation import (BRANCH_BY_KEY, RECIPE_BY_KEY, RESEARCH_BRANCHES,
                        TIER3_RECIPES, next_research, research_level, research_quote, tax_rate)


BG, PANEL, TEXT, MUTED, GOLD = "#142c36", "#203f4b", "#f5efd9", "#c8d6d5", "#e2bd68"


def quantity_value(value):
    """Accept bounded, positive whole products rather than fractional batches."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 6 or not value.isascii() or not value.isdecimal():
        return None
    quantity = int(value)
    return quantity if quantity > 0 else None


def duration_text(seconds):
    """Round remaining work up so unfinished projects never display as ready."""
    seconds = max(0, math.ceil(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds:02}s" if minutes else f"{seconds}s"


def ingredient_owned(town, ingredient):
    if ingredient.source == "innovation":
        return town.innovation["goods"][ingredient.index]
    value = getattr(town, ingredient.source)
    return value if ingredient.index is None else value[ingredient.index]


def project_text(town):
    project = town.innovation["project"]
    if project is None:
        return "No active project · Choose a branch to begin your next upgrade."
    branch = BRANCH_BY_KEY[project["branch"]]
    base = branch.levels[project["level"]-1].cost
    return (f'{branch.name} · Level {project["level"]} researching · '
            f'{duration_text(project["remaining"])} remaining · '
            f'${project.get("paid_cost", base):,} already paid')


def level_effect(branch_key, level):
    if branch_key == "green_energy":
        return f"Daily profit tax reduced by {level.tax_discount} percentage points in total"
    names = [RECIPE_BY_KEY[key].product for key in level.unlocks]
    return "Unlocks " + ", ".join(names)


def branch_text(town, branch):
    completed = research_level(town, branch.key)
    lines = [f"{branch.name} · Level {completed}/{len(branch.levels)}", "",
             branch.description, ""]
    if branch.key == "green_energy":
        lines.extend((f"Your current daily profit tax: {tax_rate(town)}%.",
                      "Tax applies only to positive daily net profit. This upgrade changes the tax rate; "
                      "it does not refund taxes already paid.", ""))
    else:
        lines.extend(("Research unlocks tier-3 products in the Advanced Workshop at this campus. "
                      "Bring the listed materials here to fabricate and sell them.", ""))
    project = town.innovation["project"]
    grant = research_cost(town, 100) < 100
    if grant:
        lines.extend(("Hotel research grant: 10% off new research projects. "
                      "Existing paid projects keep their original payment.", ""))
    for level in branch.levels:
        if level.level <= completed:
            state = "COMPLETE"
        elif project and project["branch"] == branch.key and project["level"] == level.level:
            state = f'RESEARCHING · {duration_text(project["remaining"])} remaining'
        elif level.level == completed + 1:
            state = "NEXT LEVEL"
        else:
            state = f"Requires level {level.level-1}"
        cost_text = f"Cost ${level.cost:,}"
        if grant:
            if project and project["branch"] == branch.key and project["level"] == level.level:
                cost_text = f"Paid ${project.get('paid_cost', level.cost):,} · Base cost ${level.cost:,}"
            elif level.level <= completed:
                cost_text = f"Base cost ${level.cost:,}"
            else:
                cost_text = f"Cost ${research_cost(town, level.cost):,} (base ${level.cost:,}; 10% grant)"
        lines.extend((f"Level {level.level} · {state}",
                      f"  {cost_text} · {duration_text(level.seconds)} of focused play",
                      f"  {level_effect(branch.key, level)}", ""))
    lines.append("One research project runs at a time. Pay once when starting. Research continues "
                 "while this menu is open and the game has focus. Levels and remaining time save "
                 "with your game; closing or unfocusing the game pauses research.")
    return "\n".join(lines)


def branch_values(town, branch):
    completed = research_level(town, branch.key)
    upgrade = next_research(town, branch.key)
    project = town.innovation["project"]
    if project and project["branch"] == branch.key:
        state = f'Researching {duration_text(project["remaining"])}'
    elif upgrade is None:
        state = "All levels complete"
    elif project:
        state = "Lab occupied"
    else:
        state = "Ready to research"
    if project and project["branch"] == branch.key:
        cost = f"Paid ${project.get('paid_cost', upgrade.cost):,}"
    else:
        cost = f"${research_quote(town, branch.key):,}" if upgrade else "—"
    return (branch.name, f"{completed}/{len(branch.levels)}",
            cost,
            duration_text(upgrade.seconds) if upgrade else "—", state)


def recipe_values(town, recipe):
    state = town.innovation
    unlocked = research_level(town, "metallurgy") >= recipe.level
    order = state["orders"][recipe.key]
    if order is None:
        work = "—"
    elif order["remaining"] > 0:
        work = f'{order["quantity"]} · {duration_text(order["remaining"])}'
    else:
        work = f'{order["quantity"]} ready'
    return (recipe.product, "Unlocked" if unlocked else f"Metallurgy {recipe.level}",
            state["goods"][recipe.key], work,
            state["demand"][recipe.key] if unlocked else "—",
            f'${state["prices"][recipe.key]:,}' if unlocked else "—")


def fabrication_preview(town, recipe, quantity):
    if quantity is None:
        return "Enter a positive whole number of products."
    inputs = ", ".join(f"{part.quantity*quantity} {part.label}" for part in recipe.ingredients)
    return (f"Make {quantity}: {inputs} · {duration_text(recipe.seconds)} per batch · "
            f"Reserves {quantity} cargo spaces")


def recipe_text(town, recipe):
    state = town.innovation
    unlocked = research_level(town, "metallurgy") >= recipe.level
    lines = [recipe.product, "",
             "UNLOCKED" if unlocked else f"LOCKED · Complete Advanced Metallurgy level {recipe.level}",
             "", "Materials for each product:"]
    lines.extend(f"  {part.quantity} {part.label} · You carry {ingredient_owned(town, part)}"
                 for part in recipe.ingredients)
    lines.extend(("", f"Fabrication time: {duration_text(recipe.seconds)} per batch.",
                  f'Stock in your cargo: {state["goods"][recipe.key]}.'))
    order = state["orders"][recipe.key]
    if order:
        work = (f'{duration_text(order["remaining"])} remaining' if order["remaining"] > 0
                else "ready to collect")
        lines.append(f'Current batch: {order["quantity"]} · {work}.')
    else:
        lines.append("No batch in progress for this product.")
    if unlocked:
        lines.extend((f'Today\'s selling price: ${state["prices"][recipe.key]:,} per product.',
                      f'Buyers remaining today: {state["demand"][recipe.key]}.',
                      f'Sold today: {state["sales_today"][recipe.key]} · '
                      f'Revenue today: ${state["revenue_today"][recipe.key]:,}.'))
    lines.extend(("", "Fabricate, collect and sell here at Nova SBE · Carcavelos. "
                  "You can run one batch of each product at the same time. "
                  "Inputs leave your cargo when fabrication starts; output cargo spaces are reserved. "
                  "Collected intermediate products can be used in higher-level recipes.", "",
                  "Collect and sell use the entered quantity, up to the available stock, cargo room "
                  "or buyers. Buyers and prices reset each five-minute game day. "
                  "Research and workshop progress save with the game; there is no offline fabrication."))
    return "\n".join(lines)


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


class ResearchPanel:
    def __init__(self, game):
        self.game, self.root = game, game.root
        self.closed, self.timer = False, None
        self.observed_project = None
        game.keys.clear()
        self.panel = panel = tk.Toplevel(self.root)
        game.profile_window = panel
        panel.research_controller = self
        panel.title("Foundry Town · Nova SBE · Carcavelos")
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
        tk.Label(body, text="NOVA SBE · CARCAVELOS", bg=BG, fg=GOLD,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.heading = tk.Label(body, text="INOVAÇÃO · Research today. Build the city's future.",
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
        self.footer_note = tk.Label(footer, text="Progress runs while focused · Escape closes",
                                    bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left")
        self.footer_note.pack(side="left", fill="x", expand=True)
        style = ttk.Style(panel)
        style.configure("Research.Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Research.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self._build_research()
        self._build_workshop()
        panel.bind("<Escape>", self.close)
        panel.bind("<Destroy>", self._destroyed)
        panel.bind("<Configure>", self._resized)
        panel.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        panel.grab_set()
        self.branch_tree.focus_set()

    def _table(self, page, columns, height):
        frame = ttk.Frame(page)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=tuple(col[0] for col in columns), show="headings",
                            selectmode="browse", height=height, style="Research.Treeview")
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=width, stretch=name == columns[0][0],
                         anchor="w" if name == columns[0][0] else "e")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    def _build_research(self):
        page = ttk.Frame(self.notebook, padding=7)
        self.notebook.add(page, text="Research branches")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        self.branch_tree = self._table(page, (("branch", "Research branch", 180),
            ("level", "Level", 45), ("cost", "Next cost", 75), ("time", "Next time", 75),
            ("state", "Status", 160)), 2)
        self.branch_tree.bind("<<TreeviewSelect>>", lambda event: self._select_branch())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        self.research_button = ttk.Button(controls, text="Start selected research", command=self._research)
        self.research_button.pack(side="left", padx=(0, 10))
        self.research_status = ttk.Label(controls, text="Select a branch to review its levels.",
                                        anchor="w", justify="left")
        self.research_status.pack(side="left", fill="x", expand=True)
        reader_frame, self.branch_reader = _reader(page)
        reader_frame.grid(row=2, column=0, sticky="nsew")

    def _build_workshop(self):
        page = ttk.Frame(self.notebook, padding=7)
        self.notebook.add(page, text="Advanced Workshop")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        self.recipe_tree = self._table(page, (("product", "Tier-3 product", 190),
            ("unlock", "Access", 110), ("stock", "Cargo", 50), ("order", "Batch", 110),
            ("buyers", "Buyers", 55), ("price", "Sell $", 65)), 3)
        self.recipe_tree.bind("<<TreeviewSelect>>", lambda event: self._select_recipe())
        controls = ttk.Frame(page, padding=(0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        actions = ttk.Frame(controls)
        actions.grid(row=0, column=0, sticky="w")
        ttk.Label(actions, text="Quantity").pack(side="left", padx=(0, 5))
        self.quantity = tk.StringVar(self.panel, "1")
        self.quantity_entry = ttk.Spinbox(actions, from_=1, to=999999,
                                         textvariable=self.quantity, width=7)
        self.quantity_entry.pack(side="left", padx=(0, 10))
        self.fabricate_button = ttk.Button(actions, text="Fabricate", command=lambda: self._work("make"))
        self.fabricate_button.pack(side="left", padx=(0, 7))
        self.collect_button = ttk.Button(actions, text="Collect", command=lambda: self._work("collect"))
        self.collect_button.pack(side="left", padx=(0, 7))
        self.sell_button = ttk.Button(actions, text="Sell here", command=lambda: self._work("sell"))
        self.sell_button.pack(side="left")
        self.preview = ttk.Label(controls, anchor="w", justify="left")
        self.preview.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.workshop_status = ttk.Label(controls, text="Unlock recipes with Advanced Metallurgy research.",
                                        anchor="w", justify="left")
        self.workshop_status.grid(row=2, column=0, sticky="ew", pady=(3, 0))
        reader_frame, self.recipe_reader = _reader(page)
        reader_frame.grid(row=2, column=0, sticky="nsew")
        self.quantity.trace_add("write", lambda *args: self._select_recipe())

    def _selected_branch(self):
        selected = self.branch_tree.selection()
        return BRANCH_BY_KEY.get(selected[0]) if selected else None

    def _selected_recipe(self):
        selected = self.recipe_tree.selection()
        return RECIPE_BY_KEY.get(selected[0]) if selected else None

    def _select_branch(self):
        branch = self._selected_branch()
        if branch is None:
            return
        town = self.game.town
        _write(self.branch_reader, branch_text(town, branch))
        upgrade = next_research(town, branch.key)
        available = upgrade is not None and town.innovation["project"] is None
        project = town.innovation["project"]
        if project and project["branch"] == branch.key:
            button_text = f"Researching · ${project.get('paid_cost', upgrade.cost):,} paid"
        else:
            button_text = (f"Research level {upgrade.level} · ${research_quote(town, branch.key):,}"
                           if upgrade else "Branch complete")
        self.research_button.configure(state="normal" if available else "disabled",
                                       text=button_text)

    def _select_recipe(self):
        recipe = self._selected_recipe()
        if recipe is None:
            return
        town = self.game.town
        _write(self.recipe_reader, recipe_text(town, recipe))
        self.preview.configure(text=fabrication_preview(town, recipe, quantity_value(self.quantity.get())))
        unlocked = research_level(town, "metallurgy") >= recipe.level
        order = town.innovation["orders"][recipe.key]
        self.fabricate_button.configure(state="normal" if unlocked and order is None else "disabled")
        self.collect_button.configure(state="normal" if order and order["remaining"] <= 0 else "disabled")
        can_sell = unlocked and town.innovation["goods"][recipe.key] > 0 and town.innovation["demand"][recipe.key] > 0
        self.sell_button.configure(state="normal" if can_sell else "disabled")

    def _sync_game(self):
        sync = getattr(self.game, "sync_hud", None)
        if sync is not None:
            sync()

    def _research(self):
        branch = self._selected_branch()
        if branch is None:
            self.research_status.configure(text="Select a research branch first.")
        else:
            self.game.town.start_research(branch.key)
            self.research_status.configure(text=self.game.town.message)
            self._sync_game()
            self.refresh()
        return "break"

    def _work(self, action):
        recipe = self._selected_recipe()
        quantity = quantity_value(self.quantity.get())
        if recipe is None:
            self.workshop_status.configure(text="Select a product first.")
        elif quantity is None:
            self.workshop_status.configure(text="Enter a positive whole number, such as 1 or 5.")
        else:
            actions = {"make": self.game.town.start_fabrication,
                       "collect": self.game.town.collect_research_products,
                       "sell": self.game.town.sell_research_products}
            actions[action](recipe.key, quantity)
            self.workshop_status.configure(text=self.game.town.message)
            self._sync_game()
            self.refresh()
        return "break"

    def refresh(self):
        if self.closed:
            return
        if self.timer is not None:
            self.panel.after_cancel(self.timer)
            self.timer = None
        town = self.game.town
        project = town.innovation["project"]
        current_project = (project["branch"], project["level"]) if project else None
        if self.observed_project and current_project != self.observed_project:
            branch_key, level = self.observed_project
            if research_level(town, branch_key) >= level:
                self.research_status.configure(text=f"{BRANCH_BY_KEY[branch_key].name} level {level} complete.")
        self.observed_project = current_project
        self.summary.configure(text=f'Cash ${town.cash:,} · Profit tax {tax_rate(town)}% · '
            f'Research investment ${town.innovation["research_spent"]:,}\n{project_text(town)}')
        for branch in RESEARCH_BRANCHES:
            values = branch_values(town, branch)
            if self.branch_tree.exists(branch.key):
                if tuple(self.branch_tree.item(branch.key, "values")) != tuple(map(str, values)):
                    self.branch_tree.item(branch.key, values=values)
            else:
                self.branch_tree.insert("", "end", iid=branch.key, values=values)
        for recipe in TIER3_RECIPES:
            values = recipe_values(town, recipe)
            if self.recipe_tree.exists(recipe.key):
                if tuple(self.recipe_tree.item(recipe.key, "values")) != tuple(map(str, values)):
                    self.recipe_tree.item(recipe.key, values=values)
            else:
                self.recipe_tree.insert("", "end", iid=recipe.key, values=values)
        if not self.branch_tree.selection():
            self.branch_tree.selection_set(RESEARCH_BRANCHES[0].key)
            self.branch_tree.focus(RESEARCH_BRANCHES[0].key)
        if not self.recipe_tree.selection():
            self.recipe_tree.selection_set(TIER3_RECIPES[0].key)
            self.recipe_tree.focus(TIER3_RECIPES[0].key)
        self._select_branch()
        self._select_recipe()
        self.timer = self.panel.after(1000, self.refresh)

    def _resized(self, event):
        if event.widget is self.panel:
            width = max(300, event.width-62)
            for label in (self.heading, self.summary, self.preview, self.workshop_status):
                label.configure(wraplength=width)
            self.research_status.configure(wraplength=max(170, event.width-300))
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


def open_research(game):
    if getattr(game, "profile_window", None) is not None:
        return None
    return ResearchPanel(game).panel
