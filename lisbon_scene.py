"""Retained vector scenery for a compact, playable interpretation of Lisbon."""
import math
import random

RIVER_TOP, RIVER_BOTTOM = 718, 900
MAP_BOTTOM = 1080
BRIDGE_TOLL = 3


def bridge_center(y, eastern=False):
    return 1055 - 0.32 * (y - RIVER_TOP) if eastern else 300


def bridge_at(x, y, radius=10):
    for eastern, name in ((False, "25 de Abril"), (True, "Vasco da Gama")):
        if abs(x-bridge_center(y, eastern)) <= (27 if eastern else 31)-radius:
            return name
    return None


def walkable_terrain(x, y, radius=10):
    if RIVER_TOP - radius < y < RIVER_BOTTOM + radius:
        return bridge_at(x, y, radius) is not None
    return True


class LisbonScene:
    def __init__(self, game, sites, draw=True):
        self.game, self.c = game, game.canvas
        self.sites = sites
        self.tram_position = 0.0
        if draw:
            self.draw()

    def rect(self, x1, y1, x2, y2, color, **kwargs):
        return self.c.create_rectangle(x1, y1, x2, y2, fill=color, width=0, tags="city", **kwargs)

    def poly(self, points, color, **kwargs):
        return self.c.create_polygon(*points, fill=color, width=0, tags="city", **kwargs)

    def line(self, points, color, width=1, **kwargs):
        return self.c.create_line(*points, fill=color, width=width, tags="city", **kwargs)

    def text(self, x, y, value, size=10, color="#304b54", bold=False, anchor="w"):
        self.game.label(x, y, value, size, color, bold, anchor=anchor)

    def tree(self, x, y, size=12):
        self.c.create_oval(x-size, y-3, x+size+7, y+10, fill="#c1bc9c", outline="", tags="city")
        self.rect(x-2, y-8, x+2, y+7, "#8e7756")
        for dx, dy, radius, color in ((0, -9, size, "#55795e"), (-4, -14, size*.8, "#729271"),
                                      (4, -17, size*.65, "#8fa681")):
            self.c.create_oval(x+dx-radius, y+dy-radius, x+dx+radius, y+dy+radius,
                               fill=color, outline="", tags="city")

    def road(self, points, width=42):
        self.line(points, "#b4ac98", width+10, capstyle="round", joinstyle="round")
        self.line(points, "#747a77", width, capstyle="round", joinstyle="round")
        self.line(points, "#e4d8b9", 1, dash=(9, 14))

    def draw(self):
        self.rect(0, 104, 1200, MAP_BOTTOM, "#dfd5bd")
        # Subtle sunlit paving and green hills, rather than a square grass grid.
        for y in range(105, 716, 16):
            self.line((0, y, 1200, y), "#d9cfb7")
        self.poly((0, 105, 440, 105, 380, 151, 0, 167), "#c4c6a4", smooth=True)
        self.poly((680, 104, 1030, 104, 1120, 146, 720, 157), "#c0c4a4", smooth=True)
        for x in (238, 478, 718, 958):
            self.road((x, 140, x, 653), 30)
        for y in (301, 486):
            self.road((0, y, 1200, y), 39)
        self.road((0, 660, 1200, 660), 35)
        # Baixa's broad calçada waterfront, with wave patterns.
        self.rect(0, 672, 1200, RIVER_TOP, "#eee5cf")
        for x in range(-15, 1220, 52):
            self.line((x, 707, x+13, 701, x+26, 707, x+39, 713, x+52, 707), "#a5a294", 2, smooth=True)
        for name, x in (("BELÉM", 28), ("ALCÂNTARA", 268), ("BAIXA · CHIADO", 508),
                        ("ALFAMA · GRAÇA", 748), ("ORIENTE", 988)):
            self.text(x, 133, name, 10, "#6e7767", True)
        for site in self.sites:
            if site.y < RIVER_TOP:
                self.building(site)
        for x, y in ((224, 171), (462, 168), (704, 164), (944, 167), (1180, 164),
                     (218, 366), (461, 365), (702, 367), (939, 365),
                     (221, 553), (460, 553), (702, 552), (941, 552)):
            self.tree(x, y, 11)
        self.river()
        self.south_bank()
        self.suspension_bridge()
        self.cable_bridge()
        self.tramway()
        self.text(18, 707, "RIBEIRA DAS NAUS", 7, "#738379", True)
        self.text(687, 878, "RIO TEJO", 23, "#d5edef", True, anchor="center")
        self.text(687, 901, "LISBOA  /  ALMADA", 8, "#587c81", anchor="center")
        self.text(350, 709, f"↑ LISBOA · PORTAGEM ${BRIDGE_TOLL}", 7, "#5d6d65", True)
        self.text(1090, 707, f"↑ LISBOA · ${BRIDGE_TOLL}", 7, "#5d6d65", True)

    def night_lighting(self):
        c = self.c

        def glow(x, y, radius=18, color="#f4c878"):
            c.create_oval(x-radius, y-radius*.65, x+radius, y+radius*.65,
                          fill=color, stipple="gray25", outline="", tags="night_lights")
            c.create_oval(x-radius*.55, y-radius*.4, x+radius*.55, y+radius*.4,
                          fill=color, stipple="gray50", outline="", tags="night_lights")

        for site in self.sites:
            for index, x in enumerate((site.x+22, site.x+70, site.x+118)):
                color = ("#f3d49b", "#e7b96c", "#ffe5b7")[index]
                glow(x+12, site.y+44, 23)
                c.create_rectangle(x+1, site.y+32, x+23, site.y+56, fill=color, outline="", tags="night_lights")
                c.create_line(x+12, site.y+32, x+12, site.y+56, fill="#8b795a", width=1, tags="night_lights")
            door_x, door_y = site.door
            glow(door_x, door_y+8, 21)
            c.create_oval(door_x-2, door_y-16, door_x+2, door_y-12,
                          fill="#fff1be", outline="", tags="night_lights")
        # Warm suspension-bridge lights and reflections in the Tejo.
        for x in (267, 333):
            c.create_line(x, 711, x, 924, fill="#eaa06c", width=2, tags="night_lights")
            for y in range(724, 920, 24):
                glow(x, y, 12)
                c.create_oval(x-2, y-2, x+2, y+2, fill="#ffe5a4", outline="", tags="night_lights")
        for y in (755, 860):
            c.create_line(263, y-31, 336, y-31, fill="#f5bd83", width=2, tags="night_lights")
        # The cable bridge has cool mast lighting and warm lamps along its deck.
        for y in range(723, 919, 27):
            x = bridge_center(y, True)
            for side in (-1, 1):
                lx = x+side*25
                glow(lx, y, 12, "#cce7e6")
                c.create_oval(lx-2, y-2, lx+2, y+2, fill="#eef4d9", outline="", tags="night_lights")
        for y in (761, 858):
            x = bridge_center(y, True)
            for side in (-1, 1):
                c.create_line(x+side*29, y+12, x+side*15, y-40,
                              fill="#d4edf0", width=3, tags="night_lights")
                glow(x+side*15, y-40, 17, "#bddfec")
        for x in (55, 372, 653, 920, 1144):
            glow(x, 674, 28)
            c.create_oval(x-2, 666, x+2, 670, fill="#fff0ba", outline="", tags="night_lights")
        for y in range(747, 896, 23):
            c.create_line(341, y, 360, y, fill="#d2ab69", stipple="gray25", width=2, tags="night_lights")
            x = bridge_center(y, True)-42
            c.create_line(x-14, y, x+8, y, fill="#b0d1d2", stipple="gray25", width=2, tags="night_lights")
        glow(149, 930, 32, "#c5dde0")

    def river(self):
        colors = ("#83b9bc", "#78afb6", "#6da7b0", "#629da8", "#5e98a4", "#619daa")
        for index, color in enumerate(colors):
            top = RIVER_TOP + index * (RIVER_BOTTOM-RIVER_TOP)/len(colors)
            self.rect(0, top, 1200, top+(RIVER_BOTTOM-RIVER_TOP)/len(colors)+1, color)
        self.line((0, RIVER_TOP, 1200, RIVER_TOP), "#faf0d8", 6)
        rng = random.Random(1528)
        for _ in range(80):
            x, y = rng.randrange(0, 1200), rng.randrange(RIVER_TOP+12, RIVER_BOTTOM-8)
            self.line((x, y, x+rng.randrange(8, 30), y), "#91c1c4", 1)
        # A small traditional sailing boat and a commuter ferry.
        self.poly((519, 807, 566, 807, 556, 818, 529, 818), "#f2e6c9")
        self.line((541, 770, 541, 807), "#735b46", 2)
        self.poly((538, 774, 518, 802, 538, 802), "#fff5dc")
        self.poly((545, 780, 563, 802, 545, 802), "#dfbc90")
        self.poly((1110, 822, 1170, 822, 1158, 836, 1118, 836), "#e8e8dd")
        self.rect(1122, 809, 1156, 822, "#e8e8dd")
        self.rect(1128, 813, 1151, 818, "#416372")
        self.line((1110, 838, 1089, 841), "#b2d2d0", 2)

    def south_bank(self):
        self.rect(0, RIVER_BOTTOM+2, 1200, MAP_BOTTOM, "#cfceb0")
        self.rect(0, RIVER_BOTTOM+2, 1200, RIVER_BOTTOM+9, "#f1e8ce")
        self.road((0, 1058, 1200, 1058), 24)
        self.road((300, 902, 300, 1058), 32)
        self.road((996, 902, 980, 1058), 32)
        self.text(350, 916, "ALMADA", 12, "#6c7f65", True)
        if any(site.role == "SHIPYARD" for site in self.sites):
            self.rect(458, 868, 478, 912, "#aa8b63")
            for y in range(870, 910, 7):
                self.line((459, y, 477, y), "#d2b98d", 2)
            self.poly((483, 866, 545, 866, 533, 890, 493, 890), "#9b6051")
            self.rect(495, 851, 532, 866, "#e9dfc8")
            self.rect(501, 854, 525, 861, "#5d858c")
            self.line((470, 882, 486, 875), "#d9c69d", 2)
            self.line((424, 925, 424, 856, 483, 845), "#747d72", 4)
            self.line((483, 845, 483, 864), "#747d72", 1)
            self.text(459, 924, "DOCA DE REPARAÇÕES", 6, "#657e78")
        # Cristo Rei silhouette on the south bank.
        self.rect(130, 971, 167, 982, "#b5af97")
        self.poly((137, 971, 142, 936, 156, 936, 161, 971), "#e4dbc1")
        self.rect(146, 917, 152, 944, "#f5edd6")
        self.rect(133, 923, 165, 928, "#f5edd6")
        self.c.create_oval(145, 910, 153, 919, fill="#f5edd6", outline="", tags="city")
        self.text(149, 998, "CRISTO REI", 7, "#7b826a", anchor="center")
        for x, y in ((48, 969), (78, 1011), (415, 1014), (466, 978), (1146, 960), (1112, 1025)):
            self.tree(x, y, 15)
        for site in self.sites:
            if site.y >= RIVER_BOTTOM:
                self.building(site)

    def suspension_bridge(self):
        self.line((308, 704, 308, 924), "#638b8a", 72)
        self.line((300, 697, 300, 934), "#9e5147", 69)
        self.line((300, 695, 300, 935), "#555d61", 54)
        self.line((300, 695, 300, 935), "#d8c5a6", 1, dash=(6, 8))
        for side in (267, 333):
            self.line((side, 704, side, 925), "#b05c4d", 3)
            self.line((side, 713, side, 746, side, 808, side, 867, side, 921), "#cf8b73", 3, smooth=True)
            for y in range(725, 918, 14):
                self.line((side, y, side-5 if side < 300 else side+5, y-10), "#d99a81", 1)
        for y in (755, 860):
            for x in (263, 326):
                self.rect(x, y-34, x+10, y+14, "#9d493f")
                self.rect(x+2, y-34, x+5, y+14, "#d18c74")
            self.rect(263, y-33, 336, y-27, "#a95547")
            self.line((273, y-24, 326, y+6, 273, y+6, 326, y-24), "#bc7460", 2)
        self.text(250, 803, "25 DE ABRIL", 8, "#f5dfc5", True, anchor="e")

    def cable_bridge(self):
        start, end = (1061, 698), (992, 919)
        self.line((start[0]+7, start[1]+7, end[0]+7, end[1]+7), "#638d8f", 59)
        self.line((*start, *end), "#c3c9c1", 58)
        self.line((*start, *end), "#747e7e", 45)
        self.line((*start, *end), "#eee3c5", 1, dash=(6, 9))
        for y in (761, 858):
            x = bridge_center(y, True)
            for side in (-1, 1):
                self.line((x+side*29, y+12, x+side*15, y-40), "#e0e3d5", 5)
                for spread in (-37, -22, 0, 23, 38):
                    target_y = y+spread
                    target_x = bridge_center(target_y, True)+side*26
                    self.line((x+side*15, y-39, target_x, target_y), "#d8e0d6", 1)
        self.text(1090, 775, "VASCO", 8, "#e0efdf", True)
        self.text(1090, 789, "DA GAMA", 8, "#e0efdf", True)

    def building(self, site):
        x, y, right, bottom = site.bounds
        palettes = (("#dec4a0", "#bc785b"), ("#e3c4b5", "#b87356"), ("#c7d3d0", "#ac7058"),
                    ("#e4ce95", "#b97552"))
        wall, roof = palettes[max(0, site.trade) % len(palettes)]
        if site.role == "CASINO":
            wall, roof = "#d3cabd", "#796f68"
        elif site.role == "TIER2":
            wall, roof = "#b98b73", "#5a6c71"
        elif site.role == "WAREHOUSE":
            wall, roof = "#bdd0cd", "#8b8f84"
        elif site.role == "PASTELARIA":
            wall, roof = "#f0dca6", "#b77955"
        elif site.role == "SHIPYARD":
            wall, roof = "#b8c8c5", "#5a747c"
        # Soft offset shadows, stone side wall, tiled pitched roof.
        self.poly((x+6, y+21, right+11, y+21, right+11, bottom+8, x+7, bottom+8), "#bfb69e")
        self.rect(x, y+12, right, bottom, wall)
        self.rect(right-8, y+15, right, bottom, "#afaa97")
        self.poly((x-4, y+14, x+14, y-2, right-13, y-2, right+4, y+14), roof)
        self.line((x+2, y+15, right-2, y+15), "#e9d1b0", 3)
        for tile_x in range(x+10, right-8, 13):
            self.line((tile_x, y+1, tile_x-4, y+11), "#cb9571")
        self.rect(x+10, y+20, right-14, y+24, "#eee2c8")
        # Tall shuttered windows and wrought-iron balconies.
        for window_x in (x+22, x+70, x+118):
            self.rect(window_x-3, y+29, window_x+27, y+63, "#eddfc9")
            self.rect(window_x, y+31, window_x+24, y+60, "#5f7d82")
            self.rect(window_x+2, y+33, window_x+10, y+46, "#a5c0bb")
            self.line((window_x+12, y+32, window_x+12, y+60), "#e8ddbf", 2)
            self.rect(window_x-6, y+57, window_x+30, y+61, "#777c70")
            self.line((window_x-4, y+50, window_x-4, y+59, window_x+28, y+59, window_x+28, y+50), "#4e625e")
            for bar in range(0, 28, 5):
                self.line((window_x+bar, y+51, window_x+bar, y+59), "#4e625e")
        # Azulejo band and an inviting ground-floor shopfront.
        self.rect(x+7, y+64, right-10, y+70, "#e9e3ce")
        for tile_x in range(x+10, right-12, 10):
            self.poly((tile_x, y+67, tile_x+3, y+64, tile_x+6, y+67, tile_x+3, y+70), "#628b9b")
        self.rect(x+8, y+72, right-11, bottom-4, "#314c55")
        self.text(x+15, y+81, site.name, 8, "#fff5df", True)
        roles = {"SUPPLIER": "SUPPLIES", "FACTORY": "WORKSHOP", "PUBLIC SHOP": "MARKET",
                 "TIER2": "TIER 2 · CRAFT & SELL", "CASINO": "CASINO", "GARAGE": "GARAGE", "WAREHOUSE": "STORAGE",
                 "PASTELARIA": "GASTRONOMIA · PASTÉIS", "SHIPYARD": "ESTALEIRO · REPARAÇÕES"}
        role_label = "WHEAT · EGGS (F / R)" if site.role == "SUPPLIER" and site.trade == 3 else roles[site.role]
        self.text(x+15, y+96, role_label, 6, "#d1c9a8")
        door_x, _ = site.door
        self.rect(door_x-12, bottom-13, door_x+12, bottom+1, "#98754e")
        self.rect(door_x-14, bottom+2, door_x+14, bottom+6, "#d4a45c")
        self.rect(x+3, bottom+13, right-3, bottom+32, "#ede4cf")

    def tramway(self):
        for y in (681, 691):
            self.line((25, y, 1175, y), "#7f8580", 2)
            self.line((25, y+1, 1175, y+1), "#f0e6d0")
        self.line((45, 665, 1155, 665), "#8c9387", 1)
        for x in (55, 372, 653, 920, 1144):
            self.line((x, 668, x, 698), "#737e77", 2)
            self.line((x-8, 666, x+8, 666), "#737e77", 2)
        self.create_tram()

    def create_tram(self):
        # One retained group, moved each frame instead of rebuilding the tram.
        c = self.c
        c.create_oval(-34, 692, 38, 703, fill="#b4ac92", outline="", tags="tram")
        c.create_polygon(-34, 664, -28, 655, 28, 655, 34, 664, 34, 690, 28, 696, -28, 696, -34, 690,
                         fill="#d8a32f", outline="#a47931", smooth=True, tags="tram")
        c.create_rectangle(-30, 660, 30, 665, fill="#f7e8c3", outline="", tags="tram")
        self.tram_windows = []
        for x in (-25, -10, 5, 20):
            self.tram_windows.append(c.create_rectangle(x, 668, x+10, 681, fill="#55777c", outline="#f4e7bd", tags="tram"))
        c.create_line(-30, 684, 30, 684, fill="#f4e4b4", width=2, tags="tram")
        c.create_line(-8, 655, 2, 645, 12, 655, fill="#4a5d5e", width=2, tags="tram")
        c.create_oval(-25, 690, -16, 699, fill="#3c4c4f", outline="", tags="tram")
        c.create_oval(16, 690, 25, 699, fill="#3c4c4f", outline="", tags="tram")
        self.game.label(0, 687, "TEJO", 6, "#fff5dc", True, anchor="center", tag="tram")

    def set_night(self, enabled):
        for item in self.tram_windows:
            self.c.itemconfigure(item, fill="#f2d69a" if enabled else "#55777c")

    def animate(self, elapsed):
        phase = elapsed % 40
        fraction = min(1, phase/17) if phase < 20 else max(0, 1-(phase-20)/17)
        x = 80+1040*fraction
        self.c.move("tram", (x-self.tram_position)*self.game.scale_x, 0)
        self.tram_position = x


