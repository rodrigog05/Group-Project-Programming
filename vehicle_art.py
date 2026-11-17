"""Reference-inspired vehicle silhouettes for the retained town renderer."""


def draw_player_vehicle(canvas, kind, facing):
    previous = set(canvas.find_withtag("player"))

    def polygon(points, color):
        canvas.create_polygon(*points, fill=color, outline="", tags="player")

    def oval(bounds, color):
        canvas.create_oval(*bounds, fill=color, outline="", tags="player")

    def line(points, color, width=1):
        canvas.create_line(*points, fill=color, width=width, tags="player")

    oval((-37, 3, 38, 20), "#34433f")
    if kind == "motorcycle":
        for x in (-25, 26):
            oval((x-9, 1, x+9, 19), "#181e24")
            oval((x-6, 4, x+6, 16), "#aab3b8")
            oval((x-4, 6, x+4, 14), "#253744")
            line((x-5, 10, x+5, 10), "#dce0df", 2)
        line((-24, 9, -7, -6, 11, 7, -24, 9), "#677278", 3)
        line((18, -12, 26, 10), "#a6adb0", 3)
        polygon((-32,-13,-17,-9,-6,-16,7,-15,28,-8,32,0,14,8,-3,3,-13,-5,-29,-6), "#e7edef")
        polygon((2,-11,19,-9,27,-3,9,0,-1,-3), "#287abc")
        polygon((7,-7,23,-5,27,-1,10,-3), "#d83d43")
        polygon((-10,-16,2,-17,9,-12,1,-7,-9,-8), "#f5f6f2")
        polygon((-24,-15,-9,-14,-7,-10,-24,-11), "#24292e")
        polygon((20,-14,24,-24,30,-18,31,-9), "#8ca7b1")
        line((16,-16,28,-15), "#24292e", 2)
        oval((15,-20,20,-17), "#303940")
        polygon((28,-5,33,-3,30,0,26,-1), "#f6e7b3")
    elif kind == "car":
        polygon((-36,-4,-29,-10,-11,-13,1,-22,18,-21,29,-10,37,-5,36,9,-34,9), "#b91d30")
        polygon((-35,-4,-13,-8,19,-8,35,-4,32,3,-32,3), "#e23845")
        polygon((-9,-13,2,-20,16,-19,24,-11), "#263a45")
        polygon((2,-18,14,-18,18,-12,0,-12), "#6a8c99")
        polygon((20,-9,34,-6,29,-3,15,-5), "#f04850")
        polygon((-34,4,35,4,36,10,-34,10), "#292f35")
        polygon((28,-4,37,-3,35,-1,27,-2), "#f6f0cf")
        line((25,-7,35,-6), "#ffeec7", 2)
        line((-31,-6,-20,-8), "#7a1322", 2)
        line((7,-9,9,3), "#9f1426")
        line((11,-7,15,-7), "#c5bcc0")
        polygon((-29,-11,-18,-12,-17,-9,-30,-8), "#252f34")
        wheel_positions = (-23, 24)
    else:
        polygon((-36,-25,12,-25,28,-15,37,-6,37,10,-36,10), "#c7cecf")
        polygon((-33,-23,10,-23,10,6,-33,6), "#f3f3ed")
        polygon((12,-23,25,-14,31,-6,12,-6), "#5c7c89")
        polygon((14,-21,22,-14,25,-8,14,-8), "#8cabb4")
        polygon((12,-4,34,-4,37,1,34,8,12,8), "#e1e4df")
        polygon((-36,5,37,5,37,11,-36,11), "#30363c")
        line((-17,-20,-17,4), "#a9b3b4")
        line((-30,-18,6,-18), "#d1d7d4")
        line((14,-4,14,5), "#9da7a9")
        line((-14,-4,-11,-4), "#353d43", 2)
        oval((23,-9,28,-4), "#242d33")
        polygon((31,-4,36,-2,36,1,30,0), "#f3e9bd")
        line((32,3,37,3), "#77868b", 2)
        line((-36,-14,-36,-4), "#c34a40", 2)
        wheel_positions = (-24, 25)
    if kind != "motorcycle":
        for x in wheel_positions:
            oval((x-8, 2, x+8, 18), "#1c2228")
            oval((x-5.5, 4.5, x+5.5, 15.5), "#b9c4c9")
            oval((x-3, 7, x+3, 13), "#39434b")
            for dx, dy in ((0, 5), (4, 2), (3, -4)):
                line((x-dx, 10-dy, x+dx, 10+dy), "#d7dedf", 1)
            oval((x-1, 9, x+1, 11), "#d4b752" if kind == "car" else "#818c91")
    if facing < 0:
        for item in set(canvas.find_withtag("player")) - previous:
            coordinates = canvas.coords(item)
            mirrored = [-value if index % 2 == 0 else value for index, value in enumerate(coordinates)]
            if canvas.type(item) == "oval":
                mirrored[0], mirrored[2] = mirrored[2], mirrored[0]
            canvas.coords(item, *mirrored)
