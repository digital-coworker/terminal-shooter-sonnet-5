"""Weapon system — progressive fire-power upgrades a la classic verticals.

Each pickup bumps the player's weapon level. Levels change bullet
pattern/spread/damage, mirroring the "power capsule" upgrade chains of
Raiden, 1942, TwinBee and Ikaruga.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from .entities import Bullet

MAX_LEVEL = 8


@dataclass
class WeaponState:
    kind: str = "vulcan"   # vulcan -> spread -> laser -> missile chain
    level: int = 1
    shield: int = 0
    bombs: int = 3

    def upgrade(self):
        if self.level < MAX_LEVEL:
            self.level += 1
        if self.level in (3, 6) and self.kind == "vulcan":
            pass  # kind changes are explicit via pickup kind below

    def set_kind(self, kind: str):
        if kind != self.kind:
            self.kind = kind
        else:
            self.upgrade()


def fire(px: float, py: float, weapon: WeaponState, enemies: List) -> List[Bullet]:
    """Return the bullets spawned by one trigger pull, per weapon/level."""
    lvl = weapon.level
    bullets: List[Bullet] = []
    speed = -34.0

    if weapon.kind == "vulcan":
        # Level 1-8: widening twin/triple/quad streams, classic Raiden vulcan.
        if lvl <= 1:
            bullets.append(Bullet(px, py - 1, 0, speed, "!", 6))
        elif lvl == 2:
            bullets.append(Bullet(px - 1, py - 1, 0, speed, "!", 6))
            bullets.append(Bullet(px + 1, py - 1, 0, speed, "!", 6))
        elif lvl <= 4:
            bullets.append(Bullet(px - 1, py - 1, -2, speed, "!", 6))
            bullets.append(Bullet(px, py - 1, 0, speed, "!", 6))
            bullets.append(Bullet(px + 1, py - 1, 2, speed, "!", 6))
        elif lvl <= 6:
            bullets.append(Bullet(px - 2, py - 1, -4, speed, "!", 6))
            bullets.append(Bullet(px - 1, py - 1, -1, speed, "!", 6))
            bullets.append(Bullet(px + 1, py - 1, 1, speed, "!", 6))
            bullets.append(Bullet(px + 2, py - 1, 4, speed, "!", 6))
        else:
            for off in (-3, -1.5, 0, 1.5, 3):
                bullets.append(Bullet(px + off, py - 1, off * 1.6, speed, "!", 6, dmg=2))

    elif weapon.kind == "spread":
        # TwinBee-style wide fan that narrows in damage-per-shot but covers area.
        n = min(3 + lvl // 2, 9)
        for i in range(n):
            frac = (i / (n - 1)) - 0.5 if n > 1 else 0
            bullets.append(Bullet(px, py - 1, frac * 26, speed * 0.9, "*", 5))

    elif weapon.kind == "laser":
        # Ikaruga-style piercing beam; longer/wider as it levels.
        width = min(1 + lvl // 3, 3)
        dmg = 2 + lvl // 2
        for i in range(width):
            off = (i - (width - 1) / 2) * 1.0
            bullets.append(Bullet(px + off, py - 1, off * 0.5, speed * 1.6,
                                   "‖" if width > 1 else "|", 4, dmg=dmg))

    elif weapon.kind == "missile":
        # Mushihimesama-style homing missiles that seek the nearest enemy.
        count = 1 + lvl // 3
        target = min(enemies, key=lambda e: (e.x - px) ** 2 + (e.y - py) ** 2,
                     default=None) if enemies else None
        for i in range(count):
            off = (i - (count - 1) / 2) * 2.0
            bullets.append(Bullet(px + off, py - 1, off, speed * 0.7, "^", 3,
                                   dmg=3, homing=True, target=target))
    return bullets


LEVEL_LABEL = {
    "vulcan": "VULCAN",
    "spread": "SPREAD",
    "laser": "LASER",
    "missile": "MISSILE",
}
