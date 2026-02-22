#!/usr/bin/env python3
# =============================================================================
#  teslui.py — A Tesla vehicle dashboard TUI (stdlib-only)
#
#  USAGE:  python3 teslui.py [--mode MODE] [--unit UNIT] [--invert] [--simple] [--bw]
#
#  MODES:  ro (read-only, default) | mtm (myteslamate) | vc (vehicle-command)
#  UNITS:  metric | us
#
#  ENV:
#    TESLA_REFRESH_TOKEN    Required for live mode. If missing, runs demo mode.
#    TESLA_VIN              Optional. Pin to a specific vehicle (needed for vc).
#    MYTESLAMATE_TOKEN      Required for --mode mtm.
#    VEHICLE_COMMAND_URL    Default: https://localhost:4443
#    VEHICLE_COMMAND_CERT   Default: cert.pem
# =============================================================================

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

OWNER_API = "https://owner-api.teslamotors.com/api/1"
AUTH_URL = "https://auth.tesla.com/oauth2/v3/token"
OWNER_CLIENT_ID = "ownerapi"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\(B")

DEMO_DATA = {
    "response": {
        "vin": "DEMOE1EA1NF000001",
        "state": "charging",
        "vehicle_config": {"car_type": "modely"},
        "vehicle_state": {
            "vehicle_name": "DEMO",
            "odometer": 18432,
            "car_version": "2026.2.3",
            "locked": True,
            "sentry_mode": True,
            "valet_mode": False,
            "df": 0,
            "pf": 0,
            "dr": 0,
            "pr": 0,
            "software_update": {"version": "2026.2.6", "status": "available"},
            "tpms_pressure_fl": 3.00,
            "tpms_pressure_fr": 3.05,
            "tpms_pressure_rl": 2.95,
            "tpms_pressure_rr": 3.00,
        },
        "charge_state": {
            "battery_level": 73,
            "battery_range": 218,
            "charging_state": "Charging",
            "charge_limit_soc": 80,
            "minutes_to_full_charge": 23,
            "charger_power": 7,
            "charger_voltage": 230,
            "charge_actual_current": 32,
            "charge_energy_added": 4.2,
            "battery_heater_on": True,
        },
        "climate_state": {
            "inside_temp": 22.5,
            "outside_temp": 8.0,
            "driver_temp_setting": 21.0,
            "is_climate_on": True,
            "defrost_mode": 0,
        },
        "drive_state": {"power": 2, "shift_state": None, "speed": None, "timestamp": 1771692668445},
    }
}


def die(msg: str) -> None:
    raise SystemExit(msg)


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def vlen(s: str) -> int:
    return len(strip_ansi(s))


def clamp_int(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x


def jget(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


@dataclasses.dataclass
class Colors:
    fancy: bool = True
    inverted: bool = False
    bw: bool = False

    # reset/bold/dim/rev
    R: str = "\x1b[0m"
    B: str = "\x1b[1m"
    DIM: str = "\x1b[2m"
    REV: str = "\x1b[7m"

    RED: str = "\x1b[31m"
    GRN: str = "\x1b[32m"
    YLW: str = "\x1b[33m"
    BLU: str = "\x1b[34m"
    MAG: str = "\x1b[35m"
    CYN: str = "\x1b[36m"
    GRY: str = "\x1b[90m"

    _base: Dict[str, str] = dataclasses.field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._base = {
            "R": self.R, "B": self.B, "DIM": self.DIM, "REV": self.REV,
            "RED": self.RED, "GRN": self.GRN, "YLW": self.YLW, "BLU": self.BLU,
            "MAG": self.MAG, "CYN": self.CYN, "GRY": self.GRY,
        }
        self.apply_bw()

    def apply_bw(self) -> None:
        self.R = self._base["R"]; self.B = self._base["B"]; self.DIM = self._base["DIM"]; self.REV = self._base["REV"]
        self.RED = self._base["RED"]; self.GRN = self._base["GRN"]; self.YLW = self._base["YLW"]; self.BLU = self._base["BLU"]
        self.MAG = self._base["MAG"]; self.CYN = self._base["CYN"]; self.GRY = self._base["GRY"]

        if self.bw:
            self.RED = ""
            self.GRN = ""
            self.YLW = ""
            self.BLU = ""
            self.MAG = ""
            self.CYN = ""
            self.GRY = "\x1b[90m"


class Term:
    def __init__(self) -> None:
        self.is_windows = (os.name == "nt")
        self._raw_enabled = False
        self._old_termios = None

    def write(self, s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()

    def get_size(self) -> Tuple[int, int]:
        try:
            import shutil
            sz = shutil.get_terminal_size(fallback=(80, 24))
            return (sz.columns, sz.lines)
        except Exception:
            return (80, 24)

    def alt_screen(self, on: bool) -> None:
        self.write("\x1b[?1049h" if on else "\x1b[?1049l")

    def cursor(self, on: bool) -> None:
        self.write("\x1b[?25h" if on else "\x1b[?25l")

    def invert_screen(self, on: bool) -> None:
        self.write("\x1b[?5h" if on else "\x1b[?5l")

    def home(self) -> None:
        self.write("\x1b[H")

    def clear_to_end(self) -> None:
        self.write("\x1b[J")

    def clear_line(self) -> None:
        self.write("\x1b[2K\r")

    def move(self, row0: int, col0: int) -> None:
        self.write(f"\x1b[{row0+1};{col0+1}H")

    def enable_raw(self) -> None:
        if self.is_windows:
            self._raw_enabled = True
            return
        if self._raw_enabled:
            return
        import termios, tty
        fd = sys.stdin.fileno()
        self._old_termios = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        self._raw_enabled = True

    def disable_raw(self) -> None:
        if self.is_windows:
            self._raw_enabled = False
            return
        if not self._raw_enabled:
            return
        import termios
        fd = sys.stdin.fileno()
        if self._old_termios is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios)
        self._raw_enabled = False

    def read_key_timeout(self, timeout_s: int) -> Optional[str]:
        if self.is_windows:
            import msvcrt
            end = time.time() + timeout_s
            while time.time() < end:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch == "\r":
                        return "\n"
                    return ch
                time.sleep(0.01)
            return None
        else:
            import select
            r, _, _ = select.select([sys.stdin], [], [], timeout_s)
            if not r:
                return None
            return sys.stdin.read(1)


@dataclasses.dataclass
class Frame:
    term_w: int
    content_w: int
    lbl_w: int = 9
    val_w: int = 20
    cat_labels: bool = False

    lines: List[str] = dataclasses.field(default_factory=list)
    maxvis: int = 0

    def fline(self, s: str = "") -> None:
        self.lines.append(s)
        self.maxvis = max(self.maxvis, vlen(s))

    def blank(self) -> None:
        self.fline("")

    def row2(self, c: Colors, ll: str, vl: str, lr: str, vr: str) -> None:
        half = self.content_w // 2

        def label_cell(txt: str) -> str:
            if c.fancy and self.cat_labels:
                return f"{c.GRY}{c.REV} {txt:<{self.lbl_w-1}}{c.R}"
            return f"{c.GRY}{txt:<{self.lbl_w}}{c.R}"

        left = f"{label_cell(ll)} {vl}"
        right = f"{label_cell(lr)} {vr}"
        lvis = vlen(left)
        pad = (half - lvis - 2)
        if pad < 0:
            pad = 0
        self.fline(f"  {left}{' ' * pad}  {right}")

    def row1(self, c: Colors, label: str, val: str) -> None:
        if c.fancy and self.cat_labels:
            lab = f"{c.GRY}{c.REV} {label:<{self.lbl_w-1}}{c.R}"
        else:
            lab = f"{c.GRY}{label:<{self.lbl_w}}{c.R}"
        self.fline(f"  {lab} {val}")

    def section(self, c: Colors, title: str) -> None:
        self.blank()
        self.fline(f"  {c.B}{c.MAG}{title}{c.R}")


def flush_frame(term: Term, c: Colors, frame: Frame) -> None:
    term_w, _ = term.get_size()
    w = min(frame.maxvis, term_w)
    margin = (term_w - w) // 2
    if margin < 0:
        margin = 0

    term.home()
    term.clear_to_end()
    for line in frame.lines:
        term.write((" " * margin) + line + c.R + "\n")
        

def two_col_title(content_w: int, left: str, right: str, *, shift_left: int = 0) -> str:
    """
    Place RIGHT at a fixed start column (start of right pane), with an optional
    left shift (used in fancy mode to compensate icon prefixes like "⚡ ").
    """
    half = content_w // 2
    right_start = half - shift_left

    lvis = vlen(left)
    gap = max(2, right_start - lvis)
    return f"{left}{' ' * gap}{right}"


class TeslaClient:
    def __init__(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token
        self.access_token = ""

    def _http(self, req: urllib.request.Request, ctx: Optional[ssl.SSLContext] = None) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
                data = r.read().decode("utf-8", "replace")
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from e
        except Exception as e:
            raise RuntimeError(str(e)) from e

    def refresh_access_token(self) -> None:
        form = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": OWNER_CLIENT_ID,
            "refresh_token": self.refresh_token,
            "scope": "openid email offline_access",
        }).encode("utf-8")
        req = urllib.request.Request(
            AUTH_URL,
            method="POST",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = self._http(req)
        at = resp.get("access_token") or ""
        if not at:
            raise RuntimeError("Token refresh failed (missing access_token)")
        self.access_token = at
        new_rt = resp.get("refresh_token") or ""
        if new_rt and new_rt != self.refresh_token:
            self.refresh_token = new_rt

    def api_get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            OWNER_API + path,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "teslui/1.0",
            },
        )
        return self._http(req)

    def api_post(self, url: str, ctx: Optional[ssl.SSLContext] = None) -> Dict[str, Any]:
        req = urllib.request.Request(
            url,
            method="POST",
            data=b"",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "teslui/1.0",
            },
        )
        return self._http(req, ctx=ctx)

    def get_vehicle_id(self, target_vin: str) -> str:
        resp = self.api_get("/products")
        items = resp.get("response") or []
        if not isinstance(items, list):
            return ""
        if target_vin:
            for it in items:
                if isinstance(it, dict) and it.get("vin") == target_vin:
                    return str(it.get("id_s") or it.get("id") or "")
            return ""
        for it in items:
            if isinstance(it, dict) and it.get("vin"):
                return str(it.get("id_s") or it.get("id") or "")
        return ""

    def wake_up(self, vid: str) -> None:
        try:
            _ = self.api_post(f"{OWNER_API}/vehicles/{vid}/wake_up")
        except Exception:
            pass

    def get_vehicle_data(self, vid: str) -> Optional[Dict[str, Any]]:
        resp = self.api_get(f"/vehicles/{vid}/vehicle_data")
        vin = jget(resp, "response.vin", "")
        return resp if vin else None


