"""Progressive difficulty wave director for Terminal Shooter.

Difficulty ramps continuously with score/time (more enemies, faster,
tougher) and every 5th wave is a boss encounter — echoing the
stage-boss cadence of 1942 / Truxton / Raiden.
"""
from __future__ import annotations
import random
from .entities import Enemy

ENEMY_TYPES = [
    # kind, glyph, base_hp, base_score, pattern, shoots
    ("drone", "v", 1, 10, "drift", False),
    ("fighter", "w", 2, 20, "sine", True),
    ("interceptor", "x", 2, 25, "zigzag", True),
    ("bomber", "W", 4, 40, "hover", True),
    ("striker", "V", 3, 35, "dive", True),
]

BOSS_NAMES = [
    "IRON LOCUST", "CRIMSON WYRM", "VOID KRAKEN", "STORM TITAN",
    "OMEGA REAPER", "ABYSS SOVEREIGN",
]


class WaveDirector:
    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.wave_num = 0
        self.spawn_timer = 0.0
        self.wave_time = 0.0
        self.wave_enemy_budget = 0
        self.wave_spawned = 0
        self.in_boss = False
        self.boss_spawned = False
        self.difficulty = 1.0

    def start_next_wave(self):
        self.wave_num += 1
        self.wave_time = 0.0
        self.spawn_timer = 0.0
        self.wave_spawned = 0
        self.difficulty = 1.0 + self.wave_num * 0.14
        self.in_boss = (self.wave_num % 5 == 0)
        self.boss_spawned = False
        if not self.in_boss:
            self.wave_enemy_budget = 6 + self.wave_num * 2
        else:
            self.wave_enemy_budget = 0

    def _spawn_grunt(self) -> Enemy:
        kind, glyph, hp, score, pattern, shoots = random.choice(
            ENEMY_TYPES[: min(len(ENEMY_TYPES), 2 + self.wave_num // 2)]
        )
        d = self.difficulty
        hp = max(1, round(hp * (1 + (d - 1) * 0.5)))
        score = round(score * d)
        x = random.uniform(2, self.w - 4)
        vy = random.uniform(5, 8) * min(1.6, d * 0.7 + 0.5)
        vx = random.uniform(-6, 6) * d
        fire_rate = max(0.5, 1.6 - d * 0.12)
        return Enemy(x, -1, kind, hp, score, pattern=pattern, vx=vx, vy=vy,
                     shoots=shoots, fire_rate=fire_rate, glyph=glyph,
                     color=2 if not shoots else 5)

    def _spawn_boss(self) -> Enemy:
        idx = min((self.wave_num // 5) - 1, len(BOSS_NAMES) - 1)
        name = BOSS_NAMES[max(0, idx)]
        d = self.difficulty
        hp = round(60 * (1 + (self.wave_num / 5 - 1) * 0.6))
        boss = Enemy(self.w / 2 - 3, -6, name, hp, hp * 8, pattern="boss_entry",
                     vy=4.0, shoots=True, fire_rate=max(0.25, 0.9 - d * 0.05),
                     glyph="M", color=1, w=7, h=3, boss=True)
        boss.name = name
        return boss

    def update(self, dt: float, active_enemy_count: int):
        """Return a newly spawned Enemy or None."""
        self.wave_time += dt
        if self.in_boss:
            if not self.boss_spawned:
                self.boss_spawned = True
                return self._spawn_boss()
            return None
        self.spawn_timer -= dt
        if (self.wave_spawned < self.wave_enemy_budget and self.spawn_timer <= 0
                and active_enemy_count < 10):
            self.spawn_timer = max(0.25, 1.1 - self.difficulty * 0.06)
            self.wave_spawned += 1
            return self._spawn_grunt()
        return None

    def wave_complete(self, active_enemy_count: int) -> bool:
        if self.in_boss:
            return self.boss_spawned and active_enemy_count == 0
        return self.wave_spawned >= self.wave_enemy_budget and active_enemy_count == 0
