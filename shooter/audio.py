"""16-bit style chiptune audio engine for Terminal Shooter.

Generates simple square/triangle-wave PCM tunes with the stdlib `wave`
module (no numpy / pygame needed) and plays them as a background loop
using whatever native player is available on the host:

  * Linux:  aplay (ALSA) or paplay (PulseAudio)
  * macOS:  afplay

If no audio backend is found (headless box, no ALSA, SSH session with
no sound server) the game silently runs with audio disabled — never
crashes because of missing sound.
"""
from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 22050
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "music"

# ---------------------------------------------------------------------------
# Chiptune synthesis (used by tools/gen_music.py to pre-render the .wav files
# that ship in the repo; also callable at runtime if assets are missing).
# ---------------------------------------------------------------------------

NOTE_FREQS = {
    "C": 16.35, "C#": 17.32, "D": 18.35, "D#": 19.45, "E": 20.60,
    "F": 21.83, "F#": 23.12, "G": 24.50, "G#": 25.96, "A": 27.50,
    "A#": 29.14, "B": 30.87,
}


def note_freq(name: str) -> float:
    """'A4' -> 440.0 style note-name to frequency."""
    if name in ("R", "-", ""):
        return 0.0
    pitch = name[:-1]
    octave = int(name[-1])
    base = NOTE_FREQS[pitch]
    return base * (2 ** octave)


def _wave_sample(freq: float, t: float, shape: str) -> float:
    if freq <= 0:
        return 0.0
    phase = (t * freq) % 1.0
    if shape == "square":
        return 1.0 if phase < 0.5 else -1.0
    if shape == "triangle":
        return 4.0 * abs(phase - 0.5) - 1.0
    if shape == "saw":
        return 2.0 * phase - 1.0
    if shape == "pulse25":
        return 1.0 if phase < 0.25 else -1.0
    return math.sin(2 * math.pi * phase)


def render_track(notes, bpm=140, shape="square", volume=0.35,
                  vibrato=0.0, decay=0.15) -> bytes:
    """notes: list of (note_name, beats). Returns raw 16-bit mono PCM."""
    beat_len = 60.0 / bpm
    samples = []
    for note_name, beats in notes:
        dur = beats * beat_len
        n = int(dur * SAMPLE_RATE)
        freq = note_freq(note_name)
        for i in range(n):
            t = i / SAMPLE_RATE
            f = freq
            if vibrato and freq:
                f = freq * (1 + vibrato * math.sin(2 * math.pi * 5 * t))
            s = _wave_sample(f, t, shape)
            # simple percussive decay envelope so notes aren't harsh blocks
            env = 1.0
            if decay:
                env = math.exp(-decay * t * bpm / 60.0 * 4)
                env = max(env, 0.25)
            samples.append(s * volume * env)
    peak = max((abs(s) for s in samples), default=1.0) or 1.0
    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, s / peak)) * 32000)
        frames += struct.pack("<h", v)
    return bytes(frames)


def mix(*tracks: bytes) -> bytes:
    """Mix several equal-format PCM tracks (shorter ones are looped)."""
    if not tracks:
        return b""
    lengths = [len(t) // 2 for t in tracks]
    n = max(lengths)
    out = bytearray()
    unpacked = [struct.unpack(f"<{len(t)//2}h", t) for t in tracks]
    for i in range(n):
        acc = 0
        for samples in unpacked:
            acc += samples[i % len(samples)]
        acc = max(-32767, min(32767, acc))
        out += struct.pack("<h", acc)
    return bytes(out)


def write_wav(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def _find_player():
    if sys.platform == "darwin":
        for cand in ("afplay",):
            p = shutil.which(cand)
            if p:
                return [p]
        return None
    for cand in ("aplay", "paplay", "ffplay"):
        p = shutil.which(cand)
        if p:
            if cand == "ffplay":
                return [p, "-nodisp", "-autoexit", "-loglevel", "quiet"]
            return [p, "-q"] if cand == "aplay" else [p]
    return None


class MusicPlayer:
    """Loops a background music track and plays one-shot SFX, best-effort."""

    def __init__(self, enabled: bool = True):
        self.player_cmd = _find_player()
        self.enabled = enabled and self.player_cmd is not None
        self._proc = None
        self._current = None

    def play_music(self, name: str, loop: bool = True):
        if not self.enabled:
            return
        path = ASSET_DIR / f"{name}.wav"
        if not path.exists():
            return
        if self._current == name and self._proc and self._proc.poll() is None:
            return
        self.stop_music()
        try:
            if loop:
                # Wrap in a tiny shell loop so aplay/afplay repeats the track
                cmd = f'while :; do "{self.player_cmd[0]}" ' + \
                      " ".join(f'"{a}"' for a in self.player_cmd[1:]) + \
                      f' "{path}" >/dev/null 2>&1; done'
                self._proc = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, preexec_fn=os.setsid
                    if hasattr(os, "setsid") else None,
                )
            else:
                self._proc = subprocess.Popen(
                    self.player_cmd + [str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            self._current = name
        except Exception:
            self.enabled = False

    def play_sfx(self, name: str):
        if not self.enabled:
            return
        path = ASSET_DIR / f"{name}.wav"
        if not path.exists():
            return
        try:
            subprocess.Popen(
                self.player_cmd + [str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def stop_music(self):
        if self._proc and self._proc.poll() is None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(self._proc.pid), 15)
                else:
                    self._proc.terminate()
            except Exception:
                pass
        self._proc = None
        self._current = None

    def shutdown(self):
        self.stop_music()