def draw_character(canvas, profile, body_colors, hair_colors, costumes, x, y,
                   elapsed=0, moving=False, facing=1, tag="live"):
    """Smooth, shaded figure, shared by the character editor and game."""
    outfit, accessory = costumes[profile["costume"]]
    stride = math.sin(elapsed*13)*3 if moving else 0
    canvas.create_oval(x-11, y+8, x+12, y+16, fill="#7e8474", outline="", tags=tag)
    for side in (-1, 1):
        foot_y = y+10+side*stride
        canvas.create_line(x+side*4, y+2, x+side*5, foot_y, fill="#3c4d56", width=5, capstyle="round", tags=tag)
        canvas.create_oval(x+side*5-3, foot_y-1, x+side*5+4, foot_y+3, fill="#28363e", outline="", tags=tag)
    canvas.create_oval(x-10, y-10, x+10, y+8, fill=outfit, outline="#5d6f70", width=1, tags=tag)
    canvas.create_line(x-10, y-4, x-13, y+3-stride*.4, fill=outfit, width=5, capstyle="round", tags=tag)
    canvas.create_line(x+10, y-4, x+13, y+3+stride*.4, fill=outfit, width=5, capstyle="round", tags=tag)
    canvas.create_oval(x-7, y-24, x+7, y-9, fill=body_colors[profile["body"]], outline="#aa8a71", width=1, tags=tag)
    canvas.create_arc(x-8, y-26, x+8, y-8, start=0, extent=180, fill=hair_colors[profile["hair"]], outline="", tags=tag)
    canvas.create_oval(x+facing*3-1, y-17, x+facing*3+1, y-15, fill="#3b4544", outline="", tags=tag)
    canvas.create_line(x-5, y-9, x+5, y-8, fill=accessory, width=3, capstyle="round", tags=tag)
    if profile["costume"] == "Builder":
        canvas.create_arc(x-9, y-30, x+9, y-17, start=0, extent=180, fill=accessory, outline="", tags=tag)
        canvas.create_line(x-10, y-23, x+10, y-23, fill=accessory, width=3, tags=tag)
    elif profile["costume"] == "Wizard":
        canvas.create_polygon(x-9, y-24, x+2, y-42, x+8, y-24, fill=accessory, smooth=True, outline="", tags=tag)
    elif profile["costume"] in ("Explorer", "Chef"):
        canvas.create_oval(x-10, y-29, x+10, y-22, fill=accessory, outline="", tags=tag)
