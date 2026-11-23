"""Compact city buildings and Nova's classroom, drawn in Foundry Town's vector style.

Run ``python city_art.py`` to rebuild the two transparent street overlays.
The optional --presentation export uses resvg-py and Pillow to rasterize our SVG
classroom into the WebP format used by all building interiors.
"""
from html import escape
from pathlib import Path

from ferry import FERRY_FARE, FERRY_PIERS
from lisbon_scene import NORTH_AVENUE_Y, NORTH_JUNCTIONS, NORTH_QUARTERS, SCENERY_PLOTS, north_avenue_outline
from tycoon import SITES
from place_names import localize_place_names

COMPACT_ROLES = frozenset({"SUPPLIER", "FACTORY", "PUBLIC SHOP", "WAREHOUSE", "TIER2"})
CLOSED = frozenset({"Motorworks Garage", "Armazém do Seixal", "Pastéis de Belém"})


class Drawing:
    def __init__(self, width, height):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                      f'viewBox="0 0 {width} {height}">']

    def add(self, markup):
        self.parts.append(markup)

    def rect(self, x, y, w, h, fill, radius=0, stroke=None):
        edge = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"{edge}/>')

    def path(self, data, fill="none", stroke=None, width=1):
        edge = f' stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ""
        self.add(f'<path d="{data}" fill="{fill}"{edge}/>')

    def ellipse(self, x, y, rx, ry, fill):
        self.add(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}"/>')

    def text(self, x, y, value, size=8, color="#f7edda", weight="bold", anchor="middle"):
        value = localize_place_names(value)
        self.add(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Arial,sans-serif" '
                 f'font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>')

    def svg(self):
        return "".join(self.parts) + "</svg>"


def window(d, x, y, w=19, h=21, night=False, balcony=False):
    d.rect(x-2, y-2, w+4, h+4, "#eee4cb")
    d.rect(x, y, w, h, "#f3cf86" if night else "#54787c")
    d.path(f'M{x+2} {y+h-2}V{y+2}H{x+w-3}', stroke="#ffe6a5" if night else "#a6c5c0", width=2)
    d.path(f'M{x+w/2} {y}v{h}', stroke="#f2e9d5", width=1)
    if balcony:
        d.rect(x-5, y+h, w+10, 3, "#b4ad98")
        d.path(f'M{x-4} {y+h-7}H{x+w+4}V{y+h}H{x-4}Z', stroke="#46585a", width=1)
        for i in range(0, w+5, 4):
            d.path(f'M{x-2+i} {y+h-7}v7', stroke="#46585a", width=.7)


def roof(d, x, y, w, color="#a8654e"):
    d.path(f'M{x-4} {y+13}l15-13h{w-23}l16 13Z', color)
    for i in range(7, w, 9):
        d.path(f'M{x+i} {y+2}l-5 9', stroke="#d29a72", width=.8)
    d.path(f'M{x-4} {y+14}h{w+8}', stroke="#efe0be", width=2)


def sidewalk(d, x, y, night, east=False, south=False):
    # Clear just the old building and its signage. Roads, curbs and trees stay intact.
    ground = ("#546464" if night else "#c5c9a6") if south else (
        ("#5c696e" if east else "#5e696d") if night else "#dad7bf" if east else "#dfd5bd")
    if south and y < 1300:
        ground = "#586668" if night else "#cfceb0"
    if (x, y) == (1280, 530):
        # The old farm painted its entire city block green, beyond the building.
        d.rect(1245, 508, 230, 134, ground)
    d.rect(x-4, y-24, 192, 132, ground)


def planter(d, x, y, night):
    d.ellipse(x+3, y+4, 9, 3, "#535f57" if night else "#b9b59a")
    d.rect(x-4, y-2, 9, 7, "#986c51", 1)
    d.ellipse(x, y-5, 8, 6, "#456958" if night else "#78956c")
    d.ellipse(x-3, y-7, 4, 4, "#5f8062" if night else "#9cb589")


