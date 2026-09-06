"""Entity classes for Terminal Shooter."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    ch: str = "|"
    color: int = 1
    dmg: int = 1
    friendly: bool = True
    homing: bool = False
    target: object = None

    def update(self, dt: float, w: int, h: int) -> bool:
        if self.homing and self.target is not None and getattr(self.target, "alive", False):
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            dist = math.hypot(dx, dy) or 1.0
            speed = math.hypot(self.vx, self.vy) or 1.0
            self.vx += (dx / dist) * speed * 0.06
            self.vy += (dy / dist) * speed * 0.06
            norm = math.hypot(self.vx, self.vy) or 1.0
            self.vx = self.vx / norm * speed
            self.vy = self.vy / norm * speed
        self.x += self.vx * dt
        self.y += self.vy * dt
        return 0 <= self.x < w and -1 <= self.y < h + 1


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    ch: str
    color: int = 3

    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0


@dataclass
class PowerUp:
    x: float
    y: float
    kind: str  # "fire", "spread", "laser", "missile", "shield", "bomb", "score"
    vy: float = 6.0

    def update(self, dt: float, h: int) -> bool:
        self.y += self.vy * dt
        return self.y < h + 1


class Enemy:
    """A hostile ship. `pattern` drives its movement; stats scale with wave."""

    def __init__(self, x, y, kind, hp, score, pattern="drift", vx=0.0, vy=6.0,
                 shoots=False, fire_rate=1.4, glyph="v", color=2, w=3, h=1,
                 boss=False):
        self.x = x
        self.y = y
        self.kind = kind
        self.hp = hp
        self.max_hp = hp
        self.score = score
        self.pattern = pattern
        self.vx = vx
        self.vy = vy
        self.shoots = shoots
        self.fire_rate = fire_rate
        self._fire_timer = random.uniform(0, fire_rate)
        self.glyph = glyph
        self.color = color
        self.w = w
        self.h = h
        self.boss = boss
        self.alive = True
        self.t = 0.0
        self.base_x = x
        self.flash = 0.0

    def update(self, dt: float, w: int, h: int, player_x: float) -> bool:
        self.t += dt
        if self.pattern == "drift":
            self.y += self.vy * dt
        elif self.pattern == "sine":
            self.y += self.vy * dt
            self.x = self.base_x + math.sin(self.t * 2.2) * 6
        elif self.pattern == "zigzag":
            self.y += self.vy * dt
            self.x += self.vx * dt
            if self.x < 2 or self.x > w - 3:
                self.vx = -self.vx
        elif self.pattern == "dive":
            self.y += self.vy * dt
            self.x += (player_x - self.x) * dt * 0.5
        elif self.pattern == "hover":
            if self.y < 6:
                self.y += self.vy * dt
            else:
                self.x = self.base_x + math.sin(self.t * 1.1) * 10
        elif self.pattern == "boss_entry":
            if self.y < 4:
                self.y += self.vy * dt
            else:
                self.pattern = "boss_move"
        elif self.pattern == "boss_move":
            self.x = self.base_x + math.sin(self.t * 0.8) * (w / 2 - self.w)
        if self.flash > 0:
            self.flash -= dt
        self.x = max(1, min(w - self.w - 1, self.x))
        return self.y < h + self.h + 1

    def hit(self, dmg: int) -> bool:
        self.hp -= dmg
        self.flash = 0.08
        if self.hp <= 0:
            self.alive = False
            return True
        return False
