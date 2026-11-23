"""Public-space artwork and the matching water, garden and fountain footprints."""
import math
from city_layout import plot_bounds

EXPANDED_GARDENS=frozenset({(940,1360),(1280,1610)})
EXPANDED_SQUARE=(1800,1360)
LAKE_PLOT=(640,1572,1170,1728)
LAKE=(905,1650,185,40)  # Center and radii of the visible water.


def inset_plot(x,y,margin=10):
    left,top,right,bottom=plot_bounds(x,y)
    return left+margin,top+margin,right-margin,bottom-margin


def garden_bounds(x,y):
    return inset_plot(x,y) if (x,y) in EXPANDED_GARDENS else (x,y,x+176,y+104)


def square_bounds(x,y):
    return inset_plot(x,y) if (x,y)==EXPANDED_SQUARE else (x,y,x+176,y+104)


def fountain_geometry(x,y):
    if (x,y)==EXPANDED_SQUARE:
        left,top,right,bottom=square_bounds(x,y)
        return (left+right)/2,(top+bottom)/2,40,32
    return x+88,y+50,30,24


def fountain_bounds(x,y):
    cx,cy,rx,ry=fountain_geometry(x,y)
    return cx-rx,cy-ry,cx+rx,cy+ry


def lake_blocked(x,y,radius=0):
    cx,cy,rx,ry=LAKE
    return ((x-cx)/(rx+radius))**2+((y-cy)/(ry+radius))**2 <= 1


def bench(d,x,y,vertical=False):
    d.add(f'<g data-kind="bench" transform="translate({x} {y}) rotate({90 if vertical else 0})">')
    d.ellipse(1,5,15,4,"#7a8065")
    d.rect(-12,-1,24,6,"#a27a50",1)
    d.rect(-12,-6,24,3,"#785b41",1)
    d.path('M-9 4v4M9 4v4',stroke="#475c56",width=2)
    d.path('M-10 1h20',stroke="#c39a65",width=.8)
    d.add('</g>')


def tree(d,x,y,night,size=16):
    d.ellipse(x+4,y+7,size+3,size*.65,"#40584f" if night else "#9fa881")
    d.rect(x-2,y,4,size*.5,"#776349")
    d.ellipse(x,y,size,size,"#416758" if night else "#7c9a72")
    d.ellipse(x-size*.3,y-size*.25,size*.65,size*.7,"#537b61" if night else "#9bb88c")


def flowers(d,x,y,color):
    d.ellipse(x,y,15,7,"#78936a")
    for dx in (-9,-3,3,9):
        d.ellipse(x+dx,y-1,2,2.5,color)


def garden(d,bounds,night,mirrored=False):
    left,top,right,bottom=bounds
    w,h=right-left,bottom-top
    def point(u,v):
        return (right-u*w if mirrored else left+u*w),top+v*h
    d.add('<g data-kind="garden">')
    d.rect(left,top,w,h,"#526b54" if night else "#9db584")
    d.rect(left+4,top+4,w-8,h-8,"#627c5e" if night else "#b7c99a")
    points=[point(.04,.8),point(.34,.47),point(.68,.55),point(.96,.19)]
    d.path('M'+'L'.join(f'{x} {y}' for x,y in points),stroke="#929a7d" if night else "#eee5c9",width=12)
    for u,v,c in ((.18,.2,"#e38b7d"),(.76,.77,"#edcc73"),(.52,.86,"#bf99ce")):
        flowers(d,*point(u,v),c)
    for u,v in ((.38,.31),(.66,.67)):
        bench(d,*point(u,v))
    for u,v,size in ((.17,.66,16),(.83,.32,17),(.53,.25,14)):
        tree(d,*point(u,v),night,size)
    # Extra corner planting fills the enlarged plots without stretching the trees.
    if w>210 or h>150:
        for u,v in ((.13,.15),(.88,.84)):
            tree(d,*point(u,v),night,13)
    d.add('</g>')


