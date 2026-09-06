#!/usr/bin/env python3
"""Pre-render the 16-bit style chiptune .wav assets shipped with the game.

Run once (already done — assets are committed): python3 tools/gen_music.py
Regenerates shooter/assets/music/*.wav from pure Python square/triangle
wave synthesis. No external audio libraries required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shooter.audio import render_track, mix, write_wav, ASSET_DIR

# Note durations are in beats. "R" = rest.

def n(*pairs):
    return list(pairs)


TITLE_MELODY = n(
    ("A4", 0.5), ("C5", 0.5), ("E5", 0.5), ("A5", 1.0),
    ("G5", 0.5), ("E5", 0.5), ("C5", 0.5), ("A4", 1.0),
    ("A4", 0.5), ("C5", 0.5), ("E5", 0.5), ("A5", 1.0),
    ("B5", 0.5), ("A5", 0.5), ("G5", 0.5), ("E5", 1.0),
)
TITLE_BASS = n(
    ("A2", 1.0), ("A2", 1.0), ("F2", 1.0), ("A2", 1.0),
    ("A2", 1.0), ("A2", 1.0), ("E2", 1.0), ("E2", 1.0),
)

STAGE_MELODY = n(
    ("E5", 0.5), ("G5", 0.5), ("A5", 0.5), ("E5", 0.5),
    ("D5", 0.5), ("E5", 0.5), ("C5", 0.5), ("A4", 0.5),
    ("E5", 0.5), ("G5", 0.5), ("A5", 0.5), ("B5", 0.5),
    ("C6", 0.5), ("B5", 0.5), ("A5", 0.5), ("G5", 0.5),
    ("F5", 0.5), ("G5", 0.5), ("A5", 0.5), ("F5", 0.5),
    ("E5", 0.5), ("D5", 0.5), ("C5", 0.5), ("D5", 0.5),
    ("E5", 1.0), ("G5", 1.0), ("A5", 2.0),
)
STAGE_BASS = n(
    ("E2", 0.5), ("E2", 0.5), ("A2", 0.5), ("A2", 0.5),
    ("D2", 0.5), ("D2", 0.5), ("A2", 0.5), ("A2", 0.5),
    ("E2", 0.5), ("E2", 0.5), ("C2", 0.5), ("C2", 0.5),
    ("G2", 0.5), ("G2", 0.5), ("D2", 0.5), ("D2", 0.5),
    ("E2", 0.5), ("E2", 0.5), ("A2", 0.5), ("A2", 0.5),
    ("D2", 0.5), ("D2", 0.5), ("A2", 0.5), ("A2", 0.5),
    ("E2", 1.0), ("E2", 1.0), ("A2", 2.0),
)

BOSS_MELODY = n(
    ("D5", 0.25), ("F5", 0.25), ("A5", 0.25), ("D6", 0.25),
    ("C6", 0.25), ("A5", 0.25), ("F5", 0.25), ("D5", 0.25),
    ("D5", 0.25), ("F5", 0.25), ("G#5", 0.25), ("D6", 0.25),
    ("C6", 0.25), ("G#5", 0.25), ("F5", 0.25), ("D5", 0.25),
    ("E5", 0.25), ("G5", 0.25), ("B5", 0.25), ("E6", 0.25),
    ("D6", 0.25), ("B5", 0.25), ("G5", 0.25), ("E5", 0.25),
    ("D5", 0.5), ("D5", 0.5), ("D5", 1.0),
)
BOSS_BASS = n(
    ("D2", 0.5), ("D2", 0.5), ("D2", 0.5), ("D2", 0.5),
    ("G#2", 0.5), ("G#2", 0.5), ("G#2", 0.5), ("G#2", 0.5),
    ("E2", 0.5), ("E2", 0.5), ("E2", 0.5), ("E2", 0.5),
    ("D2", 1.0), ("D2", 1.0),
)

GAMEOVER_MELODY = n(
    ("A4", 0.5), ("G4", 0.5), ("F4", 0.5), ("E4", 0.5),
    ("D4", 0.5), ("C4", 1.0), ("C4", 2.0),
)

VICTORY_MELODY = n(
    ("C5", 0.25), ("E5", 0.25), ("G5", 0.25), ("C6", 0.25),
    ("G5", 0.25), ("C6", 0.5), ("E6", 1.0), ("C6", 1.0),
)


def build(name, melody, bass=None, bpm=150, shape="square", bass_shape="triangle"):
    lead = render_track(melody, bpm=bpm, shape=shape, volume=0.32, decay=0.05)
    if bass:
        low = render_track(bass, bpm=bpm, shape=bass_shape, volume=0.28, decay=0.02)
        pcm = mix(lead, low)
    else:
        pcm = lead
    out = ASSET_DIR / f"{name}.wav"
    write_wav(out, pcm)
    print(f"wrote {out} ({len(pcm)} bytes)")


def main():
    build("title_theme", TITLE_MELODY, TITLE_BASS, bpm=132)
    build("stage_theme", STAGE_MELODY, STAGE_BASS, bpm=150)
    build("boss_theme", BOSS_MELODY, BOSS_BASS, bpm=168, shape="pulse25")
    build("gameover_theme", GAMEOVER_MELODY, bpm=100, shape="triangle")
    build("victory_theme", VICTORY_MELODY, bpm=140, shape="square")

    # SFX: short one-shots
    shot = render_track(n(("A6", 0.06)), bpm=600, shape="square", volume=0.3, decay=2.0)
    write_wav(ASSET_DIR / "sfx_shoot.wav", shot)
    boom = render_track(n(("A2", 0.15), ("F2", 0.1)), bpm=300, shape="saw", volume=0.4, decay=1.0)
    write_wav(ASSET_DIR / "sfx_explosion.wav", boom)
    powerup = render_track(n(("C5", 0.08), ("E5", 0.08), ("G5", 0.08), ("C6", 0.12)),
                            bpm=480, shape="square", volume=0.3, decay=0.2)
    write_wav(ASSET_DIR / "sfx_powerup.wav", powerup)
    hit = render_track(n(("C3", 0.08)), bpm=400, shape="square", volume=0.35, decay=1.5)
    write_wav(ASSET_DIR / "sfx_hit.wav", hit)


if __name__ == "__main__":
    main()
