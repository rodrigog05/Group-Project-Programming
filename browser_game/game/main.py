"""Foundry Town's pygame frontend. prepare.py supplies the shared desktop model."""
import asyncio
from functools import lru_cache, partial
import json
import math
from pathlib import Path
import sys
import time

import pygame
import tycoon as model
from actors import Camera
from interiors import INTERIOR_ROLES, actions_for, vendor_greeting
from places_menu import directory_entries
from ferry import nearby_pier, ride_ferry
from prayer import at_monastery
from services import service_options

ASSETS = Path(__file__).parent / "assets"
WEB = sys.platform == "emscripten"
SAVE_KEY = "foundry-town.progress.v1"
W, H = 800, 540
GOLD, PAPER, DARK = "#ffd681", "#f4eee0", "#20383c"


@lru_cache(maxsize=48)
def picture(name):
    return pygame.image.load(str(ASSETS / name)).convert_alpha()


@lru_cache(maxsize=16)
def font(size):
    return pygame.font.Font(None, size)


def label(screen, text, pos, size=21, color=PAPER, width=0):
    x, y = pos
    face = font(size)
    for paragraph in str(text).splitlines():
        line = ""
        for word in paragraph.split():
            potential = (line+" "+word).strip()
            if width and line and face.size(potential)[0] > width:
                screen.blit(face.render(line, True, color), (x,y))
                y += face.get_linesize()
                line = word
            else:
                line = potential
        screen.blit(face.render(line, True, color), (x,y))
        y += face.get_linesize()
    return y


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((W,H))
        pygame.display.set_caption("Foundry Town")
        self.t = model.Town()
        self.t.x, self.t.y = 1368, 650
        self.started = time.time()
        self.storage = None
        self.warning = ""
        if WEB:
            import platform
            try:
                self.storage = platform.window.localStorage
                raw = self.storage.getItem(SAVE_KEY)
                if raw:
                    self.t, self.started = model.unpack_save(json.loads(str(raw)))
            except Exception:
                self.storage = None
                self.warning = "Save unavailable. This session will not overwrite existing progress."
        self.camera = Camera(W,400,1)
        self.camera.follow(self.t.x,self.t.y,snap=True)
        self.keys = set()
        self.focus = True
        self.panel = None
        self.site = None
        self.reply = ""
        self.buttons = []
        self.page = 0
        self.target = None
        self.minimap = False
        self.music = False
        self.last_save = time.monotonic()
        self.traffic = True
        self.walking = False
        self.context = {}
        self.ambient = self.make_actors()

    def make_actors(self):
        from actors import AmbientActor
        from routes import create_actors
        actors = []
        class Collector:
            def actor(self, kind, start, end, speed, offset, color):
                actors.append((AmbientActor("", start, end, speed, offset, kind), color))
        create_actors(Collector())
        return actors

    def save(self):
        if self.storage is not None:
            try:
                self.storage.setItem(SAVE_KEY,json.dumps(model.pack_save(self.t,self.started)))
            except Exception:
                self.warning = "Browser storage is full or unavailable. Progress could not be saved."
        self.last_save = time.monotonic()

    def toggle_music(self):
        try:
            if self.music:
                pygame.mixer.music.pause()
            else:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(str(ASSETS/"saudade_do_tejo.ogg"))
                pygame.mixer.music.play(-1)
            self.music = not self.music
        except pygame.error as exc:
            self.reply = f"Audio unavailable: {exc}"

    def open(self, panel):
        self.panel, self.page = panel, 0
        self.buttons.clear()
        self.keys.clear()
        self.reply = ""

    def leave(self):
        self.open(None)
        self.site = None
        self.save()

    def enter(self):
        t = self.t
        self.site = t.nearby()
        if self.site:
            self.open(self.site.name)
            if self.site.role in INTERIOR_ROLES:
                self.reply = vendor_greeting(t,self.site)
        elif nearby_pier(t.x,t.y):
            self.open("Ferry")
        elif at_monastery(t):
            self.open("Mosteiro dos Jerónimos")
            t.visit_monastery()
            self.reply = t.message

    def trade(self,key):
        if key in ("e","q"):
            self.t.interact(bulk=key=="q")
        else:
            self.t.buy_eggs(bulk=key=="r")
        self.reply = self.t.message
        self.save()

    def button(self, rect, title, action, primary=False):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, GOLD if primary else "#38585b", rect, border_radius=5)
        label(self.screen,title,(rect.x+7,rect.y+7),19,DARK if primary else PAPER)
        self.buttons.append((rect,action))

    def key(self,key):
        if key == "escape":
            self.leave()
        elif self.panel:
            if self.site and self.site.role in INTERIOR_ROLES:
                if key in [k for _,k in actions_for(self.t,self.site)]:
                    self.trade(key)
            elif key in ("page down","page up"):
                self.page = max(0,self.page+(1 if key=="page down" else -1))
        elif key in ("p","j","b","c","l","f1"):
            self.open({"p":"Places","j":"Journal","b":"Businesses","c":"Contracts","l":"Deliveries","f1":"Settings"}[key])
        elif key=="m":
            self.minimap = not self.minimap
        elif key=="e":
            self.enter()
        elif key in ("q","r","f") and self.t.nearby() and self.t.nearby().role=="SUPPLIER":
            self.trade(key)

    def tick(self,dt):
        t = self.t
        t.sync_market(time.time()-self.started)
        if not self.focus:
            return
        if not t.won or t.milestone_acknowledged:
            model.advance_city(t,dt)
            t.advance_research(dt)
            t.advance_deliveries(dt)
            t.advance_contracts(dt)
            t.advance_businesses(dt)
        if t.won and not t.milestone_acknowledged and self.panel!="Cash milestone":
            self.site = None
            self.open("Cash milestone")
        if not self.panel or (self.site and self.site.role in INTERIOR_ROLES):
            t.advance(dt)
        dx = int(bool(self.keys & {"right","d"}))-int(bool(self.keys & {"left","a"}))
        dy = int(bool(self.keys & {"down","s"}))-int(bool(self.keys & {"up","w"}))
        self.walking = False
        if not self.panel:
            previous = t.x,t.y
            t.move(dx,dy,dt)
            self.walking = previous!=(t.x,t.y)
        self.camera.follow(t.x,t.y,dt)
        if time.monotonic()-self.last_save>8:
            self.save()

    def world(self):
        t,s,c = self.t,self.screen,self.camera
        night=t.market_elapsed%model.DAY_SECONDS>=model.DAYLIGHT_SECONDS
        img=picture("world_100_night.png" if night else "world_100_day.png")
        s.blit(img,(0,36),(int(c.x),int(c.y),W,400))
        s.set_clip((0,36,W,400))
        from actors import underground
        for actor,color in self.ambient:
            if actor.kind=="car" and not self.traffic:
                continue
            x,y=actor.position(t.elapsed)
            if not c.sees(x,y) or underground(actor,x,y):
                continue
            x,y=round(x-c.x),round(y-c.y)+36
            if actor.kind=="car":
                pygame.draw.rect(s,color,(x-14,y-7,28,14),border_radius=4)
                pygame.draw.rect(s,"#aac5c8",(x-6,y-4,12,7))
            elif actor.kind=="pedestrian":
                pygame.draw.ellipse(s,color,(x-4,y-6,8,12))
                pygame.draw.circle(s,"#dfbb93",(x,y-9),3)
            elif actor.kind=="boat":
                pygame.draw.polygon(s,color,[(x-22,y-7),(x+16,y-7),(x+28,y),(x+16,y+7),(x-22,y+7)])
                pygame.draw.rect(s,"#abbec2",(x-7,y-4,14,8))
            else:
                pygame.draw.line(s,color,(x-6,y),(x+6,y))
        x,y=round(t.x-c.x),round(t.y-c.y)+36
        frame=1+int(t.elapsed*16)%8 if self.walking else 0
        sprite=picture("builder.png").subsurface((32*frame,0,32,50))
        if t.facing<0:
            sprite=pygame.transform.flip(sprite,True,False)
        if t.vehicle:
            pygame.draw.rect(s,"#376a82",(x-22,y-8,44,18),border_radius=5)
        s.blit(sprite,(x-16,y-32))
        if t.power_up is not None:
            _,symbol,color,px,py=model.POWER_UPS[t.power_up]
            label(s,symbol,(px-c.x,py-c.y+26),30,color)
        if self.minimap:
            rect=pygame.Rect(W-184,46,174,125)
            s.blit(miniature(),rect)
            pygame.draw.circle(s,GOLD,(rect.x+int(t.x*174/img.get_width()),rect.y+int(t.y*125/img.get_height())),4)
        s.set_clip(None)
        nearby=t.nearby()
        hint=f"E   Enter {nearby.name}" if nearby else "WASD / arrows to walk     E to enter"
        if not nearby and nearby_pier(t.x,t.y):
            hint="E   Board ferry"
        if at_monastery(t):
            hint="E   Visit Mosteiro dos Jerónimos"
        label(s,hint,(14,444),25,GOLD)
        if self.target:
            from guidance import next_step
            (tx,ty),via=next_step(t.x,t.y,*self.target.destination)
            label(s,f"{self.target.name}   {tx-t.x:+.0f} east   {ty-t.y:+.0f} south",(14,474))
        else:
            label(s,"Goldenfield Farm → Sunrise Bakery → Daily Bread Market",(14,474))
        label(s,"P Places    J Journal    B Businesses    L Deliveries    C Contracts    M Map    F1 Settings",(14,505),18)

    def menu(self):
        t,s=self.t,self.screen
        site=self.site
        if site and site.role in INTERIOR_ROLES:
            trade=t.business_site(site).trade
            img=picture(f"interiors/{site.role.replace(' ','_')}_{trade}.png")
            s.blit(img,(80,36))
            label(s,self.reply,(343,66),20,DARK,190)
            label(s,t.site_status(site),(420,394),16,PAPER,155)
            sprite=picture("builder.png").subsurface((0,0,32,50))
            s.blit(pygame.transform.scale(sprite,(80,125)),(190,302))
            actions=actions_for(t,site)
            for i,(title,key) in enumerate(actions):
                self.button((12+i*155,453,148,36),title,partial(self.trade,key),i==0)
        else:
            options=service_options(self)
            pages=max(1,math.ceil(len(options)/8))
            self.page=min(self.page,pages-1)
            for i,(title,action) in enumerate(options[self.page*8:self.page*8+8]):
                self.button((20,48+i*42,W-40,36),title,action)
            if pages>1:
                for x,title,delta in ((20,"Previous",-1),(160,"Next",1)):
                    self.button((x,392,120,32),title,partial(setattr,self,"page",(self.page+delta)%pages))
                label(s,f"{self.page+1} / {pages}",(300,398))
            label(s,self.reply,(20,434),19,GOLD,740)
        self.button((W-126,H-42,112,32),"Esc  Outside",self.leave)

    def draw(self):
        self.buttons.clear()
        self.screen.fill(DARK)
        if self.panel:
            self.menu()
        else:
            self.world()
        label(self.screen,self.panel or "Foundry Town",(12,8),24,GOLD)
        t=self.t
        label(self.screen,f"Day {t.day}    ${t.cash}    Bag {t.cargo}/{t.carry_capacity}",(530,9),21)
        if self.warning:
            label(self.screen,self.warning,(12,H-25),16,GOLD)
        pygame.display.flip()


@lru_cache(maxsize=1)
def miniature():
    return pygame.transform.smoothscale(picture("world_100_day.png"),(174,125))


async def main():
    pygame.display.init()
    pygame.font.init()
    g=Game()
    last=time.monotonic()
    while True:
        now=time.monotonic()
        dt,last=min(.05,now-last),now
        for e in pygame.event.get():
            if e.type==pygame.QUIT:
                g.save()
                return
            if e.type==pygame.WINDOWFOCUSLOST:
                g.keys.clear()
                g.focus=False
                g.save()
            elif e.type==pygame.WINDOWFOCUSGAINED:
                g.focus=True
            elif e.type==pygame.KEYDOWN:
                key=pygame.key.name(e.key)
                if key not in g.keys:
                    g.key(key)
                    g.keys.add(key)
            elif e.type==pygame.KEYUP:
                g.keys.discard(pygame.key.name(e.key))
            elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                for rect,action in g.buttons:
                    if rect.collidepoint(e.pos):
                        action()
                        g.save()
                        break
        g.tick(dt)
        g.draw()
        await asyncio.sleep(0)


asyncio.run(main())
