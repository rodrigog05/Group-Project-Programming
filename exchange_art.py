"""A code-drawn version of the exchange's historic trading hall photograph.

Rebuild the SVG and WebP with:
uv run --python 3.12 --with resvg-py --with Pillow python exchange_art.py
"""
from pathlib import Path
from city_art import Drawing


def chart(d, x, y, w, h, phase=0):
    d.rect(x, y, w, h, "#174a54", 2, "#527a7a")
    for row in range(1, 4):
        d.path(f'M{x+3} {y+h*row/4}h{w-6}', stroke="#2b6369", width=.7)
    for col in range(1, 7):
        d.path(f'M{x+w*col/7} {y+3}v{h-6}', stroke="#2b6369", width=.7)
    points = (0.7, .56, .66, .35, .44, .23, .39, .18, .29, .12)
    path = "M" + "L".join(f'{x+5+i*(w-10)/9:.1f} {y+5+(h-10)*points[(i+phase)%10]:.1f}' for i in range(10))
    d.path(path, stroke="#8bdec5", width=2)


def trader(d, x, y, scale=1, shirt="#68828b", hair="#514738"):
    d.add(f'<g transform="translate({x} {y}) scale({scale})">')
    d.rect(-16, 4, 32, 27, "#354e57", 5)
    d.path('M-11-10Q0-18 11-10L15 15H-15Z', shirt)
    d.path('M-12-7-18 4-29 3M12-7 18 4 27 2', stroke=shirt, width=6)
    d.ellipse(-28,3,4,3,"#cba482")
    d.ellipse(28,2,4,3,"#cba482")
    d.ellipse(0,-24,11,14,"#cfaa87")
    d.path('M-11-25Q-14-44 1-42Q15-41 11-24L6-32-8-31Z',hair)
    d.path('M-13 31v10m26-10v10',stroke="#344951",width=4)
    d.add('</g>')


def ring(d, cx, cy, rx, ry, scale=1):
    d.add(f'<g transform="translate({cx} {cy}) scale({scale})">')
    # Elliptical, bronze trading desks surround the steel monitor tower.
    d.ellipse(0,42,rx+11,ry+9,"#9a7855")
    d.rect(-rx,0,rx*2,55,"#75614e")
    d.ellipse(0,55,rx,ry,"#78624c")
    d.ellipse(0,0,rx,ry,"#c3ad87")
    d.ellipse(0,-1,rx-20,ry-17,"#324d53")
    d.path(f'M{-rx} 38Q0 {ry+90} {rx} 38',stroke="#d5ae66",width=4)
    d.rect(-42,-180,84,184,"#425052")
    d.rect(-33,-175,28,170,"#58605a")
    d.path('M-41-60h82M-41-178h82',stroke="#70bfb9",width=3)
    d.ellipse(0,-12,rx-3,ry-2,"#a89573")
    for i, (x,y) in enumerate(((-rx*.75,4),(-rx*.4,ry*.7),(0,ry*.88),(rx*.4,ry*.7),(rx*.75,4))):
        trader(d,x,y-32,.7,shirt=("#e5dfcd","#77909b","#697f7b")[i%3])
        chart(d,x-24,y-37,48,29,i)
        d.rect(x-19,y-4,37,5,"#a9afa0",1)
    # Tilted front display panels, like the reference's circular tickers.
    for i in range(5):
        x=-rx+12+i*(rx*2-24)/5
        y=ry*.64+9-abs(i-2)*9
        chart(d,x,y,(rx*2-40)/5,40,i)
    d.path(f'M{-rx} -5Q0 {ry*2-5} {rx} -5',stroke="#d1c8ab",width=3)
    d.add('</g>')


