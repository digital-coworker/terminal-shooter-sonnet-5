"""Terminal Shooter — curses render/input/collision engine and main loop."""
from __future__ import annotations

import curses
import json
import math
import os
import random
import time
from pathlib import Path

from .entities import Bullet, Enemy, Particle, PowerUp
from .weapons import WeaponState, fire, LEVEL_LABEL
from .waves import WaveDirector
from .audio import MusicPlayer

FPS = 30
FRAME_TIME = 1.0 / FPS
HIGH_SCORE_FILE = Path.home() / ".terminal_shooter_highscore.json"

STAR_CHARS = ".:*+"
PICKUP_KINDS = ["vulcan", "spread", "laser", "missile", "shield", "bomb", "score"]
PICKUP_WEIGHTS = [30, 16, 14, 12, 10, 8, 10]


def load_high_score() -> int:
    try:
        return int(json.loads(HIGH_SCORE_FILE.read_text()).get("high_score", 0))
    except Exception:
        return 0


def save_high_score(score: int):
    try:
        HIGH_SCORE_FILE.write_text(json.dumps({"high_score": score}))
    except Exception:
        pass


class Starfield:
    def __init__(self, w, h, n=60):
        self.w, self.h = w, h
        self.stars = [
            [random.uniform(0, w), random.uniform(0, h), random.uniform(4, 20)]
            for _ in range(n)
        ]

    def update(self, dt, speed_mul=1.0):
        for s in self.stars:
            s[1] += s[2] * dt * speed_mul
            if s[1] >= self.h:
                s[1] = 0
                s[0] = random.uniform(0, self.w)

    def draw(self, win):
        for x, y, speed in self.stars:
            idx = min(len(STAR_CHARS) - 1, int(speed / 6))
            try:
                win.addch(int(y), int(x), STAR_CHARS[idx], curses.color_pair(7))
            except curses.error:
                pass


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.lives = 3
        self.weapon = WeaponState()
        self.fire_cd = 0.0
        self.invuln = 0.0
        self.alive = True
        self.bomb_flash = 0.0

    def rect(self):
        return (self.x - 1, self.y, 3, 1)


