"""Decorative casino interior behind the existing roulette controls."""


def draw_background(canvas, width, top, bottom):
    def box(left, y, right, lower, color):
        canvas.create_rectangle(left, y, right, lower, fill=color, width=0, tags="live")

    def line(points, color, thickness=1):
        canvas.create_line(*points, fill=color, width=thickness, tags="live")

    def oval(bounds, color, outline="", thickness=0):
        canvas.create_oval(*bounds, fill=color, outline=outline, width=thickness, tags="live")

    horizon = top + 270
    box(0, top, width, bottom, "#20172e")
    box(0, horizon, width, bottom, "#482d3c")
    for band in range(12):
        y = horizon+(bottom-horizon)*band/12
        shade = ("#482d3c", "#4b2e3d", "#4e303e", "#51313e",
                 "#54333f", "#573440", "#5a3540", "#5d3741",
                 "#603842", "#633a43", "#663c44", "#693d45")[band]
        box(0,y,width,y+(bottom-horizon)/12+1,shade)
    # Perspective carpet diamonds and warm gold stitching.
    for y in range(horizon+20, bottom, 65):
        size = 12 + (y-horizon)*.045
        for x in range(25, width, 65):
            canvas.create_polygon(x, y-size, x+size, y, x, y+size, x-size, y,
                                  fill="", outline="#926654", width=1, tags="live")
    for x in range(-width, width*2, 160):
        line((width/2, horizon, x, bottom), "#8d4960")
    # Layered ceiling coves with electric blue and gold edges.
    for inset, y, color in ((0, top+14, "#36439c"), (15, top+25, "#4aaaff"),
                             (45, top+48, "#1d2761"), (50, top+53, "#aa7fda")):
        line((inset, y+70, width*.26, y, width*.74, y, width-inset, y+70), color, 7)
    for center in (width*.12, width*.88):
        oval((center-105, top+12, center+105, top+72), "#111a40", "#dcaa45", 5)
        oval((center-79, top+21, center+79, top+60), "#373475", "#50baff", 3)
    # Columns frame the foreground table while the passage recedes behind it.
    for x in (72, width-72, 210, width-210):
        oval((x-31,horizon+88,x+35,horizon+113),"#34283a")
        for offset,color in ((-20,"#443445"),(-15,"#75505d"),(-9,"#ae7c6d"),
                             (-3,"#c6987c"),(3,"#9d6d60"),(9,"#6d4a55"),(15,"#493646")):
            box(x+offset,top+70,x+offset+6,horizon+100,color)
        box(x-20, top+90, x+20, top+96, "#e7b84d")
        box(x-22, horizon+94, x+22, horizon+104, "#3e3452")
        box(x-17, top+130, x-9, top+170, "#ffc478")
        box(x-18,top+127,x-8,top+131,"#5d4638")
        box(x-18,top+170,x-8,top+174,"#5d4638")
        line((x-14,top+133,x-14,top+168),"#ffe6ad",2)
    # Slot machines line both sides, growing larger toward the viewer.
    for side in (-1, 1):
        for row in range(5):
            machine_y = horizon + 25 + row*110
            machine_width = 40 + row*9
            margin = 174-row*19
            x = margin if side == -1 else width-margin
            oval((x-machine_width-10,machine_y+20,x+machine_width+19,machine_y+58),"#2c2432")
            canvas.create_polygon(x+machine_width,machine_y-65,
                                  x+machine_width+10,machine_y-55,
                                  x+machine_width+10,machine_y+39,
                                  x+machine_width,machine_y+36,
                                  fill="#080f1a",width=0,tags="live")
            box(x-machine_width, machine_y-65, x+machine_width, machine_y+36, "#111c32")
            line((x-machine_width,machine_y+35,x-machine_width,machine_y-65,
                  x+machine_width,machine_y-65),"#718398",2)
            box(x-machine_width+3, machine_y-62, x+machine_width-3, machine_y-54, "#bb5bd2")
            box(x-machine_width+5, machine_y-51, x+machine_width-5, machine_y+3, "#070d16")
            box(x-machine_width+9, machine_y-47, x+machine_width-9, machine_y-1, "#184c68")
            line((x-machine_width+11,machine_y-44,x+machine_width-12,machine_y-44),"#4c9eb2")
            for reel in (-1, 0, 1):
                center = x+reel*machine_width*.5
                box(center-8, machine_y-37, center+8, machine_y-12, "#8eb8b9")
                box(center-7, machine_y-35, center+7, machine_y-15, "#d1dcd1")
                canvas.create_polygon(center,machine_y-31,center+4,machine_y-25,
                                      center,machine_y-19,center-4,machine_y-25,
                                      fill="#b74b5b" if reel else "#c3a04f",width=0,tags="live")
            line((x-machine_width+12,machine_y-42,x-machine_width+24,machine_y-8),
                 "#49788c",2)
            canvas.create_polygon(x-machine_width+4,machine_y+7,x+machine_width-4,machine_y+7,
                                  x+machine_width+2,machine_y+21,x-machine_width-2,machine_y+21,
                                  fill="#35445b",width=0,tags="live")
            box(x-machine_width+4, machine_y+9, x+machine_width-4, machine_y+18, "#4f6b8a")
            for button in (-15, 0, 15):
                oval((x+button-2, machine_y+11, x+button+2, machine_y+15), "#f5c765")
            oval((x-21, machine_y+34, x+21, machine_y+51), "#392b4a", "#79526c", 2)
            line((x, machine_y+50, x, machine_y+77), "#353043", 6)
            oval((x-17,machine_y+72,x+17,machine_y+80),"#555268")
            if row in (0, 2, 4):
                # Seen from behind, seated guests lean toward the slot controls.
                skin = ("#d6a77f", "#98674b", "#bf895f")[row//2]
                shirt = ("#7c578c", "#657f9c", "#a56e52")[(row//2+(side == 1)) % 3]
                scale = 1 + row*.09
                seat_y = machine_y+43
                canvas.create_polygon(
                    x-13*scale, seat_y-7, x+13*scale, seat_y-7,
                    x+19*scale, seat_y+10*scale, x+9*scale, seat_y+15*scale,
                    x-11*scale, seat_y+14*scale, x-19*scale, seat_y+7*scale,
                    fill="#252b40", width=0, tags="live")
                for direction in (-1, 1):
                    line((x+direction*10*scale, seat_y+9*scale,
                          x+direction*15*scale, seat_y+25*scale,
                          x+direction*19*scale, seat_y+26*scale), "#252b40", 7*scale)
                canvas.create_polygon(
                    x-12*scale, seat_y-29*scale, x+12*scale, seat_y-29*scale,
                    x+16*scale, seat_y+5*scale, x-16*scale, seat_y+5*scale,
                    fill=shirt, width=0, tags="live")
                line((x-5*scale,seat_y-25*scale,x-8*scale,seat_y-4*scale),
                     "#b298ac",1)
                line((x+10*scale,seat_y-24*scale,x+13*scale,seat_y+1*scale),
                     "#453d50",2)
                box(x-4*scale,seat_y-31*scale,x+4*scale,seat_y-27*scale,skin)
                for direction in (-1, 1):
                    line((x+direction*11*scale, seat_y-23*scale,
                          x+direction*23*scale, seat_y-16*scale,
                          x+direction*20*scale, machine_y+15), shirt, 6*scale)
                    oval((x+direction*20*scale-3, machine_y+11,
                          x+direction*20*scale+3, machine_y+17), skin)
                oval((x-9*scale, seat_y-47*scale, x+9*scale, seat_y-27*scale), skin)
                oval((x-9*scale, seat_y-48*scale, x+9*scale, seat_y-33*scale),
                     "#49392f" if row != 2 else "#b0a192")
                line((x-6*scale,seat_y-44*scale,x-3*scale,seat_y-46*scale,
                      x+3*scale,seat_y-46*scale),"#77604a" if row != 2 else "#d1c6b0",2)
