"""Retained product labels for owned properties on the cached city map."""
import businesses


class BusinessSigns:
    def __init__(self, canvas, sites, zoom, font):
        self.canvas, self.sites, self.zoom, self.font = canvas, tuple(sites), zoom, font
        self.signs = {}

    def paint(self, town, camera, night=False):
        owned = getattr(town, "businesses", {}).get("owned", {})
        if not owned and not self.signs:
            return
        color, background = ("#fff0c9", "#213d4a") if night else ("#f2e7cb", "#314c55")
        for index, site in enumerate(self.sites):
            record = owned.get(site.name)
            visible = record is not None and camera.sees(site.x+88, site.y+95, 140)
            sign = self.signs.get(site.name)
            if not visible:
                if sign is not None and sign["visible"]:
                    self.canvas.itemconfigure(sign["tag"], state="hidden")
                    sign["visible"] = False
                continue
            trade = record["trade"]
            left = (businesses.MATERIAL_NAMES[trade]+" →") if site.role == "FACTORY" else "OWNED · B"
            right = businesses.PRODUCT_NAMES[trade]
            style = left, right, color, background
            if sign is None:
                tag = f"business_sign_{index}"
                rectangles = []
                # Preserve the painted doorway between x+76 and x+100.
                for x1, x2 in ((site.x+13, site.x+76), (site.x+100, site.x+164)):
                    rectangles.append(self.canvas.create_rectangle(
                        x1*self.zoom, (site.y+87)*self.zoom, x2*self.zoom, (site.y+101)*self.zoom,
                        fill=background, width=0, tags=tag))
                labels = []
                for x, text in ((site.x+15, left), (site.x+102, right)):
                    labels.append(self.canvas.create_text(
                        x*self.zoom, (site.y+95)*self.zoom, text=text, anchor="w", fill=color,
                        font=(self.font, -max(8, round(7*self.zoom)), "bold"), tags=tag))
                sign = self.signs[site.name] = dict(tag=tag, rectangles=rectangles, labels=labels,
                                                   style=style, visible=True)
            else:
                if sign["style"] != style:
                    self.canvas.itemconfigure(sign["labels"][0], text=left, fill=color)
                    self.canvas.itemconfigure(sign["labels"][1], text=right, fill=color)
                    for item in sign["rectangles"]:
                        self.canvas.itemconfigure(item, fill=background)
                    sign["style"] = style
                if not sign["visible"]:
                    self.canvas.itemconfigure(sign["tag"], state="normal")
                    sign["visible"] = True