def make_bat_bar(c: Colors, pct: int, width: int = 12) -> str:
    pct = clamp_int(int(pct), 0, 100)
    filled = (pct * width) // 100
    empty = width - filled
    if pct >= 70:
        col = c.GRN
    elif pct >= 30:
        col = c.YLW
    else:
        col = c.RED
    blocks = ("█" * filled) + (f"{c.GRY}" + ("░" * empty) if empty else "")
    return f"{col}{blocks}{col}{c.R} {col}{pct}%{c.R}"


def fmt_time_hhmm(minutes: int) -> str:
    minutes = max(0, int(minutes))
    return f"{minutes//60:02d}:{minutes%60:02d}"


def miles_to_km(mi: float) -> int:
    return int(round(mi * 1.60934))


def c_to_f(c: float) -> int:
    return int(round((c * 9.0 / 5.0) + 32.0))


def bar_to_psi(bar: float) -> int:
    return int(round(bar * 14.5037738))


@dataclasses.dataclass
class State:
    mode: str = "ro"          # ro|mtm|vc
    unit: str = "metric"      # metric|us
    refresh_interval: int = 5
    show_help: bool = False
    cmd_msg: str = ""
    target_vin: str = ""
    myteslamate_token: str = ""
    vehicle_command_url: str = "https://localhost:4443"
    vehicle_command_cert: str = "cert.pem"


