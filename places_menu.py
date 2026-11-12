"""A readable directory of businesses and sights, with destination guidance."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from lisbon_landmarks import LANDMARKS
from wayfinding import site_guide
from tourism import monument_description, tourism_description
from tram import TRAM_FARE, TRAM_STOPS


DIRECTORY_TABS = (
    ("buy", "1  Buy materials"),
    ("make", "2  Make products"),
    ("sell", "3  Sell products"),
    ("services", "+  Services"),
    ("landmarks", "◆  Landmarks"),
)


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    detail: str
    neighborhood: str
    instruction: str
    x: float
    y: float
    marker: str
    color: str

    @property
    def destination(self):
        return self.x, self.y


def neighborhood_for(x, y):
    """Describe this game's compact map, rather than claiming scale geography."""
    if y >= 900:
        if x < 1200:
            return "Almada · Tejo"
        if y >= 1380:
            return "Palmela"
        return "Seixal" if x >= 1950 else "Cacilhas"
    for edge, name in ((238, "Belém"), (478, "Alcântara"), (718, "Baixa · Chiado"),
                       (958, "Alfama · Graça"), (1220, "Oriente"), (1775, "Marvila")):
        if x < edge:
            return name
    return "Parque das Nações"


def destination_for_landmark(landmark):
    left, top, right, bottom = landmark.bounds
    if landmark.kind == "tower":
        # The tower is in the river; guide walkers to the nearby safe promenade.
        return 140, 700
    if landmark.kind == "square":
        return (left+right)/2, (top+bottom)/2
    return (left+right)/2, bottom+18


def directory_entries(sites, landmarks=LANDMARKS):
    """Return directory rows from current site positions; no Tk window is needed."""
    sites = tuple(sites)
    rows = {key: [] for key, title in DIRECTORY_TABS}
    for site in sites:
        guide = site_guide(site)
        if guide.stage == "residential":
            continue
        door_x, door_y = site.door
        instruction = " ".join(part for part in (guide.instruction, tourism_description(site)) if part)
        entry = DirectoryEntry(site.name, guide.detail, neighborhood_for(site.x, site.y),
                               instruction, door_x, door_y+18, guide.marker, guide.color)
        categories = ("make", "sell") if guide.stage == "special" else (guide.stage,)
        for category in categories:
            rows[category].append(entry)
    descriptions = {
        "monastery": ("Manueline monastery · Belém", "Visit the limestone cloister and church façade from the public approach."),
        "castle": ("Castle walls and towers · Alfama", "Visit the hilltop castle's public approach and look for the stone towers."),
        "square": ("Riverside square and arcades", "Walk into the open central courtyard of Praça do Comércio, beside its yellow arcades and statue."),
        "tower": ("Historic riverside tower · Belém", "The tower stands in the Tejo. Guidance leads to the safe north-bank promenade beside it."),
    }
    for landmark in landmarks:
        detail, instruction = descriptions.get(landmark.kind, ("Lisbon landmark", "Explore this Lisbon landmark."))
        x, y = destination_for_landmark(landmark)
        left, top, right, bottom = landmark.bounds
        instruction = " ".join(part for part in (instruction, monument_description(landmark, sites)) if part)
        rows["landmarks"].append(DirectoryEntry(landmark.name, detail, neighborhood_for(left, top),
                                                 instruction, x, y, "◆", "#d5bf76"))
    for stop in TRAM_STOPS:
        rows["services"].append(DirectoryEntry(
            f"Tram · {stop.name}", f"${TRAM_FARE} express travel", stop.name,
            f"Walk to the yellow TRAM platform and press E. Pay ${TRAM_FARE} to travel to any other north-bank stop. "
            "Your cargo and vehicle remain available after the trip.", stop.x, stop.y, "T", "#936f22"))
    return {key: tuple(sorted(entries, key=lambda entry: entry.name.casefold())) for key, entries in rows.items()}


