"""Street-bounded plots shared by map artwork, entrances and collision geometry."""

ROAD_COLOR = "#293b46"
COMPACT_ROLES = frozenset({"SUPPLIER", "FACTORY", "PUBLIC SHOP", "WAREHOUSE", "TIER2"})
CLOSED = frozenset({"Motorworks Garage", "Armazém do Seixal", "Pastéis de Belém", "Tool Market", "The Pottery Shop"})


def plot_bounds(x, y):
    if y < 718:
        columns = ((0,218),(258,458),(498,698),(738,938),(978,1205),
                   (1245,1475),(1515,1755),(1795,2015),(2055,2330))
        rows = ((142,276.5),(325.5,461.5),(510.5,637.5))
    else:
        columns = ((350,580),(640,900),(920,1170),(1210,1475),
                   (1515,1755),(1795,2015),(2055,2330))
        rows = ((1089,1221),(1312,1528),(1572,1728))
    # Source coordinates identify a plot; centers, rather than wall edges, select it.
    left,right = min(columns,key=lambda bounds: abs(sum(bounds)/2-(x+88)))
    top,bottom = min(rows,key=lambda bounds: abs(sum(bounds)/2-(y+52)))
    return left,top,right,bottom


def plot_center(x,y):
    left,top,right,bottom = plot_bounds(x,y)
    return (left+right)/2,(top+bottom)/2


def compact_bounds(x,y):
    cx,cy = plot_center(x,y)
    return cx-64,cy-40,cx+64,cy+40


def apartment_transform(x,y):
    cx,cy = plot_center(x,y)
    scale=.9
    return cx-88*scale,cy-44.5*scale,scale


def apartment_bounds(x,y):
    px,py,scale = apartment_transform(x,y)
    return px+4*scale,py+3*scale,px+172*scale,py+106*scale


def legacy_transform(x,y,role):
    cx,cy = plot_center(x,y)
    if role == "GARAGE":  # Center the showroom and its forecourt as one building.
        return cx-88*.9,cy-74*.9,.9
    return cx-88,cy-52,1


def building_bounds(x,y,role,name):
    if name in CLOSED:
        return apartment_bounds(x,y)
    if role in COMPACT_ROLES:
        return compact_bounds(x,y)
    px,py,scale = legacy_transform(x,y,role)
    return px,py,px+176*scale,py+104*scale
