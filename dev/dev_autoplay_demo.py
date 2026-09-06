"""Autoplay demo bot used only to record the asciinema cast for the README
and GitHub Pages demo. Not part of the shipped game — a scripted "AI"
plays a real session for ~45s so the recording shows genuine gameplay:
dodging, shooting, picking up power-ups, and reaching a boss fight.
"""
import curses
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shooter.game import Game


def main(stdscr):
    g = Game(stdscr)
    g.audio.enabled = False
    g.state = "title"
    for _ in range(6):
        g.draw()
        time.sleep(0.15)
    g.start_run()

    random.seed(42)
    t_end = time.time() + 42
    dodge_dir = 1
    while time.time() < t_end and g.state != "quit":
        p = g.player
        # steer toward the safest x (away from nearest enemy bullet column)
        threat = None
        for b in g.enemy_bullets:
            if b.y > p.y - 8 and abs(b.x - p.x) < 4:
                threat = b
                break
        if threat is not None:
            p.x += -3 if threat.x >= p.x else 3
        else:
            p.x += math.sin(time.time() * 1.3) * 2.2

        if random.random() < 0.5:
            g._try_fire()
        if random.random() < 0.01:
            g._use_bomb()

        p.x = max(2, min(g.w - 3, p.x))
        g.update(1 / 30)
        g.draw()
        time.sleep(1 / 30)

        if g.state == "gameover":
            g.reset()
            g.start_run()

    g.audio.shutdown()


curses.wrapper(main)