def open_places(game, sites):
    """Open a modal directory, sharing the game's existing pause-window slot."""
    if getattr(game, "profile_window", None) is not None:
        return None
    root = game.root
    game.keys.clear()
    panel = tk.Toplevel(root)
    game.profile_window = panel
    panel.title("Foundry Town · Places & Production")
    panel.transient(root)
    panel.configure(bg="#142c36")
    panel.resizable(True, True)
    panel.minsize(680, 440)
    available_width = root.winfo_width() if root.winfo_width() > 100 else root.winfo_screenwidth()
    available_height = root.winfo_height() if root.winfo_height() > 100 else root.winfo_screenheight()
    width = min(1080, max(680, available_width-100))
    height = min(700, max(480, available_height-100))
    x = root.winfo_rootx()+max(0, (available_width-width)//2)
    y = root.winfo_rooty()+max(0, (available_height-height)//2)
    panel.geometry(f"{width}x{height}+{x}+{y}")
    body = tk.Frame(panel, bg="#142c36", padx=20, pady=16)
    body.pack(fill="both", expand=True)
    tk.Label(body, text="PLACES & PRODUCTION", bg="#142c36", fg="#f5efd9",
             font=("Segoe UI", 19, "bold")).pack(anchor="w")
    steps = tk.Frame(body, bg="#142c36")
    steps.pack(fill="x", pady=(8, 4))
    for text, color in (("1  BUY MATERIALS", "#96620c"), ("2  MAKE PRODUCTS", "#23679b"),
                        ("3  SELL PRODUCTS", "#167253")):
        tk.Label(steps, text=text, bg=color, fg="white", padx=12, pady=6,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 8))
    tk.Label(body, text="Example: Goldenfield Farm → Sunrise Bakery → Daily Bread Market. Buy Wheat, make Bread, then sell it.",
             bg="#142c36", fg="#e1d8be", justify="left", wraplength=width-50,
             font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 12))
    style = ttk.Style(panel)
    style.configure("Places.Treeview", rowheight=29, font=("Segoe UI", 10))
    style.configure("Places.Treeview.Heading", font=("Segoe UI", 10, "bold"))
    notebook = ttk.Notebook(body)
    rows = directory_entries(sites)
    trees = []
    for key, title in DIRECTORY_TABS:
        page = ttk.Frame(notebook, padding=8)
        notebook.add(page, text=title)
        tree = ttk.Treeview(page, columns=("name", "purpose", "area"), show="headings",
                            height=8, selectmode="browse", style="Places.Treeview")
        for column, title_text, col_width, minimum in (("name", "Place", 290, 180),
                                                       ("purpose", "What happens here", 390, 180),
                                                       ("area", "Neighborhood", 195, 135)):
            tree.heading(column, text=title_text)
            tree.column(column, width=col_width, minwidth=minimum, stretch=True)
        vertical = ttk.Scrollbar(page, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(page, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        lookup = {}
        for index, entry in enumerate(rows[key]):
            item = tree.insert("", "end", iid=str(index), values=(f"{entry.marker} · {entry.name}", entry.detail, entry.neighborhood))
            lookup[item] = entry
        if lookup:
            first = next(iter(lookup))
            tree.selection_set(first)
            tree.focus(first)
        trees.append((tree, lookup))
    selected_text = tk.StringVar(panel)
    explanation = tk.Label(body, textvariable=selected_text, bg="#203f4b", fg="#fff2cb",
                           font=("Segoe UI", 11), padx=12, pady=10, justify="left",
                           anchor="w", wraplength=width-70, height=4)
    controls = tk.Frame(body, bg="#142c36")
    # Reserve the controls and instructions first, so a smaller window only
    # reduces the table's height and never hides its action buttons.
    controls.pack(side="bottom", fill="x")
    explanation.pack(side="bottom", fill="x", pady=(10, 8))
    notebook.pack(fill="both", expand=True)

    def current_entry():
        index = notebook.index(notebook.select())
        tree, lookup = trees[index]
        selection = tree.selection()
        return lookup.get(selection[0]) if selection else None

    def clear_pause(event=None):
        if event is None or event.widget is panel:
            if game.profile_window is panel:
                game.profile_window = None
            game.keys.clear()

    def close(event=None):
        clear_pause()
        try:
            panel.grab_release()
            panel.destroy()
            if root.winfo_exists():
                root.focus_set()
        except tk.TclError:
            pass
        return "break"

    def guide(event=None):
        entry = current_entry()
        if entry is not None:
            game.world_view.set_destination(entry.name, entry.x, entry.y)
            return close()
        return "break"

    def update_selection(event=None):
        entry = current_entry()
        selected_text.set(f"{entry.name}\n{entry.instruction}" if entry else "No places in this category.")
        go.configure(state="normal" if entry else "disabled")

    def double_click(event):
        if event.widget.identify_region(event.x, event.y) in ("tree", "cell"):
            return guide()

    go = tk.Button(controls, text="Guide me here", command=guide, bg="#e2bd68", fg="#172c33",
                   activebackground="#f0d591", relief="flat", padx=20, pady=8,
                   cursor="hand2", font=("Segoe UI", 11, "bold"))
    go.pack(side="right")
    tk.Button(controls, text="Close", command=close, padx=16, pady=8).pack(side="right", padx=10)
    tk.Label(controls, text="Choose a place, then use Guide me here or press Enter.",
             bg="#142c36", fg="#d7dfd9", font=("Segoe UI", 9)).pack(side="left")
    for tree, lookup in trees:
        tree.bind("<<TreeviewSelect>>", update_selection)
        tree.bind("<Return>", guide)
        tree.bind("<Double-1>", double_click)
    notebook.bind("<<NotebookTabChanged>>", update_selection)
    panel.bind("<Escape>", close)
    panel.bind("<Destroy>", clear_pause)
    panel.bind("<Configure>", lambda event: explanation.configure(wraplength=max(400, panel.winfo_width()-70))
               if event.widget is panel else None)
    panel.protocol("WM_DELETE_WINDOW", close)
    update_selection()
    panel.grab_set()
    trees[0][0].focus_set()
    return panel
