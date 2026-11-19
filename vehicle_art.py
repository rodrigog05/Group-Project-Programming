"""Reference-inspired vehicle silhouettes for the retained town renderer."""


def draw_player_vehicle(canvas, kind, facing, profile, body_colors, costumes):
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
        # Seated rider: thigh reaches forward, shin folds back to the foot peg.
        jacket, accent = costumes[profile["costume"]]
        skin = body_colors[profile["body"]]
        polygon((-10,-14,0,-15,14,-5,8,9,1,9,5,-3,-10,-7), "#45647d")
        polygon((1,6,9,6,12,11,0,11), "#252c33")
        polygon((-14,-17,-12,-35,0,-37,10,-22,1,-12), jacket)
        line((-6,-32,4,-23,18,-18), jacket, 6)
        oval((15,-20,21,-16), skin)
        line((-11,-31,-4,-23), accent, 2)
        oval((-10,-53,9,-34), "#242e38")
        polygon((1,-49,9,-47,10,-41,1,-40), "#87a8b1")
        line((-5,-51,2,-52), "#c9d1d4", 2)
    elif kind == "car":
        polygon((-37,-2,-32,-10,-23,-13,-12,-23,3,-25,14,-22,25,-12,35,-9,40,-2,37,9,-35,9), "#c51b2b")
        polygon((-18,-14,-10,-21,2,-23,12,-20,23,-12), "#192c35")
        polygon((-8,-20,2,-22,10,-20,18,-14,-5,-14), "#506a75")
        polygon((-34,-7,-22,-10,-8,-9,7,-1,23,-8,36,-5,33,2,10,5,-12,1), "#ef3540")
        polygon((-16,-4,-3,-3,10,2,17,0,11,6,-9,2), "#921523")
        polygon((21,-9,34,-7,37,-4,26,-5), "#f9eacb")
        polygon((30,1,40,-1,38,7,28,7), "#1b252c")
        polygon((-37,-8,-28,-10,-26,-7,-37,-5), "#771321")
        polygon((-34,4,35,4,36,10,-34,10), "#292f35")
        polygon((28,-4,37,-3,35,-1,27,-2), "#f6f0cf")
        line((25,-7,35,-6), "#ffeec7", 2)
        line((-31,-6,-20,-8), "#7a1322", 2)
        line((7,-9,9,3), "#9f1426")
        line((11,-7,15,-7), "#c5bcc0")
        polygon((-29,-11,-18,-12,-17,-9,-30,-8), "#252f34")
        wheel_positions = (-23, 24)
    elif kind == "f1":
        # Side profile: low chassis, long nose, exposed slicks and elevated rear wing.
        polygon((-49,5,49,5,48,10,-48,10), "#171c29")
        line((-35,4,33,4), "#8c959c", 2)
        polygon((-37,3,-33,-9,-23,-13,-16,-22,-9,-23,-2,-10,
                 16,-5,42,-2,47,3,42,6,-35,6), "#242b58")
        polygon((-33,-7,-20,-11,-5,-7,13,-2,5,4,-27,3), "#354783")
        polygon((-30,-10,-23,-14,-13,-14,-7,-8,-17,-6), "#d93443")
        polygon((-22,-14,-16,-22,-10,-22,-5,-13), "#dfb936")
        polygon((7,-6,30,-2,43,0,44,3,28,4,12,0), "#efc32f")
        # Broad rear-wing endplate/support, with the original slim wing above.
        polygon((-44,-20,-37,-20,-35,3,-43,3), "#32394c")
        line((-40,-18,-38,1), "#586378", 2)
        polygon((-47,-24,-32,-24,-32,-20,-47,-20), "#252d51")
        line((-46,-23,-33,-23), "#8491ba")
        line((-4,-12,0,-21,12,-21,18,-8), "#75849a", 2)
        oval((2,-20,11,-11), "#e2c938")
        polygon((6,-18,11,-17,11,-14,6,-14), "#293f56")
        polygon((38,3,49,3,49,7,37,7), "#272e4d")
        line((39,1,48,1), "#7e89ad")
        for axle in (-33, 31):
            oval((axle-11,-3,axle+11,19), "#151b22")
            oval((axle-8,-.0,axle+8,16), "#d6bc3f")
            oval((axle-6,2,axle+6,14), "#303948")
            oval((axle-2,6,axle+2,10), "#818a96")
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
    if kind in ("car", "van"):
        for x in wheel_positions:
            oval((x-8, 2, x+8, 18), "#1c2228")
            oval((x-5.5, 4.5, x+5.5, 15.5), "#343b40" if kind == "car" else "#b9c4c9")
            oval((x-3, 7, x+3, 13), "#39434b")
            for dx, dy in ((0, 5), (4, 2), (3, -4)):
                line((x-dx, 10-dy, x+dx, 10+dy), "#606970" if kind == "car" else "#d7dedf", 1)
            oval((x-1, 9, x+1, 11), "#d4b752" if kind == "car" else "#818c91")
    if facing < 0:
        for item in set(canvas.find_withtag("player")) - previous:
            coordinates = canvas.coords(item)
            mirrored = [-value if index % 2 == 0 else value for index, value in enumerate(coordinates)]
            if canvas.type(item) == "oval":
                mirrored[0], mirrored[2] = mirrored[2], mirrored[0]
            canvas.coords(item, *mirrored)