class Game:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(0)
        self._setup_colors()
        self.h, self.w = stdscr.getmaxyx()
        self.h = max(self.h, 24)
        self.w = max(self.w, 60)
        self.audio = MusicPlayer(enabled=True)
        self.reset()

    # ------------------------------------------------------------------ setup
    def _setup_colors(self):
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        pairs = [
            (1, curses.COLOR_RED, bg),
            (2, curses.COLOR_GREEN, bg),
            (3, curses.COLOR_YELLOW, bg),
            (4, curses.COLOR_BLUE, bg),
            (5, curses.COLOR_MAGENTA, bg),
            (6, curses.COLOR_CYAN, bg),
            (7, curses.COLOR_BLUE, bg),
            (8, curses.COLOR_BLACK, curses.COLOR_WHITE if bg != -1 else -1),
        ]
        for idx, fg, bgc in pairs:
            try:
                curses.init_pair(idx, fg, bgc)
            except curses.error:
                pass

    def reset(self):
        self.state = "title"
        self.stars = Starfield(self.w, self.h)
        self.player = Player(self.w // 2, self.h - 4)
        self.bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.particles = []
        self.powerups = []
        self.waves = WaveDirector(self.w, self.h)
        self.score = 0
        self.high_score = load_high_score()
        self.combo = 0
        self.combo_timer = 0.0
        self.t = 0.0
        self.shake = 0.0
        self.paused = False
        self.wave_banner = 0.0
        self.wave_banner_text = ""
        self.game_over_reason = ""
        self.keys_down = set()

    # ------------------------------------------------------------------ input
    def handle_input(self):
        while True:
            try:
                key = self.stdscr.getch()
            except curses.error:
                break
            if key == -1:
                break
            self._on_key(key)

    def _on_key(self, key):
        if key in (ord("q"), ord("Q")):
            self.state = "quit"
            return
        if self.state == "title":
            if key in (ord(" "), curses.KEY_ENTER, 10, 13):
                self.start_run()
            elif key in (ord("m"), ord("M")):
                self.audio.enabled = not self.audio.enabled
                if not self.audio.enabled:
                    self.audio.stop_music()
            return
        if self.state == "gameover":
            if key in (ord(" "), curses.KEY_ENTER, 10, 13):
                self.reset()
                self.start_run()
            return
        if self.state == "paused":
            if key in (ord("p"), ord("P")):
                self.state = "playing"
            return
        if self.state == "playing":
            if key == curses.KEY_LEFT:
                self.player.x -= 3
            elif key == curses.KEY_RIGHT:
                self.player.x += 3
            elif key == curses.KEY_UP:
                self.player.y -= 1.5
            elif key == curses.KEY_DOWN:
                self.player.y += 1.5
            elif key == ord(" "):
                self._try_fire()
            elif key in (ord("b"), ord("B")):
                self._use_bomb()
            elif key in (ord("p"), ord("P")):
                self.state = "paused"
            self.player.x = max(2, min(self.w - 3, self.player.x))
            self.player.y = max(2, min(self.h - 2, self.player.y))

    # ------------------------------------------------------------------ logic
    def start_run(self):
        self.state = "playing"
        self.waves.start_next_wave()
        self.wave_banner = 2.0
        self.wave_banner_text = self._wave_title()
        self.audio.play_music("stage_theme")

    def _wave_title(self):
        if self.waves.in_boss:
            return f"WARNING — BOSS APPROACHING"
        return f"WAVE {self.waves.wave_num}"

    def _try_fire(self):
        p = self.player
        if p.fire_cd > 0:
            return
        rate = max(0.08, 0.22 - p.weapon.level * 0.015)
        p.fire_cd = rate
        new_bullets = fire(p.x, p.y, p.weapon, self.enemies)
        self.bullets.extend(new_bullets)
        self.audio.play_sfx("sfx_shoot")

    def _use_bomb(self):
        p = self.player
        if p.weapon.bombs <= 0:
            return
        p.weapon.bombs -= 1
        p.bomb_flash = 0.35
        self.shake = 0.4
        for e in self.enemies:
            if e.boss:
                if e.hit(20):
                    self._on_enemy_killed(e)
            else:
                e.hit(999)
                self._on_enemy_killed(e)
        self.enemy_bullets.clear()
        self.audio.play_sfx("sfx_explosion")

    def _spawn_particles(self, x, y, n, color=3, spread=14):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(2, spread)
            self.particles.append(Particle(
                x, y, math.cos(ang) * spd, math.sin(ang) * spd * 0.5,
                random.uniform(0.2, 0.5), random.choice("*+.oO"), color))

    def _on_enemy_killed(self, e: Enemy):
        self.score += e.score
        self.combo += 1
        self.combo_timer = 1.5
        self._spawn_particles(e.x + e.w / 2, e.y, 10 + (14 if e.boss else 0),
                               color=1 if e.boss else 3)
        self.audio.play_sfx("sfx_explosion")
        drop_chance = 0.9 if e.boss else 0.22
        if random.random() < drop_chance:
            kind = random.choices(PICKUP_KINDS, weights=PICKUP_WEIGHTS)[0]
            self.powerups.append(PowerUp(e.x + e.w / 2, e.y, kind))
        if e.boss:
            self.score += 500
            self.shake = 0.6

    def _apply_powerup(self, kind: str):
        p = self.player
        if kind == "score":
            self.score += 250
        elif kind == "shield":
            p.weapon.shield = min(3, p.weapon.shield + 1)
        elif kind == "bomb":
            p.weapon.bombs = min(9, p.weapon.bombs + 1)
        else:
            p.weapon.set_kind(kind)
        self.audio.play_sfx("sfx_powerup")

    def update(self, dt: float):
        if self.state != "playing":
            return
        self.t += dt
        speed_mul = 1.0 + min(2.0, self.waves.wave_num * 0.08)
        self.stars.update(dt, speed_mul)
        p = self.player

        if p.fire_cd > 0:
            p.fire_cd -= dt
        if p.invuln > 0:
            p.invuln -= dt
        if p.bomb_flash > 0:
            p.bomb_flash -= dt
        if self.shake > 0:
            self.shake -= dt
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
        if self.wave_banner > 0:
            self.wave_banner -= dt

        # spawn
        new_enemy = self.waves.update(dt, len(self.enemies))
        if new_enemy:
            self.enemies.append(new_enemy)
            if new_enemy.boss:
                self.audio.play_music("boss_theme")

        # update bullets
        self.bullets = [b for b in self.bullets if b.update(dt, self.w, self.h)]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.update(dt, self.w, self.h)]

        # update enemies + enemy fire
        alive_enemies = []
        for e in self.enemies:
            keep = e.update(dt, self.w, self.h, p.x)
            if not keep:
                continue
            alive_enemies.append(e)
            if e.shoots:
                e._fire_timer -= dt
                if e._fire_timer <= 0:
                    e._fire_timer = e.fire_rate
                    dx = p.x - e.x
                    dy = p.y - e.y
                    dist = math.hypot(dx, dy) or 1
                    spd = 14 + self.waves.difficulty * 2
                    self.enemy_bullets.append(Bullet(
                        e.x + e.w / 2, e.y + e.h, dx / dist * spd, dy / dist * spd,
                        "•", 1, friendly=False))
                    if e.boss and self.waves.difficulty > 2:
                        for off in (-0.5, 0.5):
                            self.enemy_bullets.append(Bullet(
                                e.x + e.w / 2, e.y + e.h,
                                dx / dist * spd + off * 8, dy / dist * spd,
                                "•", 5, friendly=False))
        self.enemies = alive_enemies

        # particles / powerups
        self.particles = [pt for pt in self.particles if pt.update(dt)]
        alive_pw = []
        for pw in self.powerups:
            if pw.update(dt, self.h):
                alive_pw.append(pw)
        self.powerups = alive_pw

        self._collisions()

        # wave progression
        if self.waves.wave_complete(len(self.enemies)):
            self.waves.start_next_wave()
            self.wave_banner = 2.0
            self.wave_banner_text = self._wave_title()
            if not self.waves.in_boss:
                self.audio.play_music("stage_theme")

        if p.lives <= 0:
            self.game_over_reason = "SHIP DESTROYED"
            self._end_run()

    def _collisions(self):
        p = self.player
        # player bullets vs enemies
        for b in self.bullets:
            if not b.friendly:
                continue
            for e in self.enemies:
                if not e.alive:
                    continue
                if (e.x - 1 <= b.x <= e.x + e.w and e.y - 1 <= b.y <= e.y + e.h):
                    b.y = -999  # mark consumed
                    killed = e.hit(b.dmg)
                    self.audio.play_sfx("sfx_hit")
                    if killed:
                        self._on_enemy_killed(e)
                    break
        self.bullets = [b for b in self.bullets if b.y != -999]
        self.enemies = [e for e in self.enemies if e.alive]

        # enemy bullets vs player
        if p.invuln <= 0:
            for b in self.enemy_bullets:
                if abs(b.x - p.x) < 1.4 and abs(b.y - p.y) < 1.0:
                    b.y = -999
                    self._damage_player()
                    break
            self.enemy_bullets = [b for b in self.enemy_bullets if b.y != -999]

            # enemy body collisions
            for e in self.enemies:
                if e.x - 1 <= p.x <= e.x + e.w and e.y - 1 <= p.y <= e.y + e.h:
                    self._damage_player()
                    if not e.boss:
                        e.hp = 0
                        e.alive = False
                    break
            self.enemies = [e for e in self.enemies if e.alive]

        # powerups vs player
        remaining = []
        for pw in self.powerups:
            if abs(pw.x - p.x) < 2.2 and abs(pw.y - p.y) < 1.5:
                self._apply_powerup(pw.kind)
            else:
                remaining.append(pw)
        self.powerups = remaining

    def _damage_player(self):
        p = self.player
        if p.weapon.shield > 0:
            p.weapon.shield -= 1
            p.invuln = 0.5
            self._spawn_particles(p.x, p.y, 8, color=6)
            return
        p.lives -= 1
        p.invuln = 1.2
        self.shake = 0.35
        self._spawn_particles(p.x, p.y, 16, color=1)
        self.audio.play_sfx("sfx_explosion")
        if p.lives > 0:
            p.weapon = WeaponState(bombs=p.weapon.bombs)

    def _end_run(self):
        self.state = "gameover"
        if self.score > self.high_score:
            self.high_score = self.score
            save_high_score(self.score)
        self.audio.play_music("gameover_theme", loop=False)

    # ------------------------------------------------------------------ draw
    def draw(self):
        win = self.stdscr
        win.erase()
        h, w = self.h, self.w
        ox = oy = 0
        if self.shake > 0:
            ox = random.randint(-1, 1)
            oy = random.randint(-1, 1)

        if self.state == "title":
            self._draw_title(win)
        elif self.state in ("playing", "paused"):
            self.stars.draw(win)
            self._draw_entities(win, ox, oy)
            self._draw_hud(win)
            if self.wave_banner > 0:
                self._draw_center_text(win, self.wave_banner_text, h // 2 - 2, 6)
            if self.state == "paused":
                self._draw_center_text(win, "PAUSED — press P to resume", h // 2, 7)
        elif self.state == "gameover":
            self.stars.draw(win)
            self._draw_gameover(win)
        win.noutrefresh()
        curses.doupdate()

    def _draw_center_text(self, win, text, y, color):
        x = max(0, (self.w - len(text)) // 2)
        try:
            win.addstr(int(y), int(x), text, curses.color_pair(color) | curses.A_BOLD)
        except curses.error:
            pass

    def _safe_add(self, win, y, x, s, attr=0):
        if 0 <= y < self.h and 0 <= x < self.w:
            try:
                win.addstr(int(y), int(x), s[: max(0, self.w - int(x) - 1)], attr)
            except curses.error:
                pass

    def _safe_ch(self, win, y, x, ch, attr=0):
        if 0 <= y < self.h - 0 and 0 <= x < self.w - 0:
            try:
                win.addch(int(y), int(x), ch, attr)
            except curses.error:
                pass

    def _draw_title(self, win):
        logo = [
            " _____ _____ ____  __  __ ___ _   _    _    _     ",
            "|_   _| ____|  _ \\|  \\/  |_ _| \\ | |  / \\  | |    ",
            "  | | |  _| | |_) | |\\/| || ||  \\| | / _ \\ | |    ",
            "  | | | |___|  _ <| |  | || || |\\  |/ ___ \\| |___ ",
            "  |_| |_____|_| \\_\\_|  |_|___|_| \\_/_/   \\_\\_____|",
            "",
            " ____  _   _  ___   ___ _____ _____ ____  ",
            "/ ___|| | | |/ _ \\ / _ \\_   _| ____|  _ \\ ",
            "\\___ \\| |_| | | | | | | || | |  _| | |_) |",
            " ___) |  _  | |_| | |_| || | | |___|  _ < ",
            "|____/|_| |_|\\___/ \\___/ |_| |_____|_| \\_\\ ",
        ]
        y0 = self.h // 2 - len(logo) - 3
        for i, line in enumerate(logo):
            x = max(0, (self.w - len(line)) // 2)
            self._safe_add(win, y0 + i, x, line, curses.color_pair(6) | curses.A_BOLD)
        self._draw_center_text(win, "a 16-bit vertical shoot-'em-up for your terminal",
                                y0 + len(logo) + 1, 7)
        blink = int(self.t * 2) % 2 == 0
        if blink:
            self._draw_center_text(win, "PRESS SPACE / ENTER TO START", y0 + len(logo) + 4, 3)
        self._draw_center_text(win, "ARROWS move   SPACE fire   B bomb   P pause   M mute   Q quit",
                                y0 + len(logo) + 6, 4)
        self._draw_center_text(win, f"HIGH SCORE: {self.high_score}", y0 + len(logo) + 8, 2)

    def _draw_gameover(self, win):
        h, w = self.h, self.w
        self._draw_center_text(win, "GAME OVER", h // 2 - 4, 1)
        self._draw_center_text(win, self.game_over_reason, h // 2 - 2, 7)
        self._draw_center_text(win, f"SCORE: {self.score}    HIGH SCORE: {self.high_score}",
                                h // 2, 3)
        self._draw_center_text(win, f"WAVE REACHED: {self.waves.wave_num}", h // 2 + 1, 6)
        blink = int(self.t * 2) % 2 == 0
        if blink:
            self._draw_center_text(win, "PRESS SPACE TO RETRY", h // 2 + 4, 2)
        self._draw_center_text(win, "Q to quit", h // 2 + 6, 4)

    def _draw_entities(self, win, ox, oy):
        for pt in self.particles:
            self._safe_ch(win, pt.y + oy, pt.x + ox, pt.ch, curses.color_pair(pt.color))
        for pw in self.powerups:
            glyph = {"vulcan": "V", "spread": "S", "laser": "L", "missile": "M",
                     "shield": "O", "bomb": "B", "score": "$"}[pw.kind]
            self._safe_ch(win, pw.y, pw.x, glyph, curses.color_pair(2) | curses.A_BOLD)
        for b in self.bullets:
            self._safe_ch(win, b.y, b.x, b.ch, curses.color_pair(b.color) | curses.A_BOLD)
        for b in self.enemy_bullets:
            self._safe_ch(win, b.y, b.x, b.ch, curses.color_pair(b.color))
        for e in self.enemies:
            attr = curses.color_pair(e.color)
            if e.flash > 0:
                attr = curses.color_pair(7) | curses.A_BOLD | curses.A_REVERSE
            if e.boss:
                self._draw_boss(win, e, attr)
            else:
                self._safe_ch(win, e.y, e.x, e.glyph, attr)
        p = self.player
        if p.invuln <= 0 or int(self.t * 12) % 2 == 0:
            attr = curses.color_pair(6) | curses.A_BOLD
            self._safe_ch(win, p.y, p.x, "▲", attr)
            self._safe_ch(win, p.y + 1, p.x - 1, "/", attr)
            self._safe_ch(win, p.y + 1, p.x + 1, "\\", attr)

    def _draw_boss(self, win, e, attr):
        art = [
            "  /=====\\  ",
            " <  0 0  > ",
            "  \\-----/  ",
        ]
        for row, line in enumerate(art):
            self._safe_add(win, e.y + row, e.x - 2, line, attr)
        bar_w = 20
        pct = max(0, e.hp / e.max_hp)
        filled = int(bar_w * pct)
        bx = max(0, self.w // 2 - bar_w // 2)
        name = getattr(e, "name", "BOSS")
        self._safe_add(win, 1, bx, name[:bar_w].center(bar_w), curses.color_pair(1) | curses.A_BOLD)
        self._safe_add(win, 2, bx, "[" + "#" * filled + "-" * (bar_w - filled) + "]",
                        curses.color_pair(1))

    def _draw_hud(self, win):
        w, h = self.w, self.h
        p = self.player
        label = LEVEL_LABEL.get(p.weapon.kind, p.weapon.kind.upper())
        top = (f"SCORE {self.score:06d}  HI {self.high_score:06d}  "
               f"WAVE {self.waves.wave_num}")
        self._safe_add(win, 0, 1, top, curses.color_pair(7) | curses.A_BOLD)
        bottom = (f"LIVES {'♥' * max(0, p.lives)}  {label} Lv{p.weapon.level}  "
                  f"SHIELD {'o' * p.weapon.shield}  BOMBS {p.weapon.bombs}")
        self._safe_add(win, h - 1, 1, bottom, curses.color_pair(3))
        if self.combo >= 3:
            self._safe_add(win, 3, w - 14, f"COMBO x{self.combo}",
                            curses.color_pair(5) | curses.A_BOLD)

    # ------------------------------------------------------------------ loop
    def run(self):
        last = time.time()
        while self.state != "quit":
            now = time.time()
            dt = now - last
            last = now
            if dt > 0.1:
                dt = 0.1
            self.handle_input()
            self.update(dt if self.state == "playing" else min(dt, FRAME_TIME))
            self.draw()
            elapsed = time.time() - now
            sleep_left = FRAME_TIME - elapsed
            if sleep_left > 0:
                time.sleep(sleep_left)
        self.audio.shutdown()


def _main(stdscr):
    game = Game(stdscr)
    game.run()


def run():
    try:
        curses.wrapper(_main)
    except KeyboardInterrupt:
        pass
