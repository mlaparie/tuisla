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
- On Linux, `xdg-mime` (package `xdg-utils` on Guix and most distros) so `--login` can catch the Tesla sign-in link by itself. Without it, you have to copy that link from the browser by hand.
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
- `--mode vc`, commands are signed by tuisla itself with your own key, through Tesla's [vehicle-command](https://github.com/teslamotors/vehicle-command) proxy, and sent with your own Tesla developer app instead of MyTeslaMate. Run `./tuisla --setup-vc` once (it runs `tuisla-setup-vc`, which must sit next to `tuisla`): it walks you through every step (keys, publishing the public key on a free GitHub Pages site, the Tesla developer app, adding the key to the car from the Tesla app) and checks each one. You need [Go](https://go.dev/) to install the proxy, `openssl`, and a payment card on the Tesla developer site; Tesla's $10 monthly credit covers a personal car. Once set up, vc mode also works without `--login-tesla`, but vehicle data then comes from the billed Fleet API, so tuisla refreshes every 60 s at most.

See `./tuisla --help` for more options.

## Commands

Press `?` for the full list. Besides the usual lock, climate and charging commands, there are seat heating and cooling (`seat heat driver 2`), climate keeper and dog mode (`keeper dog`), cabin overheat protection, Guest Mode, PIN to Drive, speed limit, renaming the car, sending a destination (`navigate 1 Main St, Springfield`), Homelink, waking the car, and two read-only ones: `map` (the car's location on OpenStreetMap) and `chargers` (nearby Superchargers with free stalls).

Not possible: Sentry Mode and dashcam clips are only stored on the car's USB drive, and the live Sentry camera view only works in Tesla's own app; no API gives access to them.