def render_help(term: Term, c: Colors, st: State) -> None:
    term_w, _ = term.get_size()
    frame = Frame(term_w=term_w, content_w=min(80, term_w))
    frame.blank()

    def kcap(k: str, desc: str) -> str:
        return f"{c.REV} {k:<1} {c.R} {desc}"

    frame.section(c, "TESLUI")
    frame.row2(c, kcap("m", "mode"), "", kcap("u", "units"), "")
    frame.row2(c, kcap("r", "refresh"), "", kcap("s", "style"), "")
    frame.row2(c, kcap("-", "refresh -5s"), "", kcap("i", "invert"), "")
    frame.row2(c, kcap("+", "refresh +5s"), "", kcap("b", "bw/color"), "")
    frame.row1(c, kcap("q", "quit"), "")

    # --- Build COMMANDS section in a separate frame using the SAME formatting ---
    # This lets us:
    #  - keep COMMANDS hidden in ro (like bash)
    #  - still stabilize centering (no jump) by taking cmd_frame.maxvis into account
    cmd_frame = Frame(term_w=term_w, content_w=frame.content_w, lbl_w=frame.lbl_w, val_w=frame.val_w)
    cmd_frame.section(c, "COMMANDS")
    cmd_frame.row2(c, kcap("h", "honk"), "", kcap("f", "flash lights"), "")
    cmd_frame.row2(c, kcap("L", "unlock"), "", kcap("o", "open port"), "")
    cmd_frame.row2(c, kcap("l", "lock"), "", kcap("p", "charge start"), "")
    cmd_frame.row2(c, kcap("C", "climate on"), "", kcap("P", "charge stop"), "")
    cmd_frame.row2(c, kcap("c", "climate off"), "", kcap(":", "enter command"), "")

    # Stabilize centering width even when COMMANDS is hidden
    frame.maxvis = max(frame.maxvis, cmd_frame.maxvis)

    # Match bash: only show COMMANDS when not in ro
    if st.mode != "ro":
        for s in cmd_frame.lines:
            frame.fline(s)

    frame.blank()
    frame.row2(
        c,
        "mode:", f"{c.GRY}{st.mode}{c.R}",
        "style:", f"{c.GRY}{'fancy' if c.fancy else 'minimal'}{c.R}",
    )
    frame.row2(
        c,
        "refresh:", f"{c.GRY}{st.refresh_interval}s{c.R}",
        "colors:", f"{c.GRY}{'inv' if c.inverted else 'normal'}{'/bw' if c.bw else '/col'}{c.R}",
    )
    frame.blank()
    frame.row1(c, f"{c.GRY}? close help{c.R}", "")

    flush_frame(term, c, frame)
    

