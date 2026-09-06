"""Lightweight tests for Terminal Shooter core logic (no curses needed).

Run with: python3 -m pytest tests/  (or just: python3 tests/test_core.py)
"""
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shooter.entities import Bullet, Enemy, Particle, PowerUp
from shooter.weapons import WeaponState, fire, MAX_LEVEL
from shooter.waves import WaveDirector


class TestBullet(unittest.TestCase):
    def test_moves_and_expires(self):
        b = Bullet(5, 5, 0, -10, "!", 1)
        alive = b.update(1.0, 20, 20)
        self.assertAlmostEqual(b.y, -5)
        self.assertFalse(alive)  # off top of screen

    def test_stays_in_bounds(self):
        b = Bullet(5, 5, 0, -1, "!", 1)
        alive = b.update(0.1, 20, 20)
        self.assertTrue(alive)


class TestWeapons(unittest.TestCase):
    def test_vulcan_widens_with_level(self):
        w = WeaponState(kind="vulcan", level=1)
        b1 = fire(10, 10, w, [])
        w.level = 8
        b8 = fire(10, 10, w, [])
        self.assertGreater(len(b8), len(b1))

    def test_kind_switch_does_not_reset_level_progress(self):
        w = WeaponState(kind="vulcan", level=3)
        w.set_kind("spread")
        self.assertEqual(w.kind, "spread")

    def test_missile_homes_on_nearest_enemy(self):
        w = WeaponState(kind="missile", level=4)
        e = Enemy(10, 5, "drone", 1, 10)
        bullets = fire(10, 20, w, [e])
        self.assertTrue(any(b.homing for b in bullets))

    def test_level_capped(self):
        w = WeaponState(level=MAX_LEVEL)
        w.upgrade()
        self.assertEqual(w.level, MAX_LEVEL)


class TestEnemy(unittest.TestCase):
    def test_hit_reduces_hp_and_kills(self):
        e = Enemy(5, 5, "drone", 2, 10)
        self.assertFalse(e.hit(1))
        self.assertTrue(e.alive)
        self.assertTrue(e.hit(1))
        self.assertFalse(e.alive)

    def test_sine_pattern_moves_down(self):
        e = Enemy(5, 5, "fighter", 2, 10, pattern="sine", vy=6)
        y0 = e.y
        e.update(1.0, 40, 30, player_x=5)
        self.assertGreater(e.y, y0)


class TestWaveDirector(unittest.TestCase):
    def test_boss_every_fifth_wave(self):
        wd = WaveDirector(40, 30)
        for i in range(1, 11):
            wd.start_next_wave()
            self.assertEqual(wd.in_boss, i % 5 == 0)

    def test_difficulty_increases(self):
        wd = WaveDirector(40, 30)
        wd.start_next_wave()
        d1 = wd.difficulty
        for _ in range(9):
            wd.start_next_wave()
        self.assertGreater(wd.difficulty, d1)

    def test_spawns_grunts_up_to_budget(self):
        random.seed(0)
        wd = WaveDirector(40, 30)
        wd.start_next_wave()
        spawned = 0
        for _ in range(2000):
            e = wd.update(0.05, active_enemy_count=0)
            if e:
                spawned += 1
            if spawned >= wd.wave_enemy_budget:
                break
        self.assertEqual(spawned, wd.wave_enemy_budget)


class TestPowerUpAndParticle(unittest.TestCase):
    def test_powerup_falls(self):
        p = PowerUp(5, 5, "shield")
        alive = p.update(1.0, 30)
        self.assertGreater(p.y, 5)
        self.assertTrue(alive)

    def test_particle_expires(self):
        p = Particle(1, 1, 0, 0, 0.05, "*")
        p.update(0.1)
        self.assertLessEqual(p.life, 0)


if __name__ == "__main__":
    unittest.main()
