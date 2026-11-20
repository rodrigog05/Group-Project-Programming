"""Goldenfield block, in coordinates relative to world position (1200, 450)."""
from dataclasses import dataclass
import math

WIDTH, HEIGHT = 576, 260
DOOR = (168, 184)
BUILDINGS = ((80, 80, 256, 184), (340, 80, 516, 184))
COST, CAPACITY = 4, 12


def car_position(elapsed, direction):
    # One-way wrapping lanes from living_world.AmbientActor.position.
    progress = (elapsed * 380 / (WIDTH + 40) + 0.25) % 1
    if direction < 0:
        progress = 1 - progress
    return round(-20 + (WIDTH + 40) * progress)


@dataclass
class Town:
    x: float = 208
    y: float = 210
    cash: int = 60
    wheat: int = 0

    @property
    def at_farm(self):
        return math.dist((self.x, self.y), DOOR) <= 35

    def buy(self):
        if not self.at_farm:
            return "Walk to the marked farm door."
        if self.wheat >= CAPACITY:
            return "Your bag is full."
        if self.cash < COST:
            return "You need $4 for wheat."
        self.cash -= COST
        self.wheat += 1
        return "Bought one wheat for $4."

    def walk(self, dx, dy, seconds):
        length = math.hypot(dx, dy)
        if not length:
            return
        distance = 228 * min(seconds, 0.04) / length
        x = min(WIDTH - 16, max(16, self.x + dx * distance))
        y = min(HEIGHT - 18, max(32, self.y + dy * distance))
        def blocked(x, y):
            return any(l - 10 < x < r + 10 and t - 10 < y < b + 10
                       for l, t, r, b in BUILDINGS)
        if not blocked(x, self.y):
            self.x = x
        if not blocked(self.x, y):
            self.y = y