def signs(d, site, night):
    x, y = site.x, site.y
    badge, color = {"SUPPLIER": ("BUY MATERIALS", "#a67324"),
                    "FACTORY": ("MAKE PRODUCTS", "#376b88"),
                    "PUBLIC SHOP": ("SELL PRODUCTS", "#377e68"),
                    "TIER2": ("MAKE & SELL", "#72618f"),
                    "WAREHOUSE": ("STORAGE", "#65727f")}[site.role]
    d.rect(x+20, y-14, 136, 13, color, 2)
    d.path(f'M{x+24} {y-12}h128', stroke="#e8d7af", width=.7)
    d.text(x+88, y-4, badge, 8)
    d.rect(x+3, y+4, 174, 13, "#263f46" if night else "#365258", 2)
    d.text(x+90, y+13, site.name, 7.5)


def shell(d, site, wall, night, roof_color="#a8654e"):
    x, y = site.x+24, site.y+24
    d.path(f'M{x+5} {y+16}h132v66H{x+5}Z', "#4d5b57" if night else "#b9b198")
    d.rect(x, y+12, 128, 68, wall)
    d.rect(x+120, y+13, 8, 67, "#77827a" if night else "#b6a88f")
    roof(d, x, y, 128, roof_color)
    d.rect(x+2, y+76, 117, 4, "#b8ae95")
    # Every model meets the original entrance, avoiding any saved-position jump.
    d.rect(x+53, y+54, 22, 26, "#304b53")
    d.rect(x+55, y+56, 8, 21, "#c9a968" if night else "#6a9299")
    d.path(f'M{x+65} {y+70}h3', stroke="#e5ca85", width=1)
    d.rect(x+49, y+80, 30, 4, {"SUPPLIER":"#c69b4e", "FACTORY":"#4d879d",
                                            "PUBLIC SHOP":"#4e9679", "WAREHOUSE":"#8c829d", "TIER2":"#8b70a8"}[site.role])
    return x, y


def tool_shop(d, site, night):
    x, y = shell(d, site, "#acb6b3" if night else "#e6d7ac", night, "#656d6e")
    d.rect(x+8, y+25, 107, 12, "#315e67", 1)
    d.text(x+61, y+33.5, "HARDWARE", 7)
    for wx in (x+9, x+83):
        window(d, wx, y+44, 29, 27, night)
        # Wall-mounted spanners and drills distinguish the hardware windows.
        for offset in (4, 14, 24):
            d.path(f'M{wx+offset} {y+49}v12m-3-12 3 3 3-3', stroke="#e1c176", width=2)
        d.rect(wx-2, y+72, 33, 3, "#776d57")
    d.path(f'M{x+115} {y+20}h12v22h-12Z', "#d9b05b")
    d.path(f'M{x+121} {y+24}v13m-3-13 3 3 3-3', stroke="#36525b", width=2)


def furniture_shop(d, site, night):
    x, y = shell(d, site, "#a49f91" if night else "#ead7bd", night)
    d.rect(x+8, y+24, 106, 12, "#8e6850", 1)
    d.text(x+61, y+33, "HOME FURNISHINGS", 7.5)
    for wx in (x+9, x+83):
        window(d, wx, y+41, 29, 31, night)
    # One sofa and one table with a lamp, instead of generic market crates.
    d.rect(x+12, y+54, 23, 12, "#8ca49a", 3)
    d.rect(x+10, y+59, 27, 8, "#537c76", 2)
    d.path(f'M{x+14} {y+67}v4m19-4v4', stroke="#634f42", width=2)
    d.path(f'M{x+86} {y+62}h24m-19 0v9m14-9v9', stroke="#ba8856", width=3)
    d.path(f'M{x+98} {y+61}V{y+49}m-6 0 3-7h6l3 7Z', "#e5be70", "#b18b51")
    planter(d, x-11, y+73, night)


def pottery_shop(d, site, night):
    x, y = shell(d, site, "#a78370" if night else "#e6b6a0", night)
    for tx in range(7, 116, 7):
        d.path(f'M{x+tx} {y+23}l3-3 3 3-3 3Z', "#759a9b")
    d.rect(x+12, y+29, 101, 11, "#597f80", 1)
    d.text(x+62, y+37, "POTTERY", 6.8)
    for wx in (x+10, x+83):
        window(d, wx, y+44, 28, 28, night)
        for ox, color in ((6,"#d89764"), (19,"#89aaa0")):
            d.path(f'M{wx+ox-2} {y+51}h4v4q9 12-2 12t-2-12Z', color)
            d.ellipse(wx+ox, y+51, 3, 1, "#725c4c")
        d.path(f'M{wx-1} {y+69}h30', stroke="#dac29a", width=2)
    for px, py in ((x-8,y+71),(x+136,y+68)):
        d.ellipse(px, py+8, 7, 3, "#ac7755")
        d.path(f'M{px-3} {py-4}h6v4q10 12-3 12t-3-12Z', "#c58e65")