def exchange_svg():
    d=Drawing(1600,900)
    d.rect(0,0,1600,900,"#d6c3a0")
    d.path('M0 0H1600L1400 195H185Z',"#bfa77f")
    d.path('M0 0 185 195V530L0 710Z',"#cbb995")
    d.path('M1600 0 1400 195V530L1600 710Z',"#c7b08e")
    d.path('M0 710 185 530H1400L1600 710V900H0Z',"#b58b5e")
    # Parquet follows perspective into the far wall rather than a flat floor grid.
    for x in range(-600,2300,110):
        d.path(f'M790 530 {x} 900',stroke="#96764f",width=2)
    for y in (576,638,716,809,899):
        d.path(f'M0 {y}H1600',stroke="#c4a77c",width=2)
    d.rect(185,125,1215,411,"#d8c6a5")
    # Two tiers of tall arched windows in the classical stone hall.
    for i,x in enumerate(range(220,1380,130)):
        for y,h in ((80,132),(267,205)):
            w=78
            d.path(f'M{x} {y+h}V{y+39}a39 39 0 0 1 78 0v{h-39}Z',"#ebd8b4","#ac9776",3)
            d.path(f'M{x+7} {y+h-6}V{y+39}a32 32 0 0 1 64 0v{h-45}Z',"#52777a")
            for dx in (23,39,55):
                d.path(f'M{x+dx} {y+12}V{y+h-7}',stroke="#d1b988",width=3)
            for dy in range(47,h-6,30):
                d.path(f'M{x+7} {y+dy}h64',stroke="#cfb78a",width=3)
            d.path(f'M{x+8} {y+49}l30-22v{h-35}',stroke="#adc3ba",width=2)
        d.rect(x-16,80,12,418,"#b29d7b")
        d.rect(x-22,73,24,10,"#ecdbb6")
        d.rect(x-22,491,24,12,"#e5d1ab")
    d.rect(183,222,1220,25,"#b19a75")
    d.rect(183,217,1220,6,"#ebd8b2")
    for x in range(190,1400,14):
        d.path(f'M{x} 197v23',stroke="#786e53",width=2)
    d.path('M184 193H1400',stroke="#817556",width=4)
    # Warm wall sconces and substantial columns frame the central space.
    for x in (87,1506):
        d.rect(x-31,104,62,528,"#b69d77")
        d.rect(x-21,111,42,519,"#e1c9a3")
        d.rect(x-38,96,76,16,"#eedbb5")
        d.rect(x-38,628,76,18,"#d6be96")
        for y in (286,457):
            d.ellipse(x,y,15,41,"#c7a16c")
            d.path(f'M{x} {y-19}v35',stroke="#fff0bc",width=4)
    # Black-and-gold iron trusses rise toward the high ceiling.
    for x in (280,585,925,1240):
        d.path(f'M{x} 195V78Q{x} 22 {x-110} 0M{x} 78Q{x} 22 {x+110} 0',stroke="#655f49",width=10)
        d.path(f'M{x+4} 188V78Q{x+4} 22 {x+112} 0',stroke="#be9c61",width=2)
    d.path('M0 36Q800 121 1600 36M0 72Q800 160 1600 72',stroke="#6c654d",width=6)
    # The desks occupy the left of the image; the original ticket remains on the right.
    ring(d,827,417,205,65,.87)
    ring(d,435,622,320,111,1.08)
    for x,y,scale in ((78,494,.8),(1379,504,.75),(1500,643,1.0)):
        d.rect(x-15,y,30,38,"#776349",3)
        for ox,oy in ((-14,-17),(7,-31),(18,-13)):
            d.ellipse(x+ox,y+oy,15,25,"#647b59")
    d.rect(1010,270,247,34,"#38535c",3)
    d.text(1133,293,"LISBON STOCK EXCHANGE",14,"#ead8ad")
    return d.svg()


def export():
    from io import BytesIO
    import resvg_py
    from PIL import Image
    root=Path(__file__).resolve().parent / "street" / "scenes"
    markup=exchange_svg()
    (root / "lisbon_exchange.svg").write_text(markup,encoding="utf-8")
    fonts=["C:/Windows/Fonts/arial.ttf"] if Path("C:/Windows/Fonts/arial.ttf").exists() else []
    png=resvg_py.svg_to_bytes(svg_string=markup,font_files=fonts)
    Image.open(BytesIO(png)).save(root / "lisbon_exchange.webp","WEBP",lossless=True)


if __name__ == "__main__":
    export()
