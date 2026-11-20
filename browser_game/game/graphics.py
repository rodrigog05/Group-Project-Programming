"""Render Foundry Town's existing vector drawing commands onto pygame surfaces."""

from functools import lru_cache
import math
import pygame


@lru_cache(maxsize=40)
def face(size, bold):
    f = pygame.font.Font(None, max(9, size))
    f.set_bold(bold)
    return f


class Drawing:
    def __init__(self):
        self.items = {}
        self.tags = {}
        self.serial = 0

    def create(self, kind, coords, options):
        self.serial += 1
        ident = self.serial
        if len(coords) == 1 and isinstance(coords[0], (tuple, list)):
            coords = coords[0]
        self.items[ident] = (kind, list(coords), options)
        tags = options.get("tags", ())
        for tag in (tags,) if isinstance(tags, str) else tags:
            self.tags.setdefault(tag, set()).add(ident)
        return ident

    def create_rectangle(self, *c, **kw):
        return self.create("rect", c, kw)

    def create_oval(self, *c, **kw):
        return self.create("oval", c, kw)

    def create_line(self, *c, **kw):
        return self.create("line", c, kw)

    def create_polygon(self, *c, **kw):
        return self.create("poly", c, kw)

    def create_arc(self, *c, **kw):
        return self.create("arc", c, kw)

    def create_text(self, *c, **kw):
        return self.create("text", c, kw)

    def find_withtag(self, key):
        if isinstance(key, int):
            return (key,) if key in self.items else ()
        return self.items.keys() if key == "all" else self.tags.get(key, ())

    def addtag_withtag(self, name, key):
        self.tags.setdefault(name, set()).update(self.find_withtag(key))

    def dtag(self, key, name):
        if name in self.tags:
            self.tags[name].difference_update(set(self.find_withtag(key)))

    def delete(self, key):
        ids = set(self.find_withtag(key))
        for i in ids:
            del self.items[i]
        for group in self.tags.values():
            group.difference_update(ids)

    def coords(self, key, *values):
        i = next(iter(self.find_withtag(key)), None)
        if i is None:
            return []
        coords = self.items[i][1]
        if values:
            coords[:] = values
        return coords

    def type(self, i):
        return self.items[i][0].replace("poly", "polygon")

    def itemconfigure(self, key, **options):
        for i in self.find_withtag(key):
            self.items[i][2].update(options)

    def move(self, key, x, y):
        for i in self.find_withtag(key):
            c = self.items[i][1]
            for j in range(0, len(c), 2):
                c[j] += x
                c[j + 1] += y

    def scale(self, key, x, y, sx, sy):
        for i in self.find_withtag(key):
            c = self.items[i][1]
            for j in range(0, len(c), 2):
                c[j] = x + (c[j] - x) * sx
                c[j + 1] = y + (c[j + 1] - y) * sy

    def bbox(self, key):
        points = [
            p
            for i in self.find_withtag(key)
            for p in zip(self.items[i][1][::2], self.items[i][1][1::2])
        ]
        if points:
            xs, ys = zip(*points)
            return min(xs), min(ys), max(xs), max(ys)

    def paint(self, surface, offset=(0, 0)):
        for kind, c, o in self.items.values():
            if o.get("state") == "hidden":
                continue
            if offset != (0, 0):
                ox, oy = offset
                if (
                    c[0] + ox < -500
                    or c[0] + ox > surface.get_width() + 500
                    or c[1] + oy < -100
                    or c[1] + oy > surface.get_height() + 100
                ):
                    continue
                c = [v + (ox if i % 2 == 0 else oy) for i, v in enumerate(c)]
            fill = o.get("fill", "")
            outline = o.get("outline", "")
            width = max(1, round(o.get("width", 1)))
            if kind == "text":
                family, size, *style = o.get("font", ("sans", 12))
                f = face(round(abs(size) * (1.33 if size > 0 else 1)), "bold" in style)
                lines = str(o.get("text", "")).splitlines()
                for index, line in enumerate(lines):
                    text = f.render(line, True, fill or "black")
                    anchor = o.get("anchor", "center")
                    pos = text.get_rect()
                    setattr(
                        pos,
                        {
                            "w": "midleft",
                            "e": "midright",
                            "n": "midtop",
                            "s": "midbottom",
                            "nw": "topleft",
                            "ne": "topright",
                            "sw": "bottomleft",
                            "se": "bottomright",
                        }.get(anchor, "center"),
                        (round(c[0]), round(c[1] + index * f.get_linesize())),
                    )
                    surface.blit(text, pos)
            elif kind in ("rect", "oval", "arc"):
                x, y, x2, y2 = c
                r = pygame.Rect(
                    round(min(x, x2)),
                    round(min(y, y2)),
                    max(1, round(abs(x2 - x))),
                    max(1, round(abs(y2 - y))),
                )
                if kind == "arc":
                    start = math.radians(o.get("start", 0))
                    extent = math.radians(o.get("extent", 90))
                    points = [
                        (
                            r.centerx + math.cos(start + extent * i / 24) * r.w / 2,
                            r.centery - math.sin(start + extent * i / 24) * r.h / 2,
                        )
                        for i in range(25)
                    ]
                    if fill:
                        pygame.draw.polygon(surface, fill, [r.center, *points])
                    if outline:
                        pygame.draw.lines(surface, outline, False, points, width)
                else:
                    draw = pygame.draw.rect if kind == "rect" else pygame.draw.ellipse
                    if fill:
                        draw(surface, fill, r)
                    if outline:
                        draw(surface, outline, r, width)
            else:
                points = list(zip(c[::2], c[1::2]))
                if kind == "line":
                    if fill:
                        pygame.draw.lines(surface, fill, False, points, width)
                elif len(points) >= 3:
                    if fill:
                        pygame.draw.polygon(surface, fill, points)
                    if outline:
                        pygame.draw.lines(surface, outline, True, points, width)


@lru_cache(maxsize=180)
def avatar(body, hair, costume, vehicle, facing, frame):
    from tycoon import draw_character, BODY_COLORS, HAIR_COLORS, COSTUMES
    from vehicle_art import draw_player_vehicle

    drawing = Drawing()
    profile = dict(body=body, hair=hair, costume=costume)
    if vehicle:
        draw_player_vehicle(drawing, vehicle, facing, profile, BODY_COLORS, COSTUMES)
    else:
        draw_character(
            drawing,
            profile,
            BODY_COLORS,
            HAIR_COLORS,
            COSTUMES,
            0,
            0,
            (frame - 1) * math.tau / 8 / 13,
            frame > 0,
            facing,
        )
    drawing.move("all", 56, 60)
    image = pygame.Surface((112, 84), pygame.SRCALPHA)
    drawing.paint(image)
    return image