def bread_shop(d, site, night):
    x, y = shell(d, site, "#a7a391" if night else "#f0dfaf", night)
    d.rect(x+8, y+25, 107, 12, "#8c6348", 1)
    d.text(x+61, y+33.5, "FRESH BREAD", 8)
    for wx in (x+9, x+83):
        window(d, wx, y+46, 29, 26, night)
        for row in (0, 9):
            for bx in (8, 20):
                d.ellipse(wx+bx, y+53+row, 6, 3.5, "#e2b164")
                d.path(f'M{wx+bx-1} {y+51+row}l2 3', stroke="#f7d391", width=1)
    # A burgundy striped canvas awning shades the bakery windows.
    for ax in range(8, 113, 9):
        d.path(f'M{x+ax} {y+38}h9l3 8h-10Z', "#a85f50" if ax % 2 else "#eee0bc")
    d.rect(x-10, y+62, 13, 19, "#475d5d", 1)
    d.text(x-3.5, y+70, "BREAD", 4.5)
    d.path(f'M{x-7} {y+74}h7m-7 3h5', stroke="#dcc59a", width=.8)


def factory(d, site, night):
    colors = ("#c7a18c", "#d8c49c", "#d8a182", "#ecd8ab")
    trade = 0 if site.role == "TIER2" else site.trade
    wall = "#8a8980" if night else colors[trade]
    x, y = shell(d, site, wall, night, "#716f67" if trade == 0 else "#a76b50")
    name = "PRECISION WORKS" if site.role == "TIER2" else ("METALWORK", "CARPENTRY", "CERAMICS", "BAKERY")[trade]
    d.rect(x+10, y+25, 104, 12, ("#4b6972", "#806548", "#9f6046", "#a88045")[trade], 1)
    d.text(x+62, y+34, name, 7)
    for wx in (x+9, x+84):
        window(d, wx, y+44, 27, 28, night)
    if trade == 0:
        d.rect(x+103, y-8, 12, 23, "#6c7778")
        d.path(f'M{x+101} {y-8}h16', stroke="#4f6266", width=3)
        d.path(f'M{x+14} {y+65}h17l-5 5h-8Z', "#aeb8af")
        d.ellipse(x+97, y+58, 7, 7, "#bec3b1")
        d.ellipse(x+97, y+58, 3, 3, "#60767b")
    elif trade == 1:
        d.path(f'M{x+14} {y+62}h18m-15 0v9m12-9v9', stroke="#a97c4e", width=3)
        for i in range(3):
            d.rect(x-11+i*3, y+56-i*3, 4, 24+i*3, "#bc9565")
        d.ellipse(x+98, y+58, 8, 8, "#b1b8ad")
        d.ellipse(x+98, y+58, 2, 2, "#786b55")
    elif trade == 2:
        d.path(f'M{x+11} {y+71}v-12a11 11 0 0 1 22 0v12Z', "#9b604a")
        d.path(f'M{x+15} {y+70}v-10a7 7 0 0 1 14 0v10Z', "#eab076" if night else "#4c4640")
        d.path(f'M{x+97} {y+48}v6q9 13 0 13t0-13Z', "#c98e61")
        d.rect(x+105, y-6, 10, 20, "#b78569")
    else:
        d.path(f'M{x+13} {y+71}v-12a10 10 0 0 1 20 0v12Z', "#aa7657")
        d.path(f'M{x+17} {y+69}v-9a6 6 0 0 1 12 0v9Z', "#e8a25c")
        for bx in (91, 104):
            d.ellipse(x+bx, y+59, 5, 7, "#deb16a")
        d.rect(x+106, y-5, 8, 18, "#b28268")


