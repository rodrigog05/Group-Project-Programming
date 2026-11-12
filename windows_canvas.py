"""Small retained canvas backed by Windows GDI/GDI+, with a Tk fallback.

Only the world viewport uses this backend. Tk continues to own the window,
menus, notifications and minimap. No additional Python packages are required.
"""
import ctypes as ct
from collections import OrderedDict
from pathlib import Path
import sys
import tkinter as tk


class Point(ct.Structure):
    _fields_ = [("x", ct.c_float), ("y", ct.c_float)]


class Rect(ct.Structure):
    _fields_ = [("x", ct.c_float), ("y", ct.c_float), ("width", ct.c_float), ("height", ct.c_float)]


class Startup(ct.Structure):
    _fields_ = [("version", ct.c_uint), ("callback", ct.c_void_p),
                ("background_thread", ct.c_int), ("external_codecs", ct.c_int)]


class BitmapHeader(ct.Structure):
    _fields_ = [("size", ct.c_uint), ("width", ct.c_int), ("height", ct.c_int),
                ("planes", ct.c_ushort), ("bits", ct.c_ushort), ("compression", ct.c_uint),
                ("image_size", ct.c_uint), ("xppm", ct.c_int), ("yppm", ct.c_int),
                ("used", ct.c_uint), ("important", ct.c_uint)]


def checked(status):
    if status:
        raise OSError(f"Windows graphics error {status}")


class Bitmap:
    def __init__(self, api, bitmap, width, height):
        self.api, self.bitmap = api, bitmap
        self._width, self._height = width, height
        self.dc = api.CreateCompatibleDC(None)
        if not self.dc:
            api.DeleteObject(bitmap)
            raise OSError("Could not allocate bitmap context")
        self.previous = api.SelectObject(self.dc, bitmap)

    def width(self):
        return self._width

    def height(self):
        return self._height

    def close(self):
        if self.dc:
            self.api.SelectObject(self.dc, self.previous)
            self.api.DeleteObject(self.bitmap)
            self.api.DeleteDC(self.dc)
            self.dc = None


