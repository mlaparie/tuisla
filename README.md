# tuisla

A Tesla dashboard for the terminal: battery, charging, climate, tyres and
locks at a glance, plus remote commands. One Python file, no dependencies
beyond Python 3 and `curl` (with HTTP/2).

Demo (ro mode, built-in demo data): `asciinema play demo.cast`

## Quick start

```sh
./tuisla          # no token yet: runs on demo data
./tuisla -l       # sign in to Tesla, then paste your MyTeslaMate API token
./tuisla          # live data; commands go through MyTeslaMate
```

Tokens are saved in `~/.local/state/tuisla/` (mode 600). `TESLA_REFRESH_TOKEN`
and `MYTESLAMATE_TOKEN` override them; `TESLA_VIN` picks a vehicle.

## Modes (`-m`, or `m` in the app)

- `mtm` (default): commands go through the [MyTeslaMate API](https://www.myteslamate.com/api/).
  You don't need a MyTeslaMate (hosted TeslaMate) instance, only their API,
  which is cheaper: pay-as-you-go credits, one per command. In their app, open
  the API tab (<https://app.myteslamate.com/fleet>), allow commands for your
  vehicle and copy the MyTeslaMate API token.
- `ro`: read-only, commands disabled.
- `vc`: Tesla's [vehicle-command](https://github.com/teslamotors/vehicle-command)
  proxy. Experimental: it needs a Fleet API app and a paired key.

Vehicle data is always read from Tesla's Owner API, so reading is free.

## Keys

`h` help · `?` command list · `:` type a command (Tab completes) · `m` mode ·
`r` refresh · `+`/`-` refresh rate · `u` units · `b` colors · `s` style ·
`i` invert · `z` log · `q` quit

See `./tuisla --help` and the header of `tuisla` for details.