def supplier(d, site, night):
    # Urban depots keep the material identity without open mines, forests or fields in a city block.
    walls = ("#b2bfc0", "#d7bc96", "#dfb49c", "#e6d4a3")
    x, y = shell(d, site, "#888e87" if night else walls[site.trade], night)
    labels = ("MINERALS", "TIMBER", "CLAY SUPPLIES", "GRAIN")
    d.rect(x+8, y+25, 107, 12, "#6b604b", 1)
    d.text(x+61, y+33.5, labels[site.trade], 7)
    for wx in (x+9, x+84):
        window(d, wx, y+43, 27, 28, night)
    if site.trade == 0:
        for ox, oy in ((15,64),(23,62),(31,65),(20,54),(93,62),(103,58)):
            d.path(f'M{x+ox-5} {y+oy}l3-6 6-1 4 6-5 4Z', "#78888a", "#acb9b3", .6)
        d.rect(x-9, y+67, 14, 12, "#7d8884", 1)
        d.path(f'M{x-7} {y+67}l3-5 5 1 3 4', "#596e74")
    elif site.trade == 1:
        for row in range(3):
            d.rect(x+12, y+51+row*6, 23, 4, "#b58b54")
            d.rect(x+13, y+51+row*6, 3, 4, "#e0b47a")
        for row in range(3):
            d.rect(x+89, y+49+row*7, 20, 5, "#bd945b")
            d.path(f'M{x+94} {y+49+row*7}v5m10-5v5', stroke="#6d6551", width=1.4)
        d.path(f'M{x-8} {y+34}v43m-5-37h11m-11 8h11', stroke="#566c5a", width=2)
        d.path(f'M{x-8} {y+26}l-7 13h14Z', "#708d64")
    elif site.trade == 2:
        for wx in (x+14, x+26, x+91, x+103):
            d.rect(wx-4, y+56, 9, 14, "#c28c69", 1)
            d.path(f'M{wx-3} {y+57}h6m-6 5h6', stroke="#ebc3a2", width=1)
        d.rect(x-11, y+70, 15, 9, "#aa735a", 1)
        d.path(f'M{x-10} {y+73}h13m-8-3v8', stroke="#dcb098", width=1)
    else:
        for bx in (x+15, x+28, x+91, x+104):
            d.path(f'M{bx-4} {y+51}q-5 3-4 17h14q1-14-4-17Z', "#c4ad75")
            d.path(f'M{bx-3} {y+53}h8', stroke="#786b4a", width=1.5)
        d.path(f'M{x+120} {y+20}h12v24h-12Z', "#d2b261")
        d.path(f'M{x+126} {y+24}v16m0-4-4-4m4 0 4-4m-4 0-3-3', stroke="#816d39", width=1)


def warehouse(d, site, night):
    x, y = shell(d, site, "#838e90" if night else "#c1ccca", night, "#677c7e")
    d.rect(x+15, y+24, 95, 11, "#64757b", 1)
    d.text(x+62, y+32.5, "WAREHOUSE", 6.8)
    d.rect(x+8, y+43, 35, 32, "#627981")
    d.rect(x+83, y+43, 32, 32, "#627981")
    for row in range(46, 75, 4):
        d.path(f'M{x+9} {y+row}h33m41 0h30', stroke="#8ca1a1", width=1)
    for bx, by in ((13,66),(25,66),(19,57),(88,66),(100,66)):
        d.rect(x+bx, y+by, 10, 9, "#cba369", 1)
        d.path(f'M{x+bx+5} {y+by}v9', stroke="#f1cd8c", width=1)
    d.rect(x+50, y+40, 28, 13, "#9eafa9")
    d.path(f'M{x+54} {y+46}h20', stroke="#d7dfc9", width=2)


def apartments(d, x, y, index, night):
    sidewalk(d, x, y, night, east=x>=1200, south=y>1080)
    d.add(f'<g data-kind="lisbon-apartments" transform="translate({x} {y})">')
    palettes = ("#e5ce95", "#99b7ae", "#cf927b", "#b0c6bd")
    # A row of narrow Lisbon houses, rather than a uniform slab.
    for number, (left, w, top) in enumerate(((4,54,1),(59,55,-9),(115,57,-1))):
        wall = palettes[(index+number)%4]
        d.rect(left+5, top+15, w, 92-top, "#4e5c58" if night else "#b5aa91")
        d.rect(left, top+12, w, 92-top, "#848e83" if night else wall)
        roof(d, left, top-8, w, "#8c604c" if number != 1 else "#79766a")
        d.rect(left+w-7, top-13, 5, 13, "#c8b99a")
        d.rect(left+w-9, top-14, 9, 3, "#e4d8bf")
        # Azulejo diamonds on alternating façades.
        if (index+number)%2:
            for ty in range(top+17, 84, 7):
                for tx in range(left+4, left+w-4, 7):
                    d.path(f'M{tx} {ty}l2-2 2 2-2 2Z', "#6c8f92" if night else "#739a9c")
        for wy in (top+22, top+49):
            for wx in (left+8, left+33):
                window(d, wx, wy, 12, 19, night and (wx+wy+index)%3 != 0, balcony=True)
        d.rect(left-1, 79, w+2, 3, "#e9deca")
        d.rect(left+6, 86, 16, 18, "#48685e")
        d.rect(left+32, 86, 16, 18, "#48685e")
        d.path(f'M{left+14} 87v16m26-16v16', stroke="#77917a", width=1)
        d.rect(left-1, 103, w+2, 3, "#d6c4a3")
    d.path('M79 29h17', stroke="#344c50", width=.8)
    d.rect(80,29,4,5,"#ce685c")
    d.rect(86,29,4,5,"#e9dfbd")
    d.rect(92,29,4,5,"#7eabc0")
    d.add('</g>')


