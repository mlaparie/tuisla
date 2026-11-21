#!/usr/bin/env python3
"""Record the tuisla demo as an asciicast: a private tmux server with a
caption pane (captions.py) on the left and tuisla on the right, driven by a
scripted key sequence.  tuisla runs on its built-in demo data, in read-only
mode, from a temporary copy (so it logs there and sees no tokens).

Usage: demo/record-tmux.py [OUT.cast]      (default: demo/tuisla.cast)
Needs: tmux, python3, and node for the mapscii part (on Guix:
guix shell node -- demo/record-tmux.py).
Make the GIF with agg (on Guix, the asciinema-agg package):
    guix shell asciinema-agg font-iosevka-term -- sh -c \
      'agg --font-dir "$GUIX_ENVIRONMENT/share/fonts" --font-family "Iosevka Term" \
           demo/tuisla.cast demo/tuisla.gif'"""
import codecs, fcntl, json, os, pty, select, shlex, shutil, struct, subprocess, sys
import tempfile, termios, time

HERE      = os.path.dirname(os.path.abspath(__file__))
OUT       = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "tuisla.cast"))
COLS, ROWS = 132, 32
CAPTION_W = 34
SOCK      = f"tuisla-demo-{os.getpid()}"      # private tmux server, not the user's


def typed(text: str, gap: float = 0.12):
    return [(gap, ch, True) for ch in text]   # True: send literally


# (caption step or None, [(delay before key, key[, literal]), ...], pause after)
SCRIPT = [
    (0,  [], 4.0),
    (1,  [(0.8, "h")], 2.0),                                  # help stays open for 2-6
    (2,  [(0.8, "+"), (1.5, "+"), (1.5, "-"), (1.5, "-")], 1.5),
    # The rest: toggle in help, close help to see it on the dashboard, revert
    # it there (colors stay on), reopen help.  Style ends on the dashboard.
    (3,  [(0.8, "b"), (1.2, "h"), (2.5, "h")], 1.0),
    (4,  [(0.8, "i"), (1.2, "h"), (2.5, "i"), (1.5, "h")], 1.0),
    (5,  [(0.8, "u"), (1.2, "h"), (2.5, "u"), (1.5, "h")], 1.0),
    (6,  [(0.8, "s"), (1.2, "h"), (2.5, "s")], 2.0),
    (7,  [(0.8, "?"), (2.0, "j"), (0.3, "j"), (0.3, "j"), (0.3, "j")], 1.5),
    (8,  [(0.8, "/")] + typed("climate", 0.15) + [(0.8, "Enter"), (2.0, "n")], 2.0),
    (None, [(0, "q")], 0.5),
    (9,  [(0.8, ":")] + typed("te") + [(0.6, "Tab"), (1.8, "Tab")] + typed(" 22")
         + [(1.2, "Enter")], 3.0),
    (10, [(0.8, "H")], 3.0),
    (11, [(0.8, "z")], 3.5),
    (None, [(0, "q")], 0.5),
    (12, [(0.8, ":")] + typed("chargers 200") + [(0.8, "Enter"), (2.5, "j"), (1.2, "Enter")], 4.5),
    (13, [(0.8, ":")] + typed("mapscii chargers", 0.1) + [(0.8, "Enter")], 9.0),
    (None, [(0, "q")], 1.0),
    (None, [(0.5, ":")] + typed("mapscii country", 0.1) + [(0.8, "Enter")], 7.0),
    (None, [(0, "q")], 1.0),
    # The world opens as a globe, then zooms in on Europe.
    (14, [(0.8, ":")] + typed("mapscii world", 0.1) + [(0.8, "Enter")]
         + [(7.0, "a")] + [(0.6, "a")] * 6, 3.0),
    (None, [(0, "q"), (2.5, "q")], 1.0),
    (15, [(0.8, "W"), (3.5, "W")], 3.0),
    (16, [(0.8, "m"), (2.2, "m"), (2.2, "m")], 2.5),
]   # the cast ends here, before anything quits, so a GIF of it loops cleanly


