"""Code-drawn Oriente canopy, shared by the street view and the landmark map.

Run this file to rebuild the two SVG assets. No image libraries are required.
"""
from pathlib import Path

BOUNDS = (1780, 150, 250, 132)


def station_svg(night=False):
    ground = "#5c696d" if night else "#dad7bf"
    steel = "#f2cc86" if night else "#f3f2df"
    ribs = "#cda266" if night else "#96aaa4"
    glass = "#546963" if night else "#c1d9d1"
    shade = "#33474d" if night else "#77948f"
    road = "#354650" if night else "#747a77"
    curb = "#4e5a60" if night else "#b4ac98"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 750 396">'
             f'<rect width="750" height="396" fill="{ground}"/>'
             # Restore the road edges obscured by the old baked-in station.
             f'<path d="M0 0H28.5V396H0ZM721.5 0H750V396H721.5Z" fill="{road}"/>'
             f'<path d="M28.5 0H43.5V379.5H28.5ZM706.5 0H721.5V379.5H706.5Z" fill="{curb}"/>'
             f'<path d="M28.5 379.5H721.5V394.5H28.5Z" fill="{curb}"/>'
             f'<path d="M0 394.5H750V396H0Z" fill="{road}"/>'
             # All building geometry stays inside the plot, with space for its name.
             '<g transform="translate(60 30) scale(.875)">'
             f'<path d="M32 0H688V64H720V287H688V300H32V287H0V64H32Z" fill="{ground}"/>',
             '<ellipse cx="365" cy="269" rx="344" ry="20" fill="#243b40" opacity=".2"/>',
             f'<path d="M8 185 42 154H706V240H8Z" fill="{shade}"/>']
    # Railway beds and raised platforms are visible through the skeletal roof.
    for y in (171, 190, 209):
        parts.append(f'<path d="M15 {y}H707" stroke="#354b50" stroke-width="9"/>')
        for x in range(20, 707, 15):
            parts.append(f'<path d="M{x} {y-5}v10" stroke="#71817b" stroke-width="2"/>')
        parts.append(f'<path d="M16 {y-4}H706M16 {y+4}H706" stroke="#bac7bf" stroke-width="1.5"/>')
    # Rear columns and a second roof edge give the canopy depth.
    for x in range(51, 680, 97):
        parts.append(f'<path d="M{x+24} 194V135Q{x+24} 83 {x-20} 66M{x+24} 135Q{x+24} 83 {x+72} 66" '
                     f'fill="none" stroke="{ribs}" stroke-width="3"/>')
    for x in range(51, 680, 97):
        parts.append(f'<path d="M{x-48} 104 {x} 57 {x+25} 22 {x-23} 69Z" fill="{glass}" '
                     f'stroke="{steel}" stroke-width="2"/>')
        parts.append(f'<path d="M{x} 57 {x+48} 104 {x+73} 69 {x+25} 22Z" fill="{shade}" '
                     f'stroke="{steel}" stroke-width="2"/>')
        # Fine roof ribs meet the ridge instead of forming solid triangular sheds.
        for step in range(1, 9):
            t = step / 9
            for sign in (-1, 1):
                a, b = x+sign*48*t, 57+47*t
                parts.append(f'<path d="M{a:.1f} {b:.1f}l25-35" stroke="{steel}" '
                             'stroke-width="1.2" opacity=".85"/>')
        for t in (.25, .5, .75):
            parts.append(f'<path d="M{x-48+25*t} {104-35*t} {x+25*t} {57-35*t} '
                         f'{x+48+25*t} {104-35*t}" fill="none" stroke="{ribs}" stroke-width="1"/>')
        # The characteristic tree-like, flared steel supports.
        parts.append(f'<path d="M{x-3} 211 {x-3} 158Q{x-7} 122 {x-48} 104M{x+3} 211V158'
                     f'Q{x+7} 122 {x+48} 104" fill="none" stroke="{steel}" stroke-width="3.5"/>')
        for dx in (-37, -25, -13, 0, 13, 25, 37):
            top = 57 + abs(dx)*47/48
            parts.append(f'<path d="M{x} 169Q{x+dx*.18:.1f} 120 {x+dx} {top:.1f}" '
                         f'fill="none" stroke="{steel}" stroke-width="1.3"/>')
        parts.append(f'<path d="M{x-8} 211h16" stroke="{steel}" stroke-width="4"/>')
        if night:
            parts.append(f'<ellipse cx="{x}" cy="191" rx="25" ry="30" fill="#ffc96e" opacity=".13"/>')
            parts.append(f'<circle cx="{x}" cy="207" r="3" fill="#fff1b0"/>')
    # Glazed platform balustrade and the concrete viaduct below it.
    parts.append(f'<path d="M8 201H712V230H8Z" fill="{glass}" fill-opacity=".4" '
                 f'stroke="{steel}" stroke-width="2"/>')
    for x in range(15, 712, 20):
        parts.append(f'<path d="M{x} 201v29" stroke="{steel}" stroke-width="1.2"/>')
    parts.append(f'<path d="M8 216H712" stroke="{steel}" stroke-width="1"/>')
    parts.append(f'<path d="M5 231H715V243H5Z" fill="{shade}" stroke="{ribs}" stroke-width="2"/>')
    for x in (12, 187, 362, 537):
        parts.append(f'<path d="M{x} 244h165v31H{x}Z" fill="#35484b"/>')
        parts.append(f'<path d="M{x} 275Q{x+82} 211 {x+165} 275" fill="none" '
                     f'stroke="{ribs}" stroke-width="8"/>')
    # Central glass entrance / footbridge, inspired by the photograph's foreground.
    parts.append(f'<path d="M317 246h80l58 52H259Z" fill="{glass}" stroke="{steel}" stroke-width="2"/>')
    for x in (278, 305, 332, 359, 386, 413, 440):
        parts.append(f'<path d="M359 247 {x} 298" stroke="{ribs}" stroke-width="1"/>')
    for y in (259, 276, 293):
        spread = (y-246)*1.12 + 40
        parts.append(f'<path d="M{359-spread:.1f} {y}H{359+spread:.1f}" stroke="{steel}" stroke-width="1"/>')
    parts.append('</g><rect x="110" y="323" width="530" height="39" rx="7" fill="#304b54"/>')
    parts.append('<text x="375" y="350" text-anchor="middle" font-family="Arial,sans-serif" '
                 'font-size="26" font-weight="700" letter-spacing="1" fill="#fff3d4">GARE DO ORIENTE</text></svg>')
    return ''.join(parts)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "street"
    for mode in ("day", "night"):
        (root / f"oriente_{mode}.svg").write_text(station_svg(mode == "night"), encoding="utf-8")
