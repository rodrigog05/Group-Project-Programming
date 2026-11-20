"""Pygbag entry point. All gameplay is local to this browser."""

import asyncio
import sys
import time

import pygame
from controller import Session
from storage import Storage
from view import H, View, W


async def main():
    pygame.display.init()
    pygame.font.init()
    view = View(pygame.display.set_mode((W, H)))
    pygame.display.set_caption("Foundry Town · Core Edition")
    game = Session(Storage.for_browser())
    view.draw(game)
    if sys.platform == "emscripten":
        import platform

        splash = platform.window.document.getElementById("core-splash")
        if splash:
            splash.hidden = True
    last = time.monotonic()
    while True:
        now = time.monotonic()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.save()
                pygame.quit()
                return
            if event.type == pygame.WINDOWFOCUSLOST:
                game.focus = False
                game.keys.clear()
                game.save()
            elif event.type == pygame.WINDOWFOCUSGAINED:
                game.focus = True
                last = now
            elif event.type == pygame.KEYDOWN:
                game.key(pygame.key.name(event.key))
            elif event.type == pygame.KEYUP:
                key = pygame.key.name(event.key)
                game.keys.discard(key)
                if key in ("w", "a", "s", "d", "up", "down", "left", "right"):
                    game.save()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, key in view.buttons:
                    if rect.collidepoint(event.pos):
                        game.key(key)
                        game.keys.discard(key)
                        break
        game.tick(now - last)
        last = now
        view.draw(game)
        await asyncio.sleep(0)


asyncio.run(main())
