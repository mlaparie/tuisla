# tuisla

A terminal app (TUI) to check on and control your Tesla: battery, charging,
climate, tyres and locks at a glance, and commands like lock, climate or
charge limit from the keyboard.

Written in Python, so it runs on Linux, macOS and even Android (Termux).

![tuisla demo](demo/tuisla.gif)

*In the demo, the left pane is just a table of contents; the app is on the
right (demo data, read-only mode).*

## What you need

- Python 3 and `curl`.
- A Tesla account. Reading your car's information is free.
- To send commands: a [MyTeslaMate API](https://www.myteslamate.com/api/)
  token, pay-as-you-go, about 1€ for 500 commands. No MyTeslaMate
  subscription needed, just the API.

## Setup

```sh
./tuisla -l    # sign in to Tesla in your browser, then paste your MyTeslaMate token
./tuisla
```

`-l` walks you through both logins; press Enter at the MyTeslaMate step if you
only want to read. Without any login, `./tuisla` shows demo data.

## Use

`h` help · `?` all commands · `:` type a command · `q` quit

Start with `-m ro` for read-only mode: commands are checked but not sent.
See `./tuisla --help` for more options.

The demo is recorded by `demo/record-tmux.py` (an Emacs org-present version:
`demo/record-emacs.py`).