def map_wayfinding(d, night):
    """Update the streets and signs baked into the original browser map."""
    verge, curb, asphalt = (("#334946", "#666e68", "#47514f") if night else
                            ("#bdc5aa", "#b4ac98", "#747a77"))
    ink = "#f8e5b5" if night else "#314c45"
    d.rect(0, 72, 2400, 66, verge)
    for x in range(20, 2400, 48):
        d.ellipse(x, 78, 8, 4, "#476254" if night else "#819a77")
    y = NORTH_AVENUE_Y
    for half, side, bevel, fill in ((18, 20, 7, curb), (13, 15, 5, asphalt)):
        points = north_avenue_outline(half, side, bevel)
        d.path("M" + "L".join(f"{x} {y}" for x, y in points) + "Z", fill=fill)
    for left, right in zip(NORTH_JUNCTIONS, NORTH_JUNCTIONS[1:]):
        d.add(f'<path d="M{left+24} {y}H{right-24}" stroke="#d8cda9" stroke-dasharray="9 14"/>')
    for x, name in NORTH_QUARTERS:
        d.text(x, 101, name, 14, ink)
    for pier in FERRY_PIERS:
        _, top, _, bottom = pier.kiosk
        y = bottom-8 if pier.north else top+8
        d.rect(pier.x-30, y-5, 60, 10, "#263e46")
        d.text(pier.x, y+2.5, f"Ferry tickets €{FERRY_FARE}", 7.2, "#fff4ce")


def city_svg(night=False):
    d = Drawing(2400, 1780)
    map_wayfinding(d, night)
    for site in SITES:
        if site.name in CLOSED:
            continue
        if site.role not in COMPACT_ROLES:
            continue
        sidewalk(d, site.x, site.y, night, east=site.x>=1200, south=site.y>1080)
        d.add(f'<g data-site="{escape(site.name, quote=True)}">')
        if site.role == "PUBLIC SHOP":
            (tool_shop, furniture_shop, pottery_shop, bread_shop)[site.trade](d, site, night)
        elif site.role == "SUPPLIER":
            supplier(d, site, night)
        elif site.role in ("FACTORY", "TIER2"):
            factory(d, site, night)
        else:
            warehouse(d, site, night)
        planter(d, site.x+13, site.y+91, night)
        planter(d, site.x+166, site.y+91, night)
        signs(d, site, night)
        d.add('</g>')
    locations = [pos for pos, kind in SCENERY_PLOTS if kind == "flats"]
    locations += [(site.x, site.y) for site in SITES if site.name in CLOSED]
    for index, (x,y) in enumerate(locations):
        apartments(d, x, y, index, night)
    # The dealership keeps its own building model; replace its old English sign.
    dealer = next(site for site in SITES if site.name == "Cacilhas Dealership")
    d.rect(dealer.x+9, dealer.y+4, 158, 15, "#a5443d")
    d.text(dealer.x+88, dealer.y+15, "CACILHAS DEALERSHIP", 6.8)
    casino = next(site for site in SITES if site.role == "CASINO")
    d.rect(casino.x+43, casino.y+43, 90, 13, "#523457", 2)
    d.text(casino.x+88, casino.y+52, "Lisbon Casino", 7.5, "#ffe7bd" if night else "#f6dca9")
    shipyard = next(site for site in SITES if site.role == "SHIPYARD")
    d.rect(shipyard.x+11, shipyard.y+75, 154, 15, "#2b4954")
    d.text(shipyard.x+88, shipyard.y+86, "Tagus Shipyard", 8)
    exchange = next(site for site in SITES if site.role == "EXCHANGE")
    d.rect(exchange.x+24, exchange.y+10, 128, 12, "#647476" if night else "#ded5bb")
    d.text(exchange.x+88, exchange.y+19, "LISBON STOCK EXCHANGE", 6.5, "#f3dfae" if night else "#344f5b")
    return d.svg()


