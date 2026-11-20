import asyncio
import math
from pathlib import Path
import time

import pygame
from town import CAPACITY, DOOR, HEIGHT, WIDTH, Town, car_position

ASSETS = Path(__file__).parent / "assets"


async def main():
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT + 86))
    pygame.display.set_caption("Foundry Town | Goldenfield Farm")
    font = pygame.font.Font(None, 22)
    small = pygame.font.Font(None, 18)
    scene = pygame.image.load(str(ASSETS / "farm.png")).convert()
    sheet = pygame.image.load(str(ASSETS / "builder.png")).convert_alpha()
    frames = [sheet.subsurface((32*i, 0, 32, 50)) for i in range(9)]
    sprites = {1: frames, -1: [pygame.transform.flip(s, True, False) for s in frames]}
    town = Town()
    held = set()
    message = ""
    elapsed = notice_until = 0
    facing = 1
    last = time.perf_counter()
    while True:
        now = time.perf_counter()
        dt, last = min(now-last, 0.04), now
        elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.WINDOWFOCUSLOST:
                held.clear()
            elif event.type == pygame.KEYUP:
                held.discard(event.key)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_e and event.key not in held:
                    message = town.buy()
                    notice_until = elapsed + 1.5
                held.add(event.key)
        dx = int(bool(held & {pygame.K_d, pygame.K_RIGHT})) - int(bool(held & {pygame.K_a, pygame.K_LEFT}))
        dy = int(bool(held & {pygame.K_s, pygame.K_DOWN})) - int(bool(held & {pygame.K_w, pygame.K_UP}))
        previous = (town.x, town.y)
        town.walk(dx, dy, dt)
        if dx:
            facing = dx
        frame = 1 + int(elapsed * 13 * 8 / math.tau) % 8 if previous != (town.x, town.y) else 0
        screen.fill("#243e43")
        screen.blit(font.render("Foundry Town   /   Goldenfield", True, "#fff1ce"), (12, 10))
        screen.blit(font.render(f"${town.cash}     Wheat {town.wheat}/{CAPACITY}", True, "#ffdc86"), (402, 10))
        screen.blit(scene, (0, 36))
        for lane, direction, color in [(26, 1, "#9b584e"), (43, -1, "#759ca5")]:
            x = car_position(elapsed, direction)
            body = pygame.Rect(x-12, lane+30, 24, 12)
            pygame.draw.rect(screen, "#30444a", body, border_radius=4)
            pygame.draw.rect(screen, color, body.inflate(-2,-2), border_radius=3)
            pygame.draw.rect(screen, "#c1dcda", (x-4, lane+33, 8, 6))
        pygame.draw.circle(screen, "#ffda61", (DOOR[0], DOOR[1]+44), 6, 2)
        screen.blit(sprites[facing][frame], (round(town.x)-16, round(town.y)+4))
        prompt = "E   Buy wheat for $4" if town.at_farm else "Walk to the gold ring at Goldenfield Farm."
        screen.blit(font.render(message if elapsed < notice_until else prompt, True, "#fff1ce"), (12, HEIGHT+41))
        screen.blit(small.render("WASD or arrows to walk     E to trade", True, "#c2d5cb"), (12, HEIGHT+65))
        pygame.display.flip()
        await asyncio.sleep(1/60)


asyncio.run(main())