def main() -> None:
    tmp    = tempfile.mkdtemp(prefix="tuisla-demo-")
    tuisla = os.path.join(tmp, "tuisla")
    fifo_p = os.path.join(tmp, "captions.fifo")
    conf   = os.path.join(tmp, "tmux.conf")
    shutil.copy(os.path.join(HERE, "..", "tuisla"), tuisla)
    os.mkfifo(fifo_p)
    with open(conf, "w") as f:
        f.write("set -g status off\n"
                "set -g escape-time 0\n"
                "set -g default-terminal screen-256color\n"
                "set -g pane-border-style fg=colour8\n"
                "set -g pane-active-border-style fg=colour8\n"
                # Title bar on each pane, so it's clear which one is the app.
                "set -g pane-border-status top\n"
                "set -g pane-border-format '#[reverse,bold] #{pane_title} #[default]'\n"
                "set -g allow-set-title off\n")

    env = {k: v for k, v in os.environ.items()
           if k not in ("TMUX", "TESLA_REFRESH_TOKEN", "MYTESLAMATE_TOKEN", "TESLA_VIN")}
    env.update(TERM="xterm-256color", XDG_STATE_HOME=os.path.join(tmp, "state"))

    def tmux(*args: str) -> None:
        subprocess.run(["tmux", "-L", SOCK, *args], check=True)

    caption_cmd = f"python3 -B {shlex.quote(os.path.join(HERE, 'captions.py'))} {shlex.quote(fifo_p)}"
    tuisla_cmd  = f"python3 -B {shlex.quote(tuisla)} -m ro -b"   # starts in black and white; b turns the colours on

    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe("tmux", ["tmux", "-L", SOCK, "-f", conf, "new-session", "-s", "demo",
                            "-x", str(COLS), "-y", str(ROWS), caption_cmd], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    start, events = time.time(), []
    utf8 = codecs.getincrementaldecoder("utf-8")("replace")   # chars may span reads

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while (left := end - time.time()) > 0:
            r, _, _ = select.select([fd], [], [], left)
            if not r:
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                return
            if not data:
                return
            events.append([time.time() - start, "o", utf8.decode(data)])

    try:
        pump(1.0)
        fifo = open(fifo_p, "w", buffering=1)      # captions.py has opened its end by now
        tmux("split-window", "-h", "-t", "demo:0", "-l", str(COLS - CAPTION_W - 1), tuisla_cmd)
        tmux("select-pane", "-t", "demo:0.0", "-T", "Animation table of content:")
        tmux("select-pane", "-t", "demo:0.1", "-T", "tuisla demo below:")
        fifo.write("0\n")
        pump(2.0)
        t0 = time.time() - start                  # both panes drawn: the cast starts here
        for step, keys, after in SCRIPT:
            if step is not None:
                fifo.write(f"{step}\n")
            for delay, key, *literal in keys:
                pump(delay)
                tmux("send-keys", "-t", "demo:0.1", *(["-l"] if literal else []), key)
                fifo.write(f"key {key}\n")
            pump(after)
        cut = time.time() - start
        fifo.write("end\n")
        fifo.close()
    finally:
        subprocess.run(["tmux", "-L", SOCK, "kill-server"], stderr=subprocess.DEVNULL)
        os.close(fd)
        os.waitpid(pid, 0)
        shutil.rmtree(tmp, ignore_errors=True)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps({"version": 2, "width": COLS, "height": ROWS,
                            "timestamp": int(start), "title": "tuisla demo (read-only mode)",
                            "env": {"TERM": "xterm-256color", "SHELL": "/bin/sh"}}) + "\n")
        # Output before t0 (tmux and tuisla starting up) is played instantly at
        # 0 s, so the cast opens on a full screen.  Drop whatever follows `cut`.
        for ts, kind, data in events:
            if ts < cut:
                f.write(json.dumps([round(max(0.0, ts - t0), 3), kind, data]) + "\n")
    print(f"wrote {OUT} ({cut - t0:.0f} s)")


if __name__ == "__main__":
    main()
