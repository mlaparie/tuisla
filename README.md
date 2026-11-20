# tuisla

A TUI to check on and control your Tesla from the comfort of your terminal:
battery, charging, climate, tyres and locks at a glance, and commands like
lock, climate or charge limit from the keyboard.

It runs on Linux, macOS or even Android (Termux).

![tuisla demo](demo/tuisla.gif)

*The left pane is just a table of contents; the actual app is on the
right only (demo data, read-only mode).*

## What you need

- Python 3 and `curl`.
- A Tesla account. Reading your car's information is free.
- A [MyTeslaMate API](https://www.myteslamate.com/api/)
  token is needed to send commands to the car. This is a pay-as-you-go thingie, about 1€ for 500 commands per month. You *do not* need a "MyTeslaMate instance" subscription, just the API.

## Setup

`tuisla` is just a standalone Python script, so you just need to have Python 3 and make the script executable with `chmod a+x tuisla`.

```sh
# First execution:
./tuisla --login  # will help you get and store your Tesla and MyTeslaMate API tokens

# From there, just:
./tuisla
```

You can skip the MyTeslaMate step if you don't want to send commands to the car. Without any login, `./tuisla` will just show demo data.

## Use

`h` help · `?` all commands · `:` type a command · `q` quit

## Modes

- `--mode mtm` (default, recommended), commands are sent to the car through the MyTeslaMate API.
- `--mode ro` (read-only), commands are checked for validity, but not sent.
- `--mode vc` (not implemented yet), this mode will allow sending commands through Tesla's own [vehicle-command](https://github.com/teslamotors/vehicle-command) proxy instead of MyTeslaMate, for those with a Tesla developer account and a key paired with their car.

See `./tuisla --help` for more options.