def run_cmd(client: TeslaClient, st: State, vid: str, ep: str, label: str, c: Colors) -> str:
    if st.mode == "ro":
        return f"? help    {c.RED}✗ commands disabled in ro (press m){c.R}"

    try:
        if st.mode == "mtm":
            if not st.myteslamate_token:
                return f"? help    {c.RED}✗ MYTESLAMATE_TOKEN missing{c.R}"
            url = (
                f"https://api.myteslamate.com/api/1/vehicles/{vid}/command/{ep}"
                f"?token={urllib.parse.quote(st.myteslamate_token)}"
            )
            resp = client.api_post(url)
        elif st.mode == "vc":
            if not st.target_vin:
                return f"? help    {c.RED}✗ TESLA_VIN required for vc{c.R}"
            cafile = st.vehicle_command_cert or "cert.pem"
            ctx = ssl.create_default_context(cafile=cafile)
            base = st.vehicle_command_url.rstrip("/")
            url = f"{base}/api/1/vehicles/{urllib.parse.quote(st.target_vin)}/command/{ep}"
            resp = client.api_post(url, ctx=ctx)
        else:
            return f"? help    {c.RED}✗ unknown mode{c.R}"
    except Exception as e:
        return f"? help    {c.RED}✗ {str(e)[:80]}{c.R}"

    ok = bool(jget(resp, "response.result", False))
    reason = str(jget(resp, "response.reason", "") or jget(resp, "error", "") or "failed")
    return (f"{c.GRN}✓ {label}{c.R}") if ok else (f"? help    {c.RED}✗ {reason}{c.R}")


