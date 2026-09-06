"""Dev-only helper: drives the Game object programmatically to reach
interesting states (boss fight, high weapon level) for screenshot capture.
Not part of the shipped game; lives outside the package.
"""
import curses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shooter.game import Game
from shooter.weapons import WeaponState


def main(stdscr):
    g = Game(stdscr)
    g.audio.enabled = False
    mode = sys.argv[1] if len(sys.argv) > 1 else "action"

    if mode == "title":
        g.state = "title"
        while True:
            g.draw()
            time.sleep(0.1)

    if mode == "boss":
        g.state = "playing"
        g.waves.wave_num = 4
        g.waves.start_next_wave()  # wave 5, boss
        g.wave_banner = 0.0
        g.player.weapon = WeaponState(kind="laser", level=6)
        for _ in range(40):
            g.update(1 / 30)
            g.draw()
            time.sleep(0.02)
        while True:
            g.draw()
            time.sleep(0.1)

    if mode == "action":
        g.start_run()
        import random
        random.seed(7)
        g.player.weapon = WeaponState(kind="spread", level=5)
        for i in range(90):
            if i % 3 == 0:
                g._try_fire()
            g.player.x += random.uniform(-1, 1)
            g.update(1 / 30)
            g.draw()
            time.sleep(0.01)
        while True:
            g.draw()
            time.sleep(0.1)

    if mode == "gameover":
        g.state = "playing"
        g.score = 4820
        g.waves.wave_num = 7
        g.game_over_reason = "SHIP DESTROYED"
        g._end_run()
        g.audio.enabled = False
        for _ in range(3):
            g.draw()
            time.sleep(0.05)
        while True:
            g.draw()
            time.sleep(0.1)


curses.wrapper(main)
