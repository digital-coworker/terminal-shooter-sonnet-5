#!/usr/bin/env python3
"""
TERMINAL SHOOTER — a 16-bit-style vertical shoot-'em-up for the terminal.

Entry point. Run with:  python3 game.py
Works on Linux and macOS terminals (curses-based, stdlib only).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shooter.game import run


if __name__ == "__main__":
    run()