class Graphics:
    def __init__(self):
        self.gdi = ct.WinDLL("gdi32", use_last_error=True)
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.plus = ct.WinDLL("gdiplus", use_last_error=True)
        p, i, f, u = ct.c_void_p, ct.c_int, ct.c_float, ct.c_uint
        def bind(dll, name, result, *args):
            func = getattr(dll, name)
            func.restype, func.argtypes = result, args
            setattr(self, name, func)
        bind(self.user, "GetDC", p, p)
        bind(self.user, "ReleaseDC", i, p, p)
        bind(self.user, "GetWindowLongW", ct.c_long, p, i)
        bind(self.user, "SetWindowLongW", ct.c_long, p, i, ct.c_long)
        bind(self.gdi, "CreateCompatibleDC", p, p)
        bind(self.gdi, "CreateCompatibleBitmap", p, p, i, i)
        bind(self.gdi, "SelectObject", p, p, p)
        bind(self.gdi, "DeleteObject", i, p)
        bind(self.gdi, "DeleteDC", i, p)
        bind(self.gdi, "BitBlt", i, p, i, i, i, i, p, i, i, u)
        bind(self.gdi, "PatBlt", i, p, i, i, i, i, u)
        bind(self.gdi, "CreateDIBSection", p, p, ct.POINTER(BitmapHeader), u, ct.POINTER(p), p, u)
        bind(ct.WinDLL("msimg32"), "AlphaBlend", i, p, i, i, i, i, p, i, i, i, i, u)
        specs = {
            "GdiplusStartup": (ct.POINTER(ct.c_size_t), ct.POINTER(Startup), p),
            "GdipCreateBitmapFromFile": (ct.c_wchar_p, ct.POINTER(p)),
            "GdipCreateHBITMAPFromBitmap": (p, ct.POINTER(p), u),
            "GdipCreateBitmapFromScan0": (i, i, i, i, p, ct.POINTER(p)),
            "GdipGetImageGraphicsContext": (p, ct.POINTER(p)),
            "GdipDisposeImage": (p,),
            "GdipCreateFromHDC": (p, ct.POINTER(p)), "GdipDeleteGraphics": (p,),
            "GdipSetSmoothingMode": (p, i), "GdipSetTextRenderingHint": (p, i),
            "GdipCreateSolidFill": (u, ct.POINTER(p)), "GdipDeleteBrush": (p,),
            "GdipCreatePen1": (u, f, i, ct.POINTER(p)), "GdipDeletePen": (p,),
            "GdipSetPenStartCap": (p, i), "GdipSetPenEndCap": (p, i),
            "GdipFillRectangle": (p, p, f, f, f, f), "GdipDrawRectangle": (p, p, f, f, f, f),
            "GdipFillEllipse": (p, p, f, f, f, f), "GdipDrawEllipse": (p, p, f, f, f, f),
            "GdipFillPie": (p, p, f, f, f, f, f, f), "GdipDrawArc": (p, p, f, f, f, f, f, f),
            "GdipFillPolygon": (p, p, ct.POINTER(Point), i, i),
            "GdipDrawPolygon": (p, p, ct.POINTER(Point), i),
            "GdipFillClosedCurve2": (p, p, ct.POINTER(Point), i, f, i),
            "GdipDrawClosedCurve2": (p, p, ct.POINTER(Point), i, f),
            "GdipDrawLines": (p, p, ct.POINTER(Point), i),
            "GdipCreateFontFamilyFromName": (ct.c_wchar_p, p, ct.POINTER(p)),
            "GdipDeleteFontFamily": (p,), "GdipCreateFont": (p, f, i, i, ct.POINTER(p)),
            "GdipDeleteFont": (p,), "GdipCreateStringFormat": (i, i, ct.POINTER(p)),
            "GdipSetStringFormatAlign": (p, i), "GdipSetStringFormatLineAlign": (p, i),
            "GdipDeleteStringFormat": (p,),
            "GdipDrawString": (p, ct.c_wchar_p, i, p, ct.POINTER(Rect), p, p),
        }
        for name, args in specs.items():
            bind(self.plus, name, i, *args)
        bind(self.plus, "GdiplusShutdown", None, ct.c_size_t)
        self.token = ct.c_size_t()
        checked(self.GdiplusStartup(ct.byref(self.token), ct.byref(Startup(1, None, 0, 0)), None))
        self.brushes, self.pens, self.fonts, self.formats = {}, {}, {}, {}
        self.family = p()
        try:
            checked(self.GdipCreateFontFamilyFromName("Segoe UI", None, ct.byref(self.family)))
        except Exception:
            self.close()
            raise
        self.timer_active = False
        try:
            self.winmm = ct.WinDLL("winmm")
            self.winmm.timeBeginPeriod.argtypes = self.winmm.timeEndPeriod.argtypes = (ct.c_uint,)
            self.timer_active = self.winmm.timeBeginPeriod(1) == 0
        except (OSError, AttributeError):
            pass

    def bitmap(self, path):
        image, bitmap = ct.c_void_p(), ct.c_void_p()
        checked(self.GdipCreateBitmapFromFile(str(Path(path).resolve()), ct.byref(image)))
        try:
            checked(self.GdipCreateHBITMAPFromBitmap(image, ct.byref(bitmap), 0xff000000))
        finally:
            self.GdipDisposeImage(image)
        with open(path, "rb") as stream:
            header = stream.read(24)
        return Bitmap(self, bitmap, int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big"))

    def color(self, value):
        return 0xff000000 | int(value.lstrip("#"), 16)

    def brush(self, color):
        if color not in self.brushes:
            handle = ct.c_void_p()
            checked(self.GdipCreateSolidFill(self.color(color), ct.byref(handle)))
            self.brushes[color] = handle
        return self.brushes[color]

    def pen(self, color, width, rounded):
        key = color, width, rounded
        if key not in self.pens:
            handle = ct.c_void_p()
            checked(self.GdipCreatePen1(self.color(color), width, 2, ct.byref(handle)))
            if rounded:
                self.GdipSetPenStartCap(handle, 2)
                self.GdipSetPenEndCap(handle, 2)
            self.pens[key] = handle
        return self.pens[key]

    def text(self, graphics, options, x, y):
        font = options.get("font", ("Segoe UI", 10))
        size = abs(font[1]) if font[1] < 0 else font[1]*4/3
        style = int("bold" in font[2:])
        key = size, style
        if key not in self.fonts:
            handle = ct.c_void_p()
            checked(self.GdipCreateFont(self.family, size, style, 2, ct.byref(handle)))
            self.fonts[key] = handle
        anchor = options.get("anchor", "center")
        align = {"w": 0, "center": 1, "e": 2}.get(anchor, 0)
        if align not in self.formats:
            handle = ct.c_void_p()
            checked(self.GdipCreateStringFormat(0, 0, ct.byref(handle)))
            self.GdipSetStringFormatAlign(handle, align)
            self.GdipSetStringFormatLineAlign(handle, 1)
            self.formats[align] = handle
        rect = Rect(x-align*500, y-500, 1000, 1000)
        value = options.get("text", "")
        checked(self.GdipDrawString(graphics, value, -1, self.fonts[key], ct.byref(rect),
                                   self.formats[align], self.brush(options.get("fill", "#000000"))))

    def close(self):
        if getattr(self, "timer_active", False):
            self.winmm.timeEndPeriod(1)
            self.timer_active = False
        for values, release in ((self.brushes, self.GdipDeleteBrush), (self.pens, self.GdipDeletePen),
                                (self.fonts, self.GdipDeleteFont), (self.formats, self.GdipDeleteStringFormat)):
            for handle in values.values():
                release(handle)
            values.clear()
        if self.family:
            self.GdipDeleteFontFamily(self.family)
            self.family = None
        if self.token.value:
            self.GdiplusShutdown(self.token)
            self.token.value = 0


class WindowsCanvas(tk.Canvas):
    """The drawing subset used by LivingWorld, stored without Tcl item updates."""
    native_world = True

    def __init__(self, master, **options):
        super().__init__(master, **options)
        try:
            self.graphics = Graphics()
        except Exception:
            tk.Canvas.destroy(self)
            raise
        self.items = {}
        self.groups, self.cached_groups, self.dirty = {}, {}, set()
        self.sprite_cache = OrderedDict()
        self.next_item = 0
        self.maps = []
        self.buffer = None
        self.origin = [0, 0]
        self.region = (0, 0, 1, 1)
        self.night = False
        hwnd = self.winfo_id()
        style = self.graphics.GetWindowLongW(hwnd, -16)
        self.graphics.SetWindowLongW(hwnd, -16, style | 0x02000000)
        self.bind("<Expose>", lambda event: self.after_idle(self.present))

    def load_world(self, day, night):
        loaded = []
        try:
            loaded = [self.graphics.bitmap(day)]
            loaded.append(self.graphics.bitmap(night))
        except Exception:
            for bitmap in loaded:
                bitmap.close()
            raise
        for bitmap in self.maps:
            bitmap.close()
        self.maps = loaded
        return tuple(loaded)

    def configure(self, cnf=None, **options):
        if "scrollregion" in options:
            self.region = options.pop("scrollregion")
        if options or cnf is not None:
            return super().configure(cnf, **options)

    config = configure

    def xview_moveto(self, fraction):
        self.origin[0] = round(fraction*self.region[2])

    def yview_moveto(self, fraction):
        self.origin[1] = round(self.region[1]+fraction*(self.region[3]-self.region[1]))

    def _add(self, kind, coords, options):
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)):
            coords = coords[0]
        self.next_item += 1
        tags = options.get("tags", ())
        tags = (tags,) if isinstance(tags, str) else tuple(tags)
        self.items[self.next_item] = [kind, list(coords), dict(options), tags]
        group = tags[0] if tags else self.next_item
        self.groups.setdefault(group, []).append(self.next_item)
        self.dirty.add(group)
        return self.next_item

    def create_rectangle(self, *coords, **options):
        return self._add("rectangle", coords, options)

    def create_oval(self, *coords, **options):
        return self._add("oval", coords, options)

    def create_line(self, *coords, **options):
        return self._add("line", coords, options)

    def create_polygon(self, *coords, **options):
        return self._add("polygon", coords, options)

    def create_arc(self, *coords, **options):
        return self._add("arc", coords, options)

    def create_text(self, *coords, **options):
        return self._add("text", coords, options)

    def find_withtag(self, tag):
        if tag == "all":
            return tuple(self.items)
        if tag in self.items:
            return (tag,)
        if tag in self.groups:
            return tuple(self.groups[tag])
        return tuple(key for key, item in self.items.items() if tag in item[3])

    def _group(self, key):
        return self.items[key][3][0] if self.items[key][3] else key

    def delete(self, *tags):
        if "all" in tags:
            self.items.clear()
            self.groups.clear()
            self.cached_groups.clear()
            self.dirty.clear()
            return
        for tag in tags:
            for key in self.find_withtag(tag):
                group = self._group(key)
                self.groups[group].remove(key)
                if not self.groups[group]:
                    del self.groups[group]
                    self.dirty.discard(group)
                else:
                    self.dirty.add(group)
                self.cached_groups.pop(group, None)
                del self.items[key]

    def coords(self, tag, *coords):
        ids = self.find_withtag(tag)
        if not coords:
            return self.items[ids[0]][1][:] if ids else []
        for key in ids:
            self.items[key][1] = list(coords[0] if len(coords) == 1 else coords)
            self.dirty.add(self._group(key))

    def itemconfigure(self, tag, **options):
        for key in self.find_withtag(tag):
            if any(self.items[key][2].get(name) != value for name, value in options.items()):
                self.dirty.add(self._group(key))
            self.items[key][2].update(options)

    itemconfig = itemconfigure

    def move(self, tag, dx, dy):
        ids = self.find_withtag(tag)
        changed = set()
        for key in ids:
            changed.add(self._group(key))
            coords = self.items[key][1]
            for index in range(0, len(coords), 2):
                coords[index] += dx
                coords[index+1] += dy
        for group in changed:
            if set(ids) == set(self.groups[group]) and group in self.cached_groups:
                self.cached_groups[group][1] += dx
                self.cached_groups[group][2] += dy
            else:
                self.dirty.add(group)

    def scale(self, tag, x, y, sx, sy):
        for key in self.find_withtag(tag):
            self.dirty.add(self._group(key))
            coords = self.items[key][1]
            for index in range(0, len(coords), 2):
                coords[index] = x+(coords[index]-x)*sx
                coords[index+1] = y+(coords[index+1]-y)*sy

    def type(self, tag):
        return self.items[tag][0]

    def _sprite(self, group, items):
        bounds = []
        for kind, coords, options, tags in items:
            if kind == "text":
                font = options.get("font", ("Segoe UI", 10))
                size = abs(font[1]) if font[1] < 0 else font[1]*4/3
                lines = options.get("text", "").split("\n")
                width, height = max(map(len, lines), default=1)*size+16, len(lines)*size*2+8
                anchor = options.get("anchor", "center")
                left = coords[0]-({"w": 0, "center": .5, "e": 1}.get(anchor, 0))*width
                bounds.append((left, coords[1]-height/2, left+width, coords[1]+height/2))
            else:
                bounds.append((min(coords[::2])-5, min(coords[1::2])-5,
                               max(coords[::2])+5, max(coords[1::2])+5))
        left, top = int(min(b[0] for b in bounds))-2, int(min(b[1] for b in bounds))-2
        width = int(max(b[2] for b in bounds)-left)+3
        height = int(max(b[3] for b in bounds)-top)+3
        normalized = [(kind, tuple(round(v-(left if i % 2 == 0 else top), 1) for i, v in enumerate(coords)),
                       options) for kind, coords, options, tags in items]
        signature = tuple((kind, coords, tuple(sorted((k, repr(v)) for k, v in options.items()
                                                     if k not in ("tags", "state"))))
                          for kind, coords, options in normalized)
        if signature not in self.sprite_cache:
            api, bits, image, graphics = self.graphics, ct.c_void_p(), ct.c_void_p(), ct.c_void_p()
            header = BitmapHeader(40, width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
            handle = api.CreateDIBSection(None, ct.byref(header), 0, ct.byref(bits), None, 0)
            if not handle:
                raise OSError("Could not allocate sprite")
            sprite = Bitmap(api, handle, width, height)
            sprite.pixels = bits
            ct.memset(bits, 0, width*height*4)
            try:
                checked(api.GdipCreateBitmapFromScan0(width, height, width*4, 0xe200b, bits, ct.byref(image)))
                checked(api.GdipGetImageGraphicsContext(image, ct.byref(graphics)))
                api.GdipSetSmoothingMode(graphics, 4)
                api.GdipSetTextRenderingHint(graphics, 4)
                for kind, coords, options in normalized:
                    self._paint(graphics, kind, coords, options)
            except Exception:
                sprite.close()
                raise
            finally:
                if graphics:
                    api.GdipDeleteGraphics(graphics)
                if image:
                    api.GdipDisposeImage(image)
            self.sprite_cache[signature] = sprite
        self.sprite_cache.move_to_end(signature)
        self.cached_groups[group] = [signature, left, top]
        self.dirty.discard(group)
        return self.cached_groups[group]

    def present(self):
        if not self.maps or not self.winfo_viewable():
            return
        api, hwnd = self.graphics, self.winfo_id()
        width, height = self.winfo_width(), self.winfo_height()
        window_dc = api.GetDC(hwnd)
        if not window_dc:
            return
        try:
            if self.buffer is None or (self.buffer.width(), self.buffer.height()) != (width, height):
                if self.buffer:
                    self.buffer.close()
                bitmap = api.CreateCompatibleBitmap(window_dc, width, height)
                if not bitmap:
                    raise OSError("Could not allocate world frame")
                self.buffer = Bitmap(api, bitmap, width, height)
            source = self.maps[int(self.night)]
            ox = round(min(max(0, self.origin[0]), max(0, source.width()-width)))
            oy = round(min(max(self.region[1], self.origin[1]), max(self.region[1], source.height()-height)))
            copy_width, copy_height = min(width, source.width()-ox), min(height, source.height()-oy)
            if (copy_width, copy_height) != (width, height):
                api.PatBlt(self.buffer.dc, 0, 0, width, height, 0x00000042)
            api.BitBlt(self.buffer.dc, 0, 0, copy_width, copy_height, source.dc, ox, oy, 0x00cc0020)
            for group, ids in self.groups.items():
                items = [self.items[key] for key in ids if self.items[key][2].get("state") != "hidden"]
                if not items:
                    continue
                cached = self.cached_groups.get(group)
                if group in self.dirty or cached is None or cached[0] not in self.sprite_cache:
                    cached = self._sprite(group, items)
                signature, left, top = cached
                sprite = self.sprite_cache[signature]
                x, y = round(left-ox), round(top-oy)
                if x+sprite.width() < 0 or y+sprite.height() < 0 or x > width or y > height:
                    continue
                self.sprite_cache.move_to_end(signature)
                api.AlphaBlend(self.buffer.dc, x, y, sprite.width(), sprite.height(),
                               sprite.dc, 0, 0, sprite.width(), sprite.height(), 0x01ff0000)
            api.BitBlt(window_dc, 0, 0, width, height, self.buffer.dc, 0, 0, 0x00cc0020)
            while len(self.sprite_cache) > 256:
                self.sprite_cache.popitem(last=False)[1].close()
        finally:
            api.ReleaseDC(hwnd, window_dc)

    def _paint(self, graphics, kind, points, options):
        api = self.graphics
        if kind == "text":
            api.text(graphics, options, *points)
            return
        fill = options.get("fill", "#000000" if kind == "line" else "")
        outline = options.get("outline", "#000000" if kind in ("oval", "rectangle", "arc") else "")
        width = options.get("width", 1)
        if kind == "line":
            outline, fill = fill, ""
        brush = api.brush(fill) if fill else None
        pen = api.pen(outline, width, options.get("capstyle") == "round") if outline and width else None
        if kind in ("rectangle", "oval", "arc"):
            x, y, right, bottom = points
            box = (x, y, max(0, right-x), max(0, bottom-y))
            if kind == "arc":
                box += (-options.get("start", 0), -options.get("extent", 90))
            if brush:
                method = {"rectangle": api.GdipFillRectangle, "oval": api.GdipFillEllipse, "arc": api.GdipFillPie}[kind]
                method(graphics, brush, *box)
            if pen:
                method = {"rectangle": api.GdipDrawRectangle, "oval": api.GdipDrawEllipse, "arc": api.GdipDrawArc}[kind]
                method(graphics, pen, *box)
        else:
            count = len(points)//2
            vertices = (Point*count)(*(Point(points[i], points[i+1]) for i in range(0, len(points), 2)))
            if brush:
                if options.get("smooth"):
                    api.GdipFillClosedCurve2(graphics, brush, vertices, count, .5, 0)
                else:
                    api.GdipFillPolygon(graphics, brush, vertices, count, 0)
            if pen:
                if kind == "line":
                    api.GdipDrawLines(graphics, pen, vertices, count)
                elif options.get("smooth"):
                    api.GdipDrawClosedCurve2(graphics, pen, vertices, count, .5)
                else:
                    api.GdipDrawPolygon(graphics, pen, vertices, count)

    def destroy(self):
        if hasattr(self, "maps"):
            for bitmap in self.maps:
                bitmap.close()
            self.maps.clear()
            for sprite in self.sprite_cache.values():
                sprite.close()
            self.sprite_cache.clear()
            if self.buffer:
                self.buffer.close()
            self.graphics.close()
        super().destroy()


def world_canvas(master, **options):
    if sys.platform == "win32":
        try:
            return WindowsCanvas(master, **options)
        except (OSError, AttributeError):
            pass
    return tk.Canvas(master, **options)