def seated_audience(d, x, y, scale, jacket, hair):
    """Back view: shoulders, bent arms and chair all face the screen above."""
    d.add(f'<g data-facing="presentation" transform="translate({x} {y}) scale({scale})">')
    # Hands reach forward onto the far side of the desk, away from the viewer.
    d.path('M-22-23-30-27-27-38M22-23 30-27 27-38', stroke=jacket, width=12)
    for sign in (-1, 1):
        d.ellipse(sign*27, -39, 6, 2, "#cea07d")
    d.path('M-23-27Q0-38 23-27L27 28H-27Z', jacket, "#34484e", 1.5)
    d.path('M-8-28Q0-22 8-28M0-19V16', stroke="#455865", width=1.2)
    d.rect(-6, -41, 12, 13, "#c49b7c", 2)
    d.ellipse(0, -55, 18, 22, hair)
    d.path('M-11-65Q0-73 11-65', stroke="#ffffff", width=.6)
    # The chair back is closest to the camera and covers the lower back.
    d.rect(-34, -1, 68, 42, "#506970", 6)
    d.rect(-29, 3, 58, 30, "#71878a", 4)
    d.path('M-29 17h58', stroke="#637e83", width=1)
    d.path('M-28 40v13m56-13v13', stroke="#4c6267", width=4)
    d.add('</g>')


def person(d, x, y, scale=1, jacket="#344f60", hair="#433f37", skin="#d1a582", presenting=False, back=False):
    """Rounded people, ink edges and small smiles match the game's other interiors."""
    d.add(f'<g transform="translate({x} {y}) scale({scale})">')
    d.ellipse(0, 64, 29, 7, "#857f70")
    for sign in (-1,1):
        d.path(f'M{sign*9} 20l{sign*2} 37', stroke="#3b4b55", width=12)
        d.ellipse(sign*12, 59, 10, 4, "#28383d")
    d.path('M-22-22Q0-33 22-22L19 25Q0 31-19 25Z', jacket, "#34484e", 1.5)
    if not back:
        d.path('M-5-25 0-3 7-25', "#f1e5ce")
    if presenting:
        d.path('M19-15 40-26 55-42', stroke=jacket, width=12)
        d.ellipse(57,-45,6,8,skin)
        d.path('M-20-14-24 10-6 16', stroke=jacket, width=12)
        d.ellipse(-3,16,7,5,skin)
    else:
        for sign in (-1,1):
            d.path(f'M{sign*20}-15 {sign*25} 17', stroke=jacket, width=12)
            d.ellipse(sign*25,20,5,6,skin)
    d.rect(-6,-33,12,12,skin,2)
    d.ellipse(0,-48,17,22,skin)
    d.path('M-17-49Q-22-76 1-73Q23-72 17-47L11-60Q-6-55-12-61L-13-47Z', hair)
    if back:
        d.ellipse(0,-49,17,20,hair)
    else:
        d.ellipse(-6,-47,1.6,2,"#33434a")
        d.ellipse(7,-47,1.6,2,"#33434a")
        d.path('M-5-37Q1-32 7-38', stroke="#855e4e", width=1.7)
    d.add('</g>')


