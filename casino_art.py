"""Neon casino facade and shared positions for animated marquee bulbs."""


def window_bounds(site):
    for left in (site.x+3, site.x+155):
        for height in (38, 52, 66, 84):
            for offset in (0, 8):
                yield left+offset, site.y+height, left+offset+5, site.y+height+9


def bulb_positions(site):
    x, y = site.x, site.y
    for side in (25, 135):
        for height in range(15, 94, 8):
            for edge in (0, 19):
                yield x+side+edge, y+height
    for row in (66, 75):
        for offset in range(50, 130, 8):
            yield x+offset, y+row
    for offset in range(53, 127, 8):
        yield x+offset, y+43


def draw_casino(scene, site):
    x, y, right, bottom = site.bounds
    p = scene
    p.poly((x+5,y+12,right+5,y+12,right+5,bottom+5,x+5,bottom+5), "#615264")
    p.rect(x,y+25,right,bottom,"#493353")
    for bounds in window_bounds(site):
        p.rect(*bounds, "#62546b")
    p.rect(x+41,y+12,right-40,bottom,"#683851")
    for height in (13,23,33):
        p.rect(x+39,y+height,right-39,y+height+4,"#edb55d")
    p.poly((x+42,y+59,x+43,y+48,x+59,y+39,x+116,y+39,x+133,y+48,x+134,y+59),
           "#26263f", outline="#a08bc3")
    p.text(x+88,y+51,"Lisbon Casino",8,"#ffb8e4",True,"center")
    for left in (x+23,x+133):
        p.rect(left-3,y+8,left+26,y+98,"#8c5974")
        p.rect(left,y+11,left+23,y+96,"#edaa55")
        p.rect(left+3,y+14,left+20,y+93,"#56517b")
        for symbol,height,color in (("♥",25,"#ff9dbe"),("♦",45,"#ffe095"),
                                    ("♠",65,"#ffb0c5"),("♣",84,"#ffe095")):
            p.text(left+11,y+height,symbol,11,color,True,"center")
        p.poly((left-8,y+5,left+28,y+5,left+31,y+10,left-6,y+10),"#40374e")
    p.rect(x+49,y+62,right-49,y+80,"#7f2d60")
    p.rect(x+61,y+82,right-61,bottom,"#261b36")
    p.rect(x+68,y+84,right-68,bottom,"#f3c67f")
    p.rect(x+87,y+84,x+90,bottom,"#725135")
    p.poly((x+61,y+82,x+70,y+82,x+67,bottom,x+61,bottom),"#b54a71")
    p.poly((right-61,y+82,right-70,y+82,right-67,bottom,right-61,bottom),"#b54a71")
    p.rect(x+59,bottom,right-59,bottom+5,"#c6af88")
    for bx,by in bulb_positions(site):
        p.c.create_oval(bx-1.2,by-1.2,bx+1.2,by+1.2,fill="#ffdf93",width=0,tags="city")


class CasinoLights:
    def __init__(self, canvas, sites, zoom):
        self.canvas = canvas
        self.frame = None
        self.items = []
        for site in sites:
            if site.role == "CASINO":
                for x,y in bulb_positions(site):
                    item = canvas.create_oval((x-1.3)*zoom,(y-1.3)*zoom,
                                              (x+1.3)*zoom,(y+1.3)*zoom,
                                              fill="#ffdf93",width=0,tags="casino-lights")
                    self.items.append(item)

    def update(self, elapsed):
        frame = int(elapsed*5)
        if frame == self.frame:
            return
        self.frame = frame
        for index,item in enumerate(self.items):
            color = ("#fff0b5","#ff89d0","#8c6b99")[(index+frame)%3]
            self.canvas.itemconfigure(item,fill=color)
