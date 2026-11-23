#!/usr/bin/env python3
"""Caption pane for the tmux demo: lists the features, highlights the current
one, and shows the keys pressed.  Reads lines from the FIFO in argv[1]:
a step number, "key NAME", or "end"."""
import collections, os, signal, sys, textwrap

STEPS = [
    ("Dashboard",           "",      "Battery, charging and its schedule, climate, preheating, tyres, locks, windows and the route at a glance."),
    ("Help",                "h",     "Keys and current settings. Toggles take effect right away:"),
    ("  Refresh rate",      "+ -",   "Refresh interval in 5 s steps, shown in help."),
    ("  Colors",            "b",     "On by default; -b starts without. Seen on the dashboard."),
    ("  Invert",            "i",     "Inverted screen, seen on the dashboard, then back."),
    ("  Units",             "u",     "Metric or US units, seen on the dashboard, then back."),
    ("  Style",             "s",     "Fancy or minimal style, seen on the dashboard, then back."),
    ("Command list",        "?",     "Every command, by category. j/k to scroll."),
    ("Search",              "/",     "Regex search in the list; n/N jump between matches."),
    ("Type a command",      ":",     "Tab completes, e.g. temp 22. In read-only mode commands are checked but not sent."),
    ("Hotkeys",             "H",     "One-key commands, e.g. H honks (not sent in read-only mode)."),
    ("Command log",         "z",     "Every command and its result is logged, with the mode it was sent in."),
    ("Last data",           "!",     "The car's last data as JSON, as Tesla sent it."),
    ("Costs",               "$",     "Billed requests (Fleet API, MyTeslaMate) and their cost, per billing period."),
    ("Chargers",            ":",     "Chargers in range, or in km (chargers 200); Enter sends one to the car."),
    ("Terminal map",        ":",     "mapscii chargers / country: the car and the Superchargers in range or in its country."),
    ("  Globe view",        ":",     "mapscii world: all Superchargers on a 3D globe; a/z zoom."),
    ("Sleep",               "W",     "The car may sleep when idle (default); W keeps it awake, w wakes it once."),
    ("Modes",               "m",     "ro -> mtm (MyTeslaMate API) -> vc (own key, via vehicle-command)."),
]
KEY_NAMES = {"Enter": "⏎", "Tab": "Tab", " ": "␣", "Left": "←"}

B, DIM, REV, CYN, R = "\x1b[1m", "\x1b[2m", "\x1b[7m", "\x1b[36m", "\x1b[0m"

current = -1
keys: collections.deque = collections.deque(maxlen=20)


def draw() -> None:
    cols, rows = os.get_terminal_size()
    out = ["\x1b[H\x1b[2J", "", f"  {B}tuisla{R} {DIM}demo, read-only mode{R}", ""]
    for i, (title, key, _) in enumerate(STEPS):
        keytxt = f"{CYN}{key:>3}{R}" if key else "   "
        if i == current:
            out.append(f" {REV}{B} > {title:<{cols - 12}}{R}{keytxt}")
        elif i < current:
            out.append(f" {DIM}   {title:<{cols - 12}}{R}{keytxt}")
        else:
            out.append(f"    {title:<{cols - 12}}{keytxt}")
    out.append("")
    if 0 <= current < len(STEPS):
        room = rows - 3 - len(out)                 # above "Keys pressed"
        for line in textwrap.wrap(STEPS[current][2], cols - 4)[:max(0, room)]:
            out.append(f"  {line}")
    sys.stdout.write("\r\n".join(out))

    # Keys pressed, newest last and highlighted, at the bottom of the pane.
    caps = []
    for k in reversed(keys):                       # keep as many recent keys as fit
        if sum(len(x) + 2 for x in caps) + len(k) + 2 > cols - 4:
            break
        caps.insert(0, k)
    line = "".join(f" {k} " for k in caps[:-1])
    if caps:
        line += f"{REV}{B} {caps[-1]} {R}"
    sys.stdout.write(f"\x1b[{rows - 2};1H  {DIM}Keys pressed:{R}\x1b[{rows - 1};1H  {line}")
    sys.stdout.flush()


signal.signal(signal.SIGWINCH, lambda *_: draw())   # redraw when tmux resizes us
sys.stdout.write("\x1b[?25l")   # hide cursor
draw()
with open(sys.argv[1]) as fifo:
    for msg in fifo:
        msg = msg.rstrip("\n")
        if msg == "end":
            break
        if msg.startswith("key "):
            keys.append(KEY_NAMES.get(msg[4:], msg[4:]))
        else:
            current = int(msg)
        draw()
