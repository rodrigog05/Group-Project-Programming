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
        # Overhead three-quarter silhouette follows the blueprint's long
        # wheelbase, broad rear body and narrow nose between exposed wheels.
        oval((-48, -23, 49, 25), "#34433f")
        polygon((-40,-13,-40,13,-29,16,-6,14,4,8,39,4,39,-4,4,-8,-6,-14,-29,-16), "#20264b")
        polygon((-32,-10,-15,-12,-3,-7,-3,7,-15,12,-32,10), "#343f7c")
        polygon((-30,-5,-19,-7,-4,-4,-4,4,-19,7,-30,5), "#ca303d")
        # Engine cover tapers toward the rear wing, behind the central cockpit.
        polygon((-33,-3,-12,-6,-8,-3,-8,3,-12,6,-33,3), "#30376a")
        polygon((-30,-2,-12,-3,-12,0,-30,1), "#e9b829")
        # Suspension arms connect each wheel to the chassis.
        for axle in (-30, 27):
            for side in (-1, 1):
                line((axle-7,side*4,axle,side*18,axle+6,side*4), "#a0a7ac", 1)
        # Four wide slick tyres with yellow sidewall stripes.
        for axle in (-30, 27):
            for side in (-1, 1):
                center_y = side * 18
                polygon((axle-8,center_y-5,axle-6,center_y-7,
                         axle+6,center_y-7,axle+8,center_y-5,
                         axle+8,center_y+5,axle+6,center_y+7,
                         axle-6,center_y+7,axle-8,center_y+5), "#151b22")
                line((axle-5,center_y-5,axle+5,center_y-5), "#d1b83e", 1)
                line((axle-5,center_y+5,axle+5,center_y+5), "#d1b83e", 1)
        # Cockpit and halo sit between the sculpted sidepods.
        oval((-11,-6,5,6), "#111b27")
        oval((-8,-4,-1,4), "#d9c334")
        polygon((-5,-3,-1,-2,-1,2,-5,3), "#526e86")
        line((-10,-7,3,-7,6,0,3,7,-10,7), "#7d8797", 2)
        line((6,0,14,0), "#7d8797", 2)
        # Long yellow nose reaches a multi-element, swept front wing.
        polygon((7,-5,20,-3,42,-2,44,2,20,3,7,5), "#ebbe2e")
        polygon((37,-26,43,-26,44,-12,48,-5,48,5,44,12,43,26,
                 37,26,39,10,43,3,43,-3,39,-10), "#242c50")
        line((40,-24,41,-12,46,-4), "#6673a1")
        line((46,4,41,12,40,24), "#6673a1")
        # Tall rear wing and endplates span the rear tyre track.
        polygon((-47,-24,-40,-24,-39,24,-46,24), "#272e52")
        line((-44,-21,-43,21), "#6c79ab", 2)
        polygon((-48,-25,-39,-25,-39,-22,-48,-22), "#151c2d")
        polygon((-48,22,-39,22,-39,25,-48,25), "#151c2d")
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