def render_dashboard(term: Term, c: Colors, st: State, data: Dict[str, Any]) -> None:
    term_w, _ = term.get_size()
    lbl_w, val_w = 9, 20
    col_w = 2 + lbl_w + val_w
    content_w = min((col_w * 2 + 2), term_w)
    frame = Frame(term_w=term_w, content_w=content_w, lbl_w=lbl_w, val_w=val_w)

    dist_u = "km" if st.unit == "metric" else "mi"
    temp_u = "°C" if st.unit == "metric" else "°F"
    press_u = "bar" if st.unit == "metric" else "psi"

    name = str(jget(data, "response.vehicle_state.vehicle_name", "Tesla"))
    model = str(jget(data, "response.vehicle_config.car_type", "?")).upper()
    vin = str(jget(data, "response.vin", "?"))
    state = str(jget(data, "response.state", "unknown"))
    sw = str(jget(data, "response.vehicle_state.car_version", "?")).split(" ")[0]
    swua = str(jget(data, "response.vehicle_state.software_update.status", "unknown"))
    odo = int(round(float(jget(data, "response.vehicle_state.odometer", 0) or 0)))

    bat = int(float(jget(data, "response.charge_state.battery_level", 0) or 0))
    rng = int(round(float(jget(data, "response.charge_state.battery_range", 0) or 0)))
    chg_state = str(jget(data, "response.charge_state.charging_state", "Disconnected")).lower()
    chg_limit = int(float(jget(data, "response.charge_state.charge_limit_soc", 0) or 0))
    chg_mins = int(float(jget(data, "response.charge_state.minutes_to_full_charge", 0) or 0))
    chg_kw = int(float(jget(data, "response.charge_state.charger_power", 0) or 0))
    chg_volts = int(float(jget(data, "response.charge_state.charger_voltage", 0) or 0))
    chg_current = int(float(jget(data, "response.charge_state.charge_actual_current", 0) or 0))
    chg_added = float(jget(data, "response.charge_state.charge_energy_added", 0) or 0)
    bat_heat = bool(jget(data, "response.charge_state.battery_heater_on", False))
    draw = int(float(jget(data, "response.drive_state.power", 0) or 0))

    inside = float(jget(data, "response.climate_state.inside_temp", 0) or 0)
    outside = float(jget(data, "response.climate_state.outside_temp", 0) or 0)
    set_temp = float(jget(data, "response.climate_state.driver_temp_setting", 0) or 0)
    climate_on = bool(jget(data, "response.climate_state.is_climate_on", False))
    defrost = int(float(jget(data, "response.climate_state.defrost_mode", 0) or 0))

    fl = float(jget(data, "response.vehicle_state.tpms_pressure_fl", 0) or 0)
    fr = float(jget(data, "response.vehicle_state.tpms_pressure_fr", 0) or 0)
    rl = float(jget(data, "response.vehicle_state.tpms_pressure_rl", 0) or 0)
    rr = float(jget(data, "response.vehicle_state.tpms_pressure_rr", 0) or 0)

    locked = bool(jget(data, "response.vehicle_state.locked", False))
    sentry = bool(jget(data, "response.vehicle_state.sentry_mode", False))
    valet = bool(jget(data, "response.vehicle_state.valet_mode", False))
    doors_open = sum(1 for k in ("df", "pf", "dr", "pr") if int(jget(data, f"response.vehicle_state.{k}", 0) or 0) > 0)

    if st.unit == "metric":
        odo = miles_to_km(odo)
        rng = miles_to_km(rng)
    else:
        inside = c_to_f(inside)
        outside = c_to_f(outside)
        set_temp = c_to_f(set_temp)
        fl = bar_to_psi(fl)
        fr = bar_to_psi(fr)
        rl = bar_to_psi(rl)
        rr = bar_to_psi(rr)

    sc = c.GRN
    if state in ("asleep", "offline"):
        sc = c.GRY
    if state == "charging":
        sc = c.YLW

    bat_bar = make_bat_bar(c, bat)

    cs_c = c.GRY
    if chg_state == "charging":
        cs_c = c.YLW
    if chg_state == "complete":
        cs_c = c.GRN

    clm_c, clm_l = (c.GRN, "on") if climate_on else (c.GRY, "off")

    def_c, def_l = c.GRY, "off"
    if defrost == 1:
        def_c, def_l = c.YLW, "on"
    elif defrost == 2:
        def_c, def_l = c.RED, "max"

    bat_c, bat_l = (c.GRN, "on") if bat_heat else (c.GRY, "off")

    dra_c = c.GRY
    if draw > 0:
        dra_c = c.R
    if 1 < draw <= 2:
        dra_c = c.YLW
    if draw > 2:
        dra_c = c.RED

    lk_c, lk_l = (c.GRN, "locked") if locked else (c.RED, "unlocked")
    sn_c, sn_l = (c.GRN, "active") if sentry else (c.GRY, "off")
    dr_c, dr_l = (c.RED, f"{doors_open} open") if doors_open > 0 else (c.GRN, "closed")
    vl_c, vl_l = (c.GRN, "on") if valet else (c.GRY, "off")

    mode_c = c.GRN if st.mode in ("mtm", "vc") else c.GRY

    px_bat = "⚡ " if c.fancy else ""
    px_clm = "🌡 " if c.fancy else ""
    px_drv = "🚗 " if c.fancy else ""
    px_sec = "🛡 " if c.fancy else ""

    frame.blank()
    frame.cat_labels = False

    ts = _dt.datetime.now().strftime("%b %d, %H:%M")
    frame.row2(
        c,
        f"{c.B}{c.R}{name} {model}{c.R}, {odo} {dist_u}",
        "",
        f"{sc}{state}{c.R}",
        f"{c.GRY}[{mode_c}{st.mode}{c.R}{c.GRY}]{c.R}",
    )
    upd = f"{c.BLU}⁺{c.R}" if swua == "available" else ""
    frame.row2(c, f"{c.GRY}[{vin}]{c.R}", f"{c.GRY}v{sw}{c.R}{upd}", f"{c.GRY}{ts}{c.R}", "")

    # icons add 2 visible chars ("⚡ "), so shift right title left in fancy mode
    frame.section(c, two_col_title(content_w, f"{px_bat}ENERGY", f"{px_clm}THERMAL",
                                  shift_left=(1 if c.fancy else 0)))
    frame.cat_labels = True

    added = f"{c.GRN}+{chg_added:g} kWh{c.R}" if chg_state != "disconnected" else ""
    frame.row2(c, "Battery", bat_bar, "Outside", f"{outside}{temp_u}")
    frame.row2(c, "Range", f"{rng} {dist_u}", "Inside", f"{inside}{temp_u}")
    frame.row2(c, "Draw", f"{dra_c}{draw} kW{c.R}", "Target", f"{set_temp}{temp_u}")
    frame.row2(c, "Charge", f"{cs_c}{chg_state}{c.R} {added}", "Control", f"{clm_c}{clm_l}{c.R}")
    frame.row2(c, "Limit", f"{chg_limit}%", "Defrost", f"{def_c}{def_l}{c.R}")
    if chg_state != "disconnected":
        frame.row2(c, "Power", f"{c.YLW}{chg_kw} kW ({chg_volts} V, {chg_current} A){c.R}", "Battery", "")
        frame.row2(c, "End in", fmt_time_hhmm(chg_mins), " heater", f"{bat_c}{bat_l}{c.R}")

    # icons add 2 visible chars ("⚡ "), so shift right title left in fancy mode
    frame.section(c, two_col_title(content_w, f"{px_drv}WHEELS", f"{px_sec}PARKING",
                                  shift_left=(1 if c.fancy else 0)))
    frame.row2(c, "F left", f"{fl:.2f} {press_u}" if st.unit == "metric" else f"{int(fl)} {press_u}", "Status", f"{lk_c}{lk_l}{c.R}")
    frame.row2(c, "F right", f"{fr:.2f} {press_u}" if st.unit == "metric" else f"{int(fr)} {press_u}", "Panels", f"{dr_c}{dr_l}{c.R}")
    frame.row2(c, "R left", f"{rl:.2f} {press_u}" if st.unit == "metric" else f"{int(rl)} {press_u}", "Sentry", f"{sn_c}{sn_l}{c.R}")
    frame.row2(c, "R right", f"{rr:.2f} {press_u}" if st.unit == "metric" else f"{int(rr)} {press_u}", "Valet", f"{vl_c}{vl_l}{c.R}")

    frame.blank()
    frame.cat_labels = False
    frame.row1(c, st.cmd_msg if st.cmd_msg else f"{c.GRY}? help{c.R}", "")

    flush_frame(term, c, frame)
    st.cmd_msg = ""


