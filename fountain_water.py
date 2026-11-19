"""Retained water jets, falling droplets and basin ripples for praça fountains."""
import math

from lisbon_scene import SCENERY_PLOTS


class FountainWater:
    def __init__(self, canvas, zoom):
        self.canvas, self.zoom = canvas, zoom
        self.fountains = []
        self.frame = None
        for (x, y), kind in SCENERY_PLOTS:
            if kind != "fountain":
                continue
            jets = [canvas.create_line(0, 0, 1, 1, fill="#b7e7ef", width=2*zoom,
                                       smooth=True, tags="fountain-water") for _ in range(3)]
            drops = [canvas.create_oval(0, 0, 1, 1, fill="#e1f7f8", width=0,
                                       tags="fountain-water") for _ in range(12)]
            ripples = [canvas.create_oval(0, 0, 1, 1, outline="#c4eced", width=zoom,
                                         tags="fountain-water") for _ in range(2)]
            self.fountains.append((x+88, y+28, jets, drops, ripples))
        self.update(0)

    def update(self, elapsed):
        frame = int(elapsed*25)
        if frame == self.frame:
            return
        self.frame = frame
        c, z = self.canvas, self.zoom
        for x, y, jets, drops, ripples in self.fountains:
            height = 24 + 2*math.sin(elapsed*3)
            for index, direction in enumerate((-1, 0, 1)):
                c.coords(jets[index], x*z, y*z, (x+direction*11)*z, (y-height)*z,
                         (x+direction*22)*z, (y+20)*z)
            for index, item in enumerate(drops):
                direction = -1 if index % 2 else 1
                phase = (elapsed*.7 + index/12) % 1
                dx = direction*22*phase
                dy = -4*height*phase*(1-phase)+20*phase
                c.coords(item, (x+dx-1)*z, (y+dy-2)*z, (x+dx+1)*z, (y+dy+2)*z)
            for index, item in enumerate(ripples):
                phase = (elapsed*.8+index*.5) % 1
                radius = 3+8*phase
                center = x+(-22 if index == 0 else 22)
                c.coords(item, (center-radius)*z, (y+20-radius*.35)*z,
                         (center+radius)*z, (y+20+radius*.35)*z)
