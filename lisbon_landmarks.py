"""Lisbon sights, drawn once into the day/night scenery caches.

Inspired by the limestone Manueline monuments in Belém, the castle's stone
walls and towers, and the yellow arcades and equestrian statue of Terreiro
do Paço. This is a compact game interpretation rather than a scale map.

References: https://www.visitportugal.com/en/content/mosteiro-dos-jeronimos
https://www.visitlisboa.com/en/places/torre-de-belem/
https://castelodesaojorge.pt/en/castle/national-monument/the-walls/
https://www.visitlisboa.com/en/places/praca-do-comercio-terreiro-do-paco
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Landmark:
    name: str
    bounds: tuple
    kind: str

    @property
    def map_point(self):
        left, top, right, bottom = self.bounds
        return (left+right)/2, (top+bottom)/2


LANDMARKS = (
    Landmark("Mosteiro dos Jerónimos", (28, 345, 204, 449), "monastery"),
    Landmark("Castelo de São Jorge", (748, 160, 924, 264), "castle"),
    Landmark("Praça do Comércio", (508, 530, 684, 634), "square"),
    Landmark("Torre de Belém", (90, 735, 190, 850), "tower"),
)

# The square's central courtyard is open to the player. The tower stands in
# the river, which already blocks walking, so needs no extra land collision.
LANDMARK_SOLIDS = (
    LANDMARKS[0].bounds,
    LANDMARKS[1].bounds,
    (508, 530, 532, 634), (660, 530, 684, 634), (532, 530, 660, 552),
)


def _oval(scene, bounds, color):
    return scene.c.create_oval(*bounds, fill=color, outline="", tags="city")


def _arch(scene, x, top, width, bottom, color):
    """An arched opening supported by both the Pillow and Tk painters."""
    radius = width/2
    _oval(scene, (x, top, x+width, top+width), color)
    scene.rect(x, top+radius, x+width, bottom, color)


def _plaque(scene, x, y, text, width, size=7):
    scene.rect(x-width/2, y-7, x+width/2, y+7, "#4b615c")
    scene.text(x, y, text, size, "#f8ecd1", True, "center")


def monastery(scene):
    x, y = 28, 345
    # Long limestone cloister and ornate church portal beside the west spire.
    scene.poly((x+5, y+91, x+180, y+91, x+180, y+105, x+9, y+105), "#b8b19d")
    scene.rect(x+5, y+37, x+171, y+94, "#e4dcc5")
    scene.rect(x+7, y+38, x+170, y+43, "#f8eed5")
    scene.rect(x+7, y+84, x+170, y+89, "#c9bfa2")
    for column in range(x+16, x+170, 21):
        scene.rect(column-3, y+42, column+2, y+87, "#f6edd5")
        _arch(scene, column+4, y+50, 12, y+82, "#657a75")
        scene.line((column+10, y+52, column+10, y+79), "#c5cdb3", 1)
        scene.poly((column-4, y+39, column, y+29, column+4, y+39), "#eee3c7")
    # Tall bell tower, layered pinnacles and a small dome.
    scene.rect(x+13, y+12, x+43, y+82, "#eee5ce")
    scene.rect(x+16, y+19, x+40, y+24, "#c8bca0")
    _arch(scene, x+22, y+30, 12, y+53, "#526a65")
    scene.line((x+28, y+36, x+28, y+47), "#bba576", 2)
    _oval(scene, (x+15, y+1, x+41, y+25), "#d9cdb1")
    scene.rect(x+14, y+12, x+43, y+17, "#f5ead0")
    scene.line((x+28, y, x+28, y-7), "#a39b83", 2)
    scene.line((x+24, y-4, x+32, y-4), "#a39b83", 2)
    for side in (x+11, x+45):
        scene.poly((side-3, y+19, side, y+7, side+3, y+19), "#f0e4c8")
    # Manueline-inspired portal with stone tracery and rose window.
    scene.rect(x+92, y+28, x+129, y+91, "#e9dfc4")
    scene.poly((x+89, y+31, x+110, y+17, x+132, y+31), "#f5ead0")
    _oval(scene, (x+103, y+32, x+119, y+48), "#79938b")
    scene.line((x+111, y+33, x+111, y+47), "#e5d6b1", 2)
    scene.line((x+104, y+40, x+118, y+40), "#e5d6b1", 2)
    _arch(scene, x+98, y+52, 25, y+89, "#bcae8c")
    _arch(scene, x+102, y+57, 17, y+89, "#59695f")
    for side in (x+94, x+126):
        scene.line((side, y+38, side, y+88), "#f8eed5", 3)
        for level in range(y+43, y+84, 9):
            scene.line((side-3, level+3, side+3, level-3), "#cbbd9a", 1)
    _plaque(scene, x+88, y+96, "MOSTEIRO DOS JERÓNIMOS", 168, 7)


def castle(scene):
    x, y = 748, 160
    _oval(scene, (x-3, y+11, x+181, y+99), "#a6b18c")
    scene.poly((x+13, y+86, x+37, y+59, x+135, y+56, x+168, y+86), "#bcc29e")
    scene.rect(x+12, y+37, x+165, y+90, "#b8ab8a")
    scene.rect(x+15, y+42, x+165, y+50, "#ddd0ad")
    for tower_x, height in ((x+12, 72), (x+65, 64), (x+139, 79)):
        top = y+90-height
        scene.rect(tower_x, top, tower_x+27, y+91, "#d0c09c")
        scene.rect(tower_x+21, top+7, tower_x+27, y+89, "#b4a17d")
        for merlon in range(tower_x-2, tower_x+29, 8):
            scene.rect(merlon, top-5, merlon+5, top+5, "#e1d3b0")
        for slit_y in range(top+16, y+73, 20):
            scene.rect(tower_x+11, slit_y, tower_x+15, slit_y+11, "#62705c")
    for merlon in range(x+42, x+138, 10):
        scene.rect(merlon, y+33, merlon+6, y+42, "#dfd0ab")
    for level in range(y+52, y+88, 11):
        scene.line((x+43, level, x+137, level), "#afa07e", 1)
        for seam in range(x+47+(level % 2)*8, x+137, 21):
            scene.line((seam, level-10, seam, level), "#afa07e", 1)
    _arch(scene, x+90, y+61, 22, y+91, "#5e6654")
    scene.line((x+77, y+22, x+77, y+5), "#756c55", 1)
    scene.poly((x+78, y+6, x+92, y+10, x+78, y+15), "#a46c5b")
    _plaque(scene, x+88, y+96, "CASTELO DE SÃO JORGE", 170, 7)


def square(scene):
    x, y = 508, 530
    scene.rect(x, y, x+176, y+104, "#ece3c9")
    for row in range(y+27, y+101, 12):
        scene.line((x+25, row, x+151, row), "#d5ceb8", 1)
    for column in range(x+31, x+151, 16):
        scene.line((column, y+23, column, y+102), "#d5ceb8", 1)
    # Pombaline yellow U-shaped arcades, open towards the waterfront.
    for left, right in ((x, x+24), (x+152, x+176)):
        scene.rect(left, y+9, right, y+103, "#d8b75c")
        scene.rect(left, y+9, right, y+15, "#fff0c7")
        for top in range(y+22, y+91, 22):
            _arch(scene, left+6, top, 12, top+17, "#667a72")
            scene.rect(left+4, top+17, right-4, top+20, "#f4e7c5")
    scene.rect(x+24, y+4, x+152, y+22, "#dfbd65")
    scene.rect(x+24, y+4, x+152, y+8, "#fff0ce")
    for column in range(x+31, x+150, 16):
        scene.rect(column, y+10, column+7, y+19, "#65818a")
    # Rua Augusta's ceremonial arch and small sculptural crown.
    scene.rect(x+69, y, x+107, y+28, "#ece1c4")
    _arch(scene, x+79, y+10, 18, y+29, "#8b9480")
    scene.rect(x+65, y+2, x+111, y+6, "#f8edd3")
    for pillar in (x+72, x+102):
        scene.rect(pillar, y+7, pillar+4, y+25, "#fff1d1")
    for figure in (x+78, x+88, x+98):
        _oval(scene, (figure-2, y-3, figure+2, y+1), "#e4d9bd")
        scene.line((figure, y, figure, y+4), "#e4d9bd", 3)
    # King José I's equestrian monument on its stone pedestal.
    scene.rect(x+74, y+75, x+102, y+81, "#bfb69b")
    scene.rect(x+79, y+65, x+97, y+76, "#d5c9a9")
    _oval(scene, (x+75, y+49, x+97, y+60), "#658576")
    scene.poly((x+93, y+52, x+98, y+43, x+104, y+43, x+105, y+48, x+99, y+57), "#658576")
    for leg_x in (x+79, x+93):
        scene.line((leg_x, y+57, leg_x-2, y+66), "#577467", 2)
    scene.line((x+76, y+52, x+70, y+58), "#577467", 2)
    scene.line((x+87, y+49, x+87, y+39), "#5c7e6b", 4)
    _oval(scene, (x+84, y+33, x+90, y+40), "#668575")
    scene.line((x+88, y+42, x+98, y+45), "#577467", 2)
    scene.text(x+88, y+95, "PRAÇA DO COMÉRCIO", 7, "#6b715d", True, "center")


def tower(scene):
    x, y = 90, 735
    # Fortified river bastion with projecting bartizans and rope mouldings.
    _oval(scene, (x-5, y+105, x+107, y+121), "#689b9d")
    scene.poly((x+9, y+72, x+83, y+72, x+99, y+95, x+89, y+111, x+8, y+111, x, y+94), "#ded3b4")
    scene.line((x+9, y+80, x+82, y+80, x+93, y+95), "#f7ecd0", 3)
    scene.rect(x+29, y+13, x+74, y+83, "#e7dec4")
    scene.rect(x+65, y+16, x+75, y+84, "#cabd9d")
    for level in (y+32, y+54, y+75):
        scene.rect(x+28, level, x+76, level+4, "#f6ebcd")
    for top in (y+20, y+41, y+62):
        _arch(scene, x+40, top, 12, top+14, "#728980")
        scene.rect(x+38, top+14, x+56, top+17, "#b8b296")
    for battlement in range(x+25, x+79, 9):
        scene.rect(battlement, y+8, battlement+6, y+16, "#f3e7c9")
    for turret_x, turret_y in ((x+21, y+10), (x+72, y+10), (x+1, y+75), (x+86, y+75)):
        scene.rect(turret_x-3, turret_y, turret_x+10, turret_y+22, "#e9dfc2")
        _oval(scene, (turret_x-4, turret_y-5, turret_x+11, turret_y+4), "#e7d9b6")
        scene.poly((turret_x-4, turret_y, turret_x+3, turret_y-10, turret_x+11, turret_y), "#f0e3c5")
        scene.rect(turret_x+2, turret_y+6, turret_x+5, turret_y+13, "#708478")
    for gun_x in range(x+17, x+84, 16):
        _arch(scene, gun_x, y+88, 7, y+99, "#74877b")
    scene.line((x+26, y+83, x+79, y+83), "#bcae8c", 2)
    _plaque(scene, x+50, y+108, "TORRE DE BELÉM", 94, 7)


def draw_landmarks(scene):
    for draw in (monastery, castle, square, tower):
        draw(scene)


def light_landmarks(scene):
    c = scene.c
    def glow(x, y, radius=15):
        c.create_oval(x-radius, y-radius*.65, x+radius, y+radius*.65,
                      fill="#f3d99a", stipple="gray25", outline="", tags="night_lights")
    def window(left, top, right, bottom):
        c.create_rectangle(left, top, right, bottom, fill="#e4cf95", outline="", tags="night_lights")
        glow((left+right)/2, bottom, 12)
    # Warm architectural uplighting, separate from business doorway lights.
    for x in (52, 112, 178):
        glow(x, 432, 24)
    for x in (70, 91, 175):
        window(x, 402, x+7, 421)
    for x, y in ((774, 194), (827, 202), (901, 187)):
        window(x, y, x+3, y+9)
        glow(x, 246, 25)
    for x in (522, 670):
        for y in (558, 580, 602):
            glow(x, y, 13)
    glow(596, 552, 24)
    glow(596, 606, 20)
    for y in (758, 779, 800):
        window(131, y, 138, y+10)
    glow(140, 833, 29)
    for y in (861, 872, 884):
        c.create_line(118, y, 161, y, fill="#c8bd86", stipple="gray25", width=2, tags="night_lights")
    for x, y, title in ((116, 441, "MOSTEIRO DOS JERÓNIMOS"), (836, 256, "CASTELO DE SÃO JORGE"),
                         (596, 625, "PRAÇA DO COMÉRCIO"), (140, 843, "TORRE DE BELÉM")):
        scene.text(x, y, title, 7, "#e6d8b3", True, "center")
