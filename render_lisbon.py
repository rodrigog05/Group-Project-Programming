"""Build antialiased background PNGs. Pillow is used only when rebuilding assets."""
import math
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

from lisbon_scene import LisbonScene, MAP_BOTTOM
from tycoon import SITES, HEIGHT


class Painter:
    def __init__(self, scale=2, viewport=None, world_size=None):
        self.scale_x = scale if viewport is None else viewport[0]/1200*scale
        self.scale_y = scale if viewport is None else viewport[1]/HEIGHT*scale
        self.scale = min(self.scale_x, self.scale_y)
        world_width, world_height = world_size or (1200, MAP_BOTTOM)
        self.image = Image.new("RGB", (round(world_width*self.scale_x), round(world_height*self.scale_y)), "#dfd5bd")
        self.draw = ImageDraw.Draw(self.image, "RGBA")
        self.fonts = {}

    def points(self, coords):
        if len(coords) == 1 and isinstance(coords[0], (tuple, list)):
            coords = coords[0]
        return [(coords[i]*self.scale_x, coords[i+1]*self.scale_y) for i in range(0, len(coords), 2)]

    def skip(self, options):
        return options.get("tags") == "tram"

    def fill(self, options):
        color = options.get("fill")
        if color and options.get("stipple"):
            alpha = {"gray25": 64, "gray50": 128, "gray75": 192}.get(options["stipple"], 64)
            return (*ImageColor.getrgb(color), alpha)
        return color

    def make_night(self, scene):
        self.image = Image.blend(self.image, Image.new("RGB", self.image.size, "#10273d"), .62)
        self.draw = ImageDraw.Draw(self.image, "RGBA")
        scene.night_lighting()

    def create_rectangle(self, *coords, **options):
        if not self.skip(options):
            self.draw.rectangle(self.points(coords), fill=self.fill(options), outline=options.get("outline") or None,
                                width=max(1, round(options.get("width", 1)*self.scale)))

    def create_polygon(self, *coords, **options):
        if not self.skip(options):
            self.draw.polygon(self.points(coords), fill=self.fill(options), outline=options.get("outline") or None)

    def create_oval(self, *coords, **options):
        if not self.skip(options):
            if options.get("tags") == "night_lights" and options.get("stipple"):
                (left, top), (right, bottom) = self.points(coords)
                padding = max(2, round(8*self.scale))
                layer = Image.new("RGBA", (round(right-left)+padding*2+1, round(bottom-top)+padding*2+1))
                ImageDraw.Draw(layer).ellipse((padding, padding, padding+right-left, padding+bottom-top), fill=self.fill(options))
                layer = layer.filter(ImageFilter.GaussianBlur(max(1, 5*self.scale)))
                self.image.paste(layer, (round(left)-padding, round(top)-padding), layer)
                return
            self.draw.ellipse(self.points(coords), fill=self.fill(options), outline=options.get("outline") or None)

    def create_line(self, *coords, **options):
        if self.skip(options):
            return
        points = self.points(coords)
        dx, dy = points[-1][0]-points[0][0], points[-1][1]-points[0][1]
        length = math.hypot(dx/self.scale_x, dy/self.scale_y)
        perpendicular_scale = (math.hypot(dy/self.scale_y*self.scale_x, dx/self.scale_x*self.scale_y)/length
                               if length else self.scale)
        width = max(1, round(options.get("width", 1)*perpendicular_scale))
        dash = options.get("dash")
        if dash:
            on, off = dash[0]*self.scale, dash[1]*self.scale
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                length = math.hypot(x2-x1, y2-y1)
                cursor = 0
                while cursor < length:
                    end = min(length, cursor+on)
                    self.draw.line((x1+(x2-x1)*cursor/length, y1+(y2-y1)*cursor/length,
                                    x1+(x2-x1)*end/length, y1+(y2-y1)*end/length),
                                   fill=self.fill(options), width=width)
                    cursor += on+off
        else:
            self.draw.line(points, fill=self.fill(options), width=width, joint="curve")

    def label(self, x, y, text, size=10, color="#304b54", bold=False, anchor="w", tag="city"):
        if tag == "tram":
            return
        key = size, bold
        if key not in self.fonts:
            font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
            candidates = (Path("C:/Windows/Fonts")/font_name,
                          Path("/usr/share/fonts/truetype/dejavu")/("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"))
            font_path = next((p for p in candidates if p.exists()), None)
            self.fonts[key] = ImageFont.truetype(str(font_path), round(size*4/3*self.scale)) if font_path else ImageFont.load_default()
        self.draw.text((x*self.scale_x, y*self.scale_y), text, fill=color, font=self.fonts[key],
                       anchor={"w": "lm", "e": "rm", "center": "mm"}.get(anchor, "lm"))


def build():
    painter = Painter()
    scene = LisbonScene(SimpleNamespace(canvas=painter, label=painter.label), SITES)
    day_image = painter.image.copy()
    painter.make_night(scene)
    night_image = painter.image.copy()
    directory = Path(__file__).parent / "assets"
    directory.mkdir(exist_ok=True)
    for factor in range(4, 21):
        scale = factor/10
        image = day_image.resize((round(1200*scale), round(MAP_BOTTOM*scale)), Image.Resampling.LANCZOS)
        image.save(directory/f"lisbon_{factor*10:03}.png", optimize=True)
        night_image.resize(image.size, Image.Resampling.LANCZOS).save(directory/f"lisbon_{factor*10:03}_night.png", optimize=True)
    print("Built 17 Lisbon background sizes")
    screens = {(1280, 720), (1280, 800), (1366, 768), (1440, 900), (1536, 864),
               (1600, 900), (1920, 1080), (1920, 1200), (2560, 1080), (2560, 1440),
               (3440, 1440), (3840, 2160)}
    viewports = screens | {(round(w*.85), round(h*.85)) for w, h in screens}
    for width, height in sorted(viewports):
        painter = Painter(viewport=(width, height))
        scene = LisbonScene(SimpleNamespace(canvas=painter, label=painter.label), SITES)
        image = painter.image.resize((width, round(MAP_BOTTOM*height/HEIGHT)), Image.Resampling.LANCZOS)
        image.save(directory/f"lisbon_view_{width}x{height}.png", optimize=True)
        painter.make_night(scene)
        painter.image.resize(image.size, Image.Resampling.LANCZOS).save(directory/f"lisbon_view_{width}x{height}_night.png", optimize=True)
    print(f"Built {len(viewports)} widescreen backgrounds")


if __name__ == "__main__":
    build()