def presentation_svg():
    d = Drawing(1448,1086)
    d.rect(0,0,1448,1086,"#d8ccb3")
    # Warm lecture theatre, drawn with the same flat shaded geometry as the game.
    d.path('M0 0H1448V180L1280 260H180L0 160Z',"#eee4cd")
    d.path('M0 160 180 260V680L0 852Z',"#b78e68")
    for y in range(190,790,15):
        d.path(f'M0 {y} 180 {260+(y-160)*.7}',stroke="#a27b5e",width=1)
    d.path('M1448 180 1280 260V680L1448 852Z',"#bbbaa5")
    d.path('M0 852 180 680H1280L1448 852V1086H0Z',"#b3aa91")
    for x in (-200,100,400,700,1000,1300,1600):
        d.path(f'M724 680 {x} 1086',stroke="#a29880",width=2)
    for y in (759,868,1009):
        d.path(f'M0 {y}H1448',stroke="#c7bda4",width=2)
    d.rect(182,259,1096,420,"#e6deca")
    d.rect(184,664,1093,16,"#b5b39f")
    # Ceiling panels, warm strip lights and a suspended projector.
    for y,x,w in ((65,180,1020),(145,280,840),(210,350,690)):
        d.path(f'M{x} {y}h{w}',stroke="#f9f1d8",width=9)
        d.path(f'M{x} {y+9}h{w}',stroke="#d0c5b0",width=2)
    d.path('M530 140v49',stroke="#919a90",width=8)
    d.rect(481,181,102,35,"#bac4ba",6)
    d.rect(489,186,85,20,"#e6e6d2",4)
    d.ellipse(564,197,10,8,"#45646b")
    d.ellipse(566,196,5,4,"#a0d9df")
    d.rect(410,275,740,329,"#a9aa98",4)
    d.rect(421,283,720,310,"#456a7d",2)
    d.rect(421,283,720,73,"#355767")
    d.text(781,329,"Foundry Town",39,"#f2d69a")
    d.text(781,380,"BUILD  ·  MAKE  ·  TRADE",16,"#dbe6d7")
    # A miniature playable-city illustration on the presentation screen.
    d.rect(705,399,408,159,"#b5c1a4",4)
    d.path('M711 515h396',stroke="#74817a",width=15)
    d.path('M711 515h396',stroke="#e9d9b3",width=1.5)
    d.path('M929 405v146',stroke="#74817a",width=12)
    for i,(color,label) in enumerate((("#c79a55","BUY"),("#5a91a5","MAKE"),("#72a185","SELL"))):
        x=727+i*124
        d.rect(x,447,99,53,"#ead6a9")
        d.path(f'M{x-4} 447l18-18h71l18 18Z',"#ac7757")
        d.rect(x+8,455,82,13,color)
        d.text(x+49,465,label,9)
        for wx in (x+13,x+66):
            window(d,wx,478,17,16)
    d.text(559,425,"01  BUY MATERIALS",17,"#f0e4c9")
    d.text(559,473,"02  PRODUCE GOODS",17,"#f0e4c9")
    d.text(559,521,"03  GROW THE CITY",17,"#f0e4c9")
    d.text(783,580,"A business tycoon made by our team",13,"#dce6d6")
    d.rect(410,604,740,7,"#eff0d8")
    d.text(286,340,"NOVA",27,"#3e6b70")
    d.text(286,369,"SBE",24,"#3e6b70")
    d.text(286,398,"CARCAVELOS",10,"#6a827a")
    # Three presenters: casual knitwear, navy suit, and red tie as in the reference.
    person(d,467,647,1.65,"#baac91","#4d4537")
    person(d,691,645,1.7,"#3f5363","#3b3c32",presenting=True)
    person(d,993,648,1.7,"#354754","#3f4035")
    d.path('M991 607l-5 14 7 24 6-24-4-14Z',"#b24e49")
    # Lectern, open laptop, mouse and clicker; the audience faces the screen.
    d.path('M753 727h125v147H753Z',"#e7dcc2")
    d.path('M878 727l20-12v147l-20 12Z',"#bfb89f")
    d.path('M748 716h150v13H748Z',"#f4ead1")
    d.path('M778 713l-13-56h82l13 56Z',"#657a7f","#3f555c",2)
    d.path('M774 716h98l-12-5h-82Z',"#8d9f9d")
    d.ellipse(810,687,5,6,"#c5d2ca")
    d.rect(871,710,14,5,"#344b51",2)
    for x in (265,1198):
        d.rect(x-20,655,40,49,"#b78b67",4)
        for dx,dy in ((0,-14),(-16,0),(17,-1)):
            d.path(f'M{x} 661q{dx-32}-56 {dx} {dy-65}q34 22 {-dx} 65',"#6b8d6c")
    # Seated professors and students in two staggered rows of lecture desks.
    for row,(py,people) in enumerate(((865,(190,425,1090,1310)),(1050,(165,470,819,1190)))):
        # Desks and laptops are in front of their bodies toward the presentation.
        d.path(f'M28 {py-79}H1420l-18 29H40Z',"#e1d6be")
        d.path(f'M40 {py-50}H1402v8H40Z',"#a59e86")
        for i,px in enumerate(people):
            d.path(f'M{px-31} {py-63}l-4-27h54l8 27Z',"#51747e","#36555e",1.4)
            d.path(f'M{px-25} {py-70}h36m-33-6h25',stroke="#b8d4c9",width=2)
            d.path(f'M{px-34} {py-62}h65',stroke="#b6c1b8",width=4)
            seated_audience(d,px,py-8,1.35 if row==0 else 1.6,
                   ("#5b6574","#8f7f70","#456477","#978f82")[i],
                   ("#655747","#665c4c","#3e4139","#8c8170")[i])
    return d.svg()