def prompt_command(term: Term, c: Colors) -> str:
    _, term_h = term.get_size()
    row = max(0, term_h - 2)
    term.move(row, 0)
    term.clear_line()
    term.write(f"{c.B}:{c.R} ")
    term.cursor(True)

    was_windows = (os.name == "nt")
    if not was_windows:
        term.disable_raw()

    try:
        line = sys.stdin.readline()
    finally:
        if not was_windows:
            term.enable_raw()
        term.cursor(False)
        term.move(row, 0)
        term.clear_line()

    line = (line or "").rstrip("\r\n")
    if line == "\x1b":
        return ""
    return line


def handle_key(term: Term, c: Colors, st: State, client: Optional[TeslaClient], vid: str, key: Optional[str]) -> bool:
    """
    returns True if caller should fetch fresh data; False otherwise.
    """
    if key is None:
        return True  # timeout => refresh

    if key in ("q", "Q"):
        raise KeyboardInterrupt

    if key == "?":
        st.show_help = not st.show_help
        return False

    if key == "i":
        c.inverted = not c.inverted
        term.invert_screen(c.inverted)
        return False

    if key == "b":
        c.bw = not c.bw
        c.apply_bw()
        return False

    if key in ("m", "M"):
        st.mode = {"ro": "mtm", "mtm": "vc", "vc": "ro"}.get(st.mode, "ro")
        return False

    if key == "u":
        st.unit = "us" if st.unit == "metric" else "metric"
        return False

    if key == "s":
        c.fancy = not c.fancy
        return False

    if key == "r":
        st.show_help = False
        return True

    if key == "+":
        st.refresh_interval += 5
        if st.refresh_interval == 6:
            st.refresh_interval = 5
        return False

    if key == "-":
        st.refresh_interval -= 5
        if st.refresh_interval <= 1:
            st.refresh_interval = 1
        return False

    # Always recognize command keys, even if commands are currently unavailable
    cmd_keys = {"h", "f", "L", "l", "C", "c", "p", "P", "o", ":"}
    if (not st.show_help) and (key in cmd_keys):
        if client is None:
            # demo mode (no token) => explicit feedback instead of "nothing happens"
            st.cmd_msg = f"? help    {c.RED}✗ commands unavailable (no TESLA_REFRESH_TOKEN){c.R}"
            return False
        if st.mode == "ro":
            st.cmd_msg = f"? help    {c.RED}✗ commands disabled in ro (press m){c.R}"
            return False

        if key == "h":
            st.cmd_msg = run_cmd(client, st, vid, "honk_horn", "NOOT NOOT!", c)
        elif key == "f":
            st.cmd_msg = run_cmd(client, st, vid, "flash_lights", "Lights flashed", c)
        elif key == "L":
            st.cmd_msg = run_cmd(client, st, vid, "door_unlock", "Unlocked", c)
        elif key == "l":
            st.cmd_msg = run_cmd(client, st, vid, "door_lock", "Locked", c)
        elif key == "C":
            st.cmd_msg = run_cmd(client, st, vid, "auto_conditioning_start", "Climate on", c)
        elif key == "c":
            st.cmd_msg = run_cmd(client, st, vid, "auto_conditioning_stop", "Climate off", c)
        elif key == "p":
            st.cmd_msg = run_cmd(client, st, vid, "charge_start", "Charging started", c)
        elif key == "P":
            st.cmd_msg = run_cmd(client, st, vid, "charge_stop", "Charging stopped", c)
        elif key == "o":
            st.cmd_msg = run_cmd(client, st, vid, "charge_port_door_open", "Port opened", c)
        elif key == ":":
            cmd = prompt_command(term, c)
            cmd_map = {
                "honk": ("honk_horn", "NOOT NOOT!"),
                "flash": ("flash_lights", "Lights flashed"),
                "lock": ("door_lock", "Locked"),
                "unlock": ("door_unlock", "Unlocked"),
                "climate on": ("auto_conditioning_start", "Climate on"),
                "climate off": ("auto_conditioning_stop", "Climate off"),
                "charge on": ("charge_start", "Charging started"),
                "charge off": ("charge_stop", "Charging stopped"),
                "port open": ("charge_port_door_open", "Port opened"),
                "port close": ("charge_port_door_close", "Port closed"),
            }
            if cmd == "":
                pass
            elif cmd in cmd_map:
                ep, label = cmd_map[cmd]
                st.cmd_msg = run_cmd(client, st, vid, ep, label, c)
            else:
                st.cmd_msg = f"? help    {c.RED}Unknown command: {cmd}{c.R}"

        return False

    return False


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("-m", "--mode", default="ro", choices=["ro", "mtm", "vc"])
    ap.add_argument("-u", "--unit", default="metric", choices=["metric", "us"])
    ap.add_argument("-i", "--invert", action="store_true")
    ap.add_argument("-s", "--simple", action="store_true", help="Disable fancy style")
    ap.add_argument("-b", "--bw", action="store_true", help="Disable colors")
    args = ap.parse_args()

    st = State(
        mode=args.mode,
        unit=args.unit,
        target_vin=os.environ.get("TESLA_VIN", "") or "",
        myteslamate_token=os.environ.get("MYTESLAMATE_TOKEN", "") or "",
        vehicle_command_url=os.environ.get("VEHICLE_COMMAND_URL", "https://localhost:4443") or "https://localhost:4443",
        vehicle_command_cert=os.environ.get("VEHICLE_COMMAND_CERT", "cert.pem") or "cert.pem",
    )

    refresh_token = os.environ.get("TESLA_REFRESH_TOKEN", "") or ""
    c = Colors(fancy=(not args.simple), inverted=bool(args.invert), bw=bool(args.bw))

    term = Term()
    client: Optional[TeslaClient] = None
    vid = ""

    term.alt_screen(True)
    term.cursor(False)
    term.invert_screen(c.inverted)
    term.enable_raw()

    def cleanup() -> None:
        try:
            term.disable_raw()
        except Exception:
            pass
        try:
            term.cursor(True)
        except Exception:
            pass
        try:
            term.invert_screen(False)
        except Exception:
            pass
        try:
            term.alt_screen(False)
        except Exception:
            pass

    try:
        # DEMO MODE
        if not refresh_token:
            while True:
                if st.show_help:
                    render_help(term, c, st)
                else:
                    render_dashboard(term, c, st, {"response": DEMO_DATA["response"]})

                key = term.read_key_timeout(st.refresh_interval)
                _ = handle_key(term, c, st, None, "", key)
            # unreachable

        # LIVE MODE
        client = TeslaClient(refresh_token)
        term.home(); term.clear_to_end()
        term.write("Authenticating…\n")
        client.refresh_access_token()
        term.write("Looking up vehicle…\n")
        vid = client.get_vehicle_id(st.target_vin)
        term.write(f"Connected: {vid} [{st.mode}]\n")
        if not vid:
            die("No vehicle found — check TESLA_VIN or token")

        time.sleep(0.5)

        data: Optional[Dict[str, Any]] = None

        while True:
            try:
                data = client.get_vehicle_data(vid)
            except Exception:
                data = None

            if not data:
                try:
                    term.home(); term.clear_to_end()
                    term.write(f"{c.YLW}waking vehicle…{c.R}\n")
                    client.wake_up(vid)
                except Exception:
                    pass

                for i in range(12):
                    time.sleep(3)
                    try:
                        data = client.get_vehicle_data(vid)
                        if data:
                            break
                    except Exception:
                        data = None
                    term.home(); term.clear_to_end()
                    term.write(f"{c.YLW}waking… ({i+1}/12){c.R}\n")

            if not data:
                time.sleep(2)
                continue

            while True:
                if st.show_help:
                    render_help(term, c, st)
                else:
                    render_dashboard(term, c, st, data)

                key = term.read_key_timeout(st.refresh_interval)
                fetch_now = handle_key(term, c, st, client, vid, key)
                if fetch_now:
                    break

    except KeyboardInterrupt:
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
