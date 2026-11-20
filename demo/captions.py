#!/usr/bin/env python3
"""Caption pane for the tmux demo: lists the features and highlights the
current one.  Reads step numbers (one per line) from the FIFO in argv[1]."""
import os, signal, sys, textwrap

STEPS = [
    ("Dashboard",       "",      "Battery, charging, climate, tyres and locks at a glance. Refreshes every 5 s."),
    ("Units",           "u",     "Metric or US units."),
    ("Colors",          "b",     "Off by default; -c starts with colors."),
    ("Invert",          "i",     "Inverted screen."),
    ("Help",            "h",     "Keys and current settings."),
    ("Command list",    "?",     "Every command, by category. j/k to scroll."),
    ("Search",          "/",     "Regex search in the list; n/N jump between matches."),
    ("Type a command",  ":",     "Tab completes. In read-only mode commands are checked but not sent."),
    ("Hotkeys",         "H",     "One-key commands, e.g. H honks (not sent in read-only mode)."),
    ("Command log",     "z",     "Every command and its result is logged."),
    ("Refresh rate",    "+ -",   "Refresh interval in 5 s steps, shown in help."),
    ("Modes",           "m",     "ro -> mtm (MyTeslaMate API) -> vc (vehicle-command, WIP)."),
]

B, DIM, REV, CYN, R = "\x1b[1m", "\x1b[2m", "\x1b[7m", "\x1b[36m", "\x1b[0m"


def draw(cur: int) -> None:
    cols = os.get_terminal_size().columns
    out = ["\x1b[H\x1b[2J", "", f"  {B}tuisla{R} {DIM}demo, read-only mode{R}", "", ""]
    for i, (title, key, _) in enumerate(STEPS):
        keytxt = f"{CYN}{key:>3}{R}" if key else "   "
        if i == cur:
            out.append(f" {REV}{B} > {title:<{cols - 12}}{R}{keytxt}")
        elif i < cur:
            out.append(f" {DIM}   {title:<{cols - 12}}{R}{keytxt}")
        else:
            out.append(f"    {title:<{cols - 12}}{keytxt}")
    out += ["", ""]
    if 0 <= cur < len(STEPS):
        for line in textwrap.wrap(STEPS[cur][2], cols - 4):
            out.append(f"  {line}")
    sys.stdout.write("\r\n".join(out))
    sys.stdout.flush()


current = -1
signal.signal(signal.SIGWINCH, lambda *_: draw(current))   # redraw when tmux resizes us
sys.stdout.write("\x1b[?25l")   # hide cursor
draw(current)
with open(sys.argv[1]) as fifo:
    for line in fifo:
        line = line.strip()
        if line == "end":
            break
        current = int(line)
        draw(current)