def export(presentation=False):
    root = Path(__file__).resolve().parent / "street"
    for night in (False, True):
        (root / f'city_{"night" if night else "day"}.svg').write_text(city_svg(night), encoding="utf-8")
    (root / "scenes" / "nova_presentation.svg").write_text(presentation_svg(), encoding="utf-8")
    if presentation:
        from io import BytesIO
        import resvg_py
        from PIL import Image
        fonts = [str(Path("C:/Windows/Fonts/arial.ttf"))] if Path("C:/Windows/Fonts/arial.ttf").exists() else []
        png = resvg_py.svg_to_bytes(svg_string=presentation_svg(), font_files=fonts)
        Image.open(BytesIO(png)).save(root / "scenes" / "nova_presentation.webp", "WEBP", lossless=True)
        for name in ("goal", "buy", "make", "sell", "garage"):
            png = resvg_py.svg_to_bytes(svg_string=tutorial_svg(name), font_files=fonts)
            Image.open(BytesIO(png)).save(root / "tutorial" / f"{name}.webp", "WEBP", lossless=True)


def tutorial_svg(name):
    """Render tutorial map views from the same building art, without stale baked-in labels."""
    from base64 import b64encode
    root = Path(__file__).resolve().parent / "street"
    base = b64encode((root / "world_100_day.webp").read_bytes()).decode("ascii")
    overlay = city_svg().split('>', 1)[1].rsplit('</svg>', 1)[0]
    campus = b64encode((root / "nova_presentation_signs.svg").read_bytes()).decode("ascii")
    world = (f'<image width="2400" height="1780" href="data:image/webp;base64,{base}"/>'
             f'{overlay}<image x="27" y="508" width="178" height="110" href="data:image/svg+xml;base64,{campus}"/>')
    d = Drawing(650, 406)
    d.rect(0, 0, 650, 406, "#193941")
    if name == "goal":
        d.text(325, 45, "Start with $60 · Reach $500", 25, "#edca80")
        d.add('<svg x="0" y="120" width="650" height="155" viewBox="240 490 1480 353">' + world)
        for n, x in ((1, 1368), (2, 1628), (3, 356)):
            d.ellipse(x, 643, 32, 32, "#eccc85")
            d.text(x, 655, str(n), 30, "#26454d")
        d.add('</svg>')
        d.text(325, 378, "1 Buy materials  ›  2 Make products  ›  3 Sell them", 17)
    else:
        identifier, caption = {
            "buy": ("Goldenfield Farm", "Walk to a yellow BUY MATERIALS store"),
            "make": ("Sunrise Bakery", "Turn materials into products at MAKE PRODUCTS"),
            "sell": ("Daily Bread Market", "Sell finished goods at SELL PRODUCTS"),
            "garage": ("Cacilhas Dealership", "Cacilhas Dealership: take the ferry"),
        }[name]
        site = next(site for site in SITES if site.name == identifier)
        left, top = site.x+88-260, site.y-103
        d.add(f'<svg width="650" height="368" viewBox="{left} {top} 520 294.4">{world}')
        # The tutorial's walking player, in the same compact style as street.js.
        x, y = site.x-32, site.y+119
        d.ellipse(x, y+2, 11, 4, "#88977c")
        d.path(f'M{x-4} {y-9}v10m8-10v10', stroke="#334c58", width=5)
        d.rect(x-7, y-23, 14, 15, "#427e9c", 3)
        d.ellipse(x, y-31, 6, 7, "#d7b084")
        d.rect(x-8, y-38, 16, 5, "#edc575", 2)
        d.add('</svg>')
        d.text(325, 393, caption, 16)
    return d.svg()


if __name__ == "__main__":
    import sys
    export("--presentation" in sys.argv)
