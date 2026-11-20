"""Map collision and time-based walking. Both Lisbon bridges carry pedestrians in Core."""
import math
from catalog import ROUTES

WIDTH, HEIGHT = 2400, 1780
RIVER_TOP, RIVER_BOTTOM = 718, 1080
RADIUS, SPEED = 10, 228

# Physical outlines for the other buildings, gardens and landmarks on the baked map.
SCENERY = (
    (1004,342,1180,446),(988,530,1164,634),(988,160,1164,264),(28,160,204,264),
    (380,1115,556,1219),(1820,345,1996,449),(2080,530,2256,634),(2060,1610,2236,1714),
    (1540,1360,1716,1464),(2060,1360,2236,1464),(508,160,684,264),(28,530,204,634),
    (650,1115,826,1219),(1540,160,1716,264),(1338,371,1398,419),(2080,345,2256,449),
    (700,1360,876,1464),(1280,1360,1456,1464),(1858,1386,1918,1434),(1540,1610,1716,1714),
    (28,345,204,449),(748,160,924,264),(508,530,532,634),(660,530,684,634),
    (532,530,660,552),(1780,190,2030,260),
)
WALLS = SCENERY + tuple((s.x-88,s.y-104,s.x+88,s.y) for r in ROUTES for s in (r.supplier,r.workshop,r.market))


def walkable(x,y):
    if not (RADIUS <= x <= WIDTH-RADIUS and 104+RADIUS <= y <= HEIGHT-RADIUS):
        return False
    if RIVER_TOP-RADIUS < y < RIVER_BOTTOM+RADIUS:
        east = 2035 - .32*(y-RIVER_TOP)
        if abs(x-300)>31-RADIUS and abs(x-east)>27-RADIUS:
            return False
    return not any(l-RADIUS<x<r+RADIUS and top-RADIUS<y<b+RADIUS for l,top,r,b in WALLS)


def move(x,y,dx,dy,seconds):
    length=math.hypot(dx,dy)
    if not length:
        return x,y
    distance=SPEED*min(max(seconds,0),.25)/length
    steps=max(1,math.ceil(distance*length/6))
    for _ in range(steps):
        nx=x+dx*distance/steps
        if walkable(nx,y):
            x=nx
        ny=y+dy*distance/steps
        if walkable(x,ny):
            y=ny
    return x,y
