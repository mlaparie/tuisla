#!/usr/bin/env python3
"""Record the org-present version of the tuisla demo as an asciicast: Emacs
(emacs -Q -nw) with slides.org on the left and tuisla in eat on the right,
driven by emacs-demo.el.  tuisla runs on its built-in demo data, in
read-only mode, from a temporary copy (so it logs there and sees no tokens).

Usage: demo/record-emacs.py [OUT.cast]     (default: demo/tuisla-emacs.cast)
Needs: emacs with org-present and eat, python3."""
import codecs, fcntl, json, os, pty, select, shutil, signal, struct, sys, tempfile, termios, time

HERE       = os.path.dirname(os.path.abspath(__file__))
OUT        = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "tuisla-emacs.cast"))
COLS, ROWS = 160, 40
TIMEOUT    = 150


def main() -> None:
    tmp    = tempfile.mkdtemp(prefix="tuisla-demo-")
    tuisla = os.path.join(tmp, "tuisla")
    shutil.copy(os.path.join(HERE, "..", "tuisla"), tuisla)

    env = {k: v for k, v in os.environ.items()
           if k not in ("TMUX", "TESLA_REFRESH_TOKEN", "MYTESLAMATE_TOKEN", "TESLA_VIN")}
    env.update(TERM="xterm-256color", COLORTERM="truecolor",
               XDG_STATE_HOME=os.path.join(tmp, "state"),
               DEMO_ORG=os.path.join(HERE, "slides.org"), DEMO_TUISLA=tuisla)

    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe("emacs", ["emacs", "-Q", "-nw", "-l", os.path.join(HERE, "emacs-demo.el")], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    start, events = time.time(), []
    utf8 = codecs.getincrementaldecoder("utf-8")("replace")   # chars may span reads
    try:
        while time.time() - start < TIMEOUT:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    break
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            events.append([time.time() - start, "o", utf8.decode(data)])
        else:
            os.kill(pid, signal.SIGTERM)
            sys.exit("timed out")
    finally:
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

    # Emacs first draws *scratch* and waits on terminal queries nobody answers;
    # play that instantly and start at the full redraw showing the title slide.
    # End at the marker emacs-demo.el prints before quitting, so a GIF loops.
    shown = next(ts for ts, _, d in events if "tuisla" in d)
    t0    = max([ts for ts, _, d in events if ts <= shown and "\x1b[2J" in d] or [0])
    cut   = next(ts for ts, _, d in events if "tuisla-demo-end" in d)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps({"version": 2, "width": COLS, "height": ROWS,
                            "timestamp": int(start), "title": "tuisla demo (read-only mode)",
                            "env": {"TERM": "xterm-256color", "SHELL": "/bin/sh"}}) + "\n")
        for ts, kind, data in events:
            if ts < cut:
                f.write(json.dumps([round(max(0.0, ts - t0), 3), kind, data]) + "\n")
    print(f"wrote {OUT} ({cut - t0:.0f} s)")


if __name__ == "__main__":
    main()