def square(d,x,y,night):
    left,top,right,bottom=square_bounds(x,y)
    w,h=right-left,bottom-top
    d.add('<g data-kind="fountain-square">')
    d.rect(left,top,w,h,"#657c7d" if night else "#e8e0cb")
    d.rect(left+4,top+4,w-8,h-8,"#738585" if night else "#eee7d5")
    for row in range(6):
        py=top+12+(h-24)*row/5
        points=[(left+5+(w-10)*step/18,py+3*math.sin(step*.8+row)) for step in range(19)]
        d.path('M'+'L'.join(f'{a:.1f} {b:.1f}' for a,b in points),stroke="#536b6e",width=1.5)
    cx,cy,rx,ry=fountain_geometry(x,y)
    d.ellipse(cx+2,cy+5,rx+5,ry+3,"#596d68" if night else "#b4b19b")
    d.ellipse(cx,cy,rx,ry,"#b7c8bb" if night else "#d8cfba")
    d.ellipse(cx,cy,rx-6,ry-5,"#478c9e" if night else "#7fbac2")
    d.ellipse(cx-2,cy-2,rx-14,ry-11,"#70becb" if night else "#a6d8d9")
    if night:
        d.ellipse(cx,cy,rx*.55,ry*.65,"#90d3d8")
    d.rect(cx-4,cy-19,8,21,"#c6d1c1")
    d.ellipse(cx,cy-20,10,4,"#e0ddc9")
    for sign in (-1,1):
        d.path(f'M{cx} {cy-22}Q{cx+sign*18} {cy-47} {cx+sign*(rx-8)} {cy-5}',stroke="#c4edf0",width=2)
        for dy in (1,6,11):
            d.ellipse(cx+sign*(rx-8),cy-15+dy,1,2,"#c4edf0")
    for bx,by in ((left+23,top+22),(right-23,top+22),(left+23,bottom-22),(right-23,bottom-22)):
        bench(d,bx,by)
    for lx in (left+9,right-9):
        if night:
            d.add(f'<ellipse cx="{lx}" cy="{top+16}" rx="18" ry="24" fill="url(#public-space-glow)"/>')
        d.path(f'M{lx} {top+20}V{bottom-8}',stroke="#4c6463",width=2)
        d.ellipse(lx,top+16,3,4,"#ffe4a2" if night else "#e4d8ac")
    d.add('</g>')


def lake(d,night):
    left,top,right,bottom=LAKE_PLOT
    cx,cy,rx,ry=LAKE
    d.add('<g data-kind="lake-park">')
    d.rect(left,top,right-left,bottom-top,"#546b52" if night else "#b5c49a")
    d.ellipse(cx,cy,rx+28,ry+21,"#939f82" if night else "#e9dfbe")
    d.ellipse(cx,cy,rx+16,ry+12,"#758b65" if night else "#8fa977")
    d.ellipse(cx+2,cy+3,rx+4,ry+3,"#426c68" if night else "#7d9677")
    d.ellipse(cx,cy,rx,ry,"#366d80" if night else "#68a7b6")
    d.ellipse(cx-12,cy-5,rx-22,ry-10,"#4e93a5" if night else "#8bc2c9")
    for dx,dy,width in ((-115,-7,35),(-30,10,48),(62,-14,36),(110,13,25)):
        d.path(f'M{cx+dx} {cy+dy}h{width}',stroke="#96cbd0",width=1)
    for dx,dy in ((-105,-65),(105,-65),(-105,65),(105,65)):
        bench(d,cx+dx,cy+dy)
    for sign in (-1,1):
        bench(d,cx+sign*238,cy,vertical=True)
        for dy in (-54,54):
            tree(d,cx+sign*228,cy+dy,night,13)
        # Reeds and pebbles sit on the water's edge, clear of the walking path.
        for dx in (-3,1,5):
            d.path(f'M{cx+sign*166+dx} {cy+19}v-10',stroke="#79935f",width=1.5)
    for dx,dy in ((-50,-5),(46,10)):
        d.ellipse(cx+dx,cy+dy,5,3,"#e5e5ca")
        d.ellipse(cx+dx+4,cy+dy-3,2.4,2.4,"#f0ecd8")
        d.path(f'M{cx+dx+6} {cy+dy-3}h3',stroke="#d1a258",width=1.5)
    d.add('</g>')


def draw_public_spaces(d,night):
    from lisbon_scene import SCENERY_PLOTS,ORIENTE_PARK_BOUNDS
    d.add('<defs><radialGradient id="public-space-glow"><stop stop-color="#ffda85" stop-opacity=".5"/>'
          '<stop offset="1" stop-color="#ffda85" stop-opacity="0"/></radialGradient></defs>')
    mirrored=False
    for (x,y),kind in SCENERY_PLOTS:
        if kind not in ("park","fountain"):
            continue
        if (x,y) in EXPANDED_GARDENS or (x,y)==EXPANDED_SQUARE:
            left,top,right,bottom=plot_bounds(x,y)
            d.rect(left,top,right-left,bottom-top,"#546464" if night else "#c5c9a6")
        if kind=="park":
            garden(d,garden_bounds(x,y),night,mirrored)
            mirrored=not mirrored
        else:
            square(d,x,y,night)
    garden(d,ORIENTE_PARK_BOUNDS,night)
    lake(d,night)
