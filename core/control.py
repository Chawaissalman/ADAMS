"""Control layer: PID loops, PLC state machine, supervisory optimizer.

Ported from the validated notebook. The PLC runs deterministic safety + PID
control; the Supervisor proposes setpoints/modes that the PLC may override.
"""
from __future__ import annotations
import math
import numpy as np
from enum import Enum
from dataclasses import dataclass


class PID:
    def __init__(self, Kp, Ki, Kd, out_min=0.0, out_max=1.0,
                 setpoint=0.0, reverse=False):
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        self.out_min, self.out_max = out_min, out_max
        self.setpoint = setpoint
        self.reverse = reverse
        self._i = 0.0; self._prev = None; self.enabled = True

    def reset(self):
        self._i = 0.0; self._prev = None

    def step(self, pv, dt):
        if not self.enabled:
            return self.out_min
        err = (self.setpoint - pv)
        if self.reverse:
            err = -err
        self._i += err * dt
        d = 0.0 if self._prev is None else (err - self._prev) / dt
        self._prev = err
        out = self.Kp * err + self.Ki * self._i + self.Kd * d
        out_c = min(max(out, self.out_min), self.out_max)
        if out != out_c and self.Ki != 0:
            self._i -= (out - out_c) / self.Ki
        return out_c


class State(Enum):
    OFF = 0; PRECHECK = 1; STARTUP = 2; NORMAL_FREE_COOLING = 3
    NORMAL_HEAT_REUSE = 4; NORMAL_CHILLER_ASSIST = 5
    WARNING = 6; TRIP = 7; SHUTDOWN = 8


STATE_ORDER = {s.name: i for i, s in enumerate(State)}


@dataclass
class Limits:
    chip_warn: float = 80; chip_trip: float = 90
    p_high_warn: float = 20; p_high_trip: float = 23
    p_low_warn: float = 6; p_low_trip: float = 4
    level_low_warn: float = 20; level_low_trip: float = 10
    level_high_warn: float = 85; level_high_trip: float = 95
    flow_low_warn: float = 0.6; flow_low_trip: float = 0.4
    tcond_warn: float = 63; tcond_trip: float = 68
    tw_in_chiller: float = 33
    reuse_min_Twout: float = 45


def faults_ok(faults):
    return [] if any(f in faults for f in ("estop", "leak")) else ["reuse"]


class PLCController:
    def __init__(self, A, limits=None):
        self.A = A; self.L = limits or Limits()
        self.state = State.OFF; self.prev_state = State.OFF
        self.t_in_state = 0.0
        self.pid_pump = PID(0.04, 0.01, 0.0, 0.15, 1.0, reverse=True)
        self.pid_V1 = PID(0.05, 0.02, 0.0, 0.1, 1.0, reverse=True)
        self.pid_V2 = PID(0.06, 0.03, 0.0, 0.0, 1.0, reverse=False)
        self.pid_water = PID(0.08, 0.03, 0.0, 0.2, 1.0, reverse=True)
        self.cmd = {"pump": 0.0, "V1": 0.5, "V2": 0.3, "water": 0.4,
                    "chiller": 0.0, "3w": 0.0}
        self.alarms = []; self.trips = []
        self.start_cmd = False; self.reset_cmd = False
        self.chiller_on = False; self.reuse_on = False
        self.ramp = {"pump": 0.08, "V1": 0.15, "V2": 0.15,
                     "water": 0.12, "3w": 0.1}

    def validate(self, pv):
        bad = []
        checks = {"Tchip": (0, 125), "Tcond": (0, 120), "Tevap": (-10, 90),
                  "Pcond": (0.5, 30), "Pevap": (0.5, 30), "level": (0, 100),
                  "mdot": (0, 3), "Tw_in": (0, 60), "Tw_out": (0, 80)}
        clean = dict(pv)
        for k, (lo, hi) in checks.items():
            v = pv.get(k, np.nan)
            if v is None or (isinstance(v, float) and math.isnan(v)) or not (lo <= v <= hi):
                bad.append(k)
                clean[k] = pv.get(k + "_last", (lo + hi) / 2)
        return clean, bad

    def evaluate_safety(self, pv, faults):
        self.alarms = []; self.trips = []
        L = self.L
        start_inhibit = self.state in (State.OFF, State.PRECHECK, State.STARTUP)

        def chk(name, val, warn, trip, hi=True):
            if hi:
                if val >= trip: self.trips.append(name)
                elif val >= warn: self.alarms.append(name)
            else:
                if val <= trip: self.trips.append(name)
                elif val <= warn: self.alarms.append(name)

        chk("HiChipTemp", pv["Tchip"], L.chip_warn, L.chip_trip, True)
        chk("HiPress", pv["Pcond"], L.p_high_warn, L.p_high_trip, True)
        if not start_inhibit:
            chk("LoPress", pv["Pevap"], L.p_low_warn, L.p_low_trip, False)
        chk("LoLevel", pv["level"], L.level_low_warn, L.level_low_trip, False)
        chk("HiLevel", pv["level"], L.level_high_warn, L.level_high_trip, True)
        if not start_inhibit:
            chk("LoFlow", pv["mdot"], L.flow_low_warn, L.flow_low_trip, False)
        chk("HiCondTemp", pv["Tcond"], L.tcond_warn, L.tcond_trip, True)
        for f in faults:
            if f in ("estop", "leak", "pump_fault", "water_flow_fail"):
                self.trips.append(f)
            if f.startswith("sensor:"):
                self.alarms.append(f)
        return len(self.trips) > 0

    def step_state(self, pv, faults, supervisor, dt):
        self.t_in_state += dt
        tripped = self.evaluate_safety(pv, faults)
        s = self.state
        if tripped and s not in (State.TRIP, State.OFF, State.SHUTDOWN):
            self._go(State.TRIP); return
        if s == State.OFF:
            if self.start_cmd and not tripped:
                self._go(State.PRECHECK)
        elif s == State.PRECHECK:
            permissives = (not tripped and len(self.validate(pv)[1]) == 0
                           and pv["level"] > self.L.level_low_warn)
            if permissives:
                self._go(State.STARTUP)
            elif self.t_in_state > 10:
                self._go(State.OFF)
        elif s == State.STARTUP:
            stable = (pv["mdot"] > self.L.flow_low_warn and
                      pv["level"] > self.L.level_low_warn and
                      pv["Pevap"] > self.L.p_low_warn and self.t_in_state > 5)
            if stable:
                self._go(State.NORMAL_FREE_COOLING)
        elif s in (State.NORMAL_FREE_COOLING, State.NORMAL_HEAT_REUSE,
                   State.NORMAL_CHILLER_ASSIST):
            want = supervisor.get("mode", "free")
            if pv["Tw_in"] > self.L.tw_in_chiller or pv["Pcond"] > self.L.tcond_warn:
                self._go(State.NORMAL_CHILLER_ASSIST); self.chiller_on = True
            elif want == "reuse" and pv["Tw_out"] >= self.L.reuse_min_Twout and "reuse" in faults_ok(faults):
                self._go(State.NORMAL_HEAT_REUSE); self.reuse_on = True; self.chiller_on = False
            else:
                self._go(State.NORMAL_FREE_COOLING); self.chiller_on = False; self.reuse_on = False
        elif s == State.WARNING:
            if not self.alarms:
                self._go(State.NORMAL_FREE_COOLING)
        elif s == State.TRIP:
            if self.reset_cmd and not tripped:
                self._go(State.OFF)
        elif s == State.SHUTDOWN:
            if self.t_in_state > 5:
                self._go(State.OFF)

    def _go(self, ns):
        if ns != self.state:
            self.prev_state = self.state; self.state = ns; self.t_in_state = 0.0

    def actuate(self, pv, supervisor, dt):
        if self.state in (State.TRIP, State.OFF):
            tgt = {"pump": 0.0, "V1": 0.7, "V2": 0.0,
                   "water": 1.0 if self.state == State.TRIP else 0.0,
                   "chiller": 0.0, "3w": 0.0}
        elif self.state in (State.PRECHECK, State.STARTUP):
            tgt = {"pump": 0.5, "V1": 0.6, "V2": 0.4, "water": 0.5,
                   "chiller": 0.0, "3w": 0.0}
        else:
            self.pid_pump.setpoint = self.A.T_chip_target_C
            self.pid_V1.setpoint = supervisor.get("Pcond_sp", self.A.T_cond_C / 4)
            self.pid_V2.setpoint = supervisor.get("level_sp", 60.0)
            self.pid_water.setpoint = supervisor.get("T4_sp", self.A.T_cond_C - 2)
            u_pump = self.pid_pump.step(pv["Tchip"], dt)
            u_V1 = self.pid_V1.step(pv["Pcond"], dt)
            u_V2 = self.pid_V2.step(pv["level"], dt)
            u_water = self.pid_water.step(pv["Tcond"], dt)
            u_pump = float(np.clip(supervisor.get("pump", u_pump), 0.15, 1.0))
            u_water = float(np.clip(supervisor.get("water", u_water), 0.2, 1.0))
            u_3w = float(np.clip(supervisor.get("3w", 0.0), 0.0, 1.0))
            u_chl = 0.0
            if self.state == State.NORMAL_CHILLER_ASSIST:
                u_chl = float(np.clip(supervisor.get("chiller", 0.5), 0.0, 1.0))
            if pv["Tchip"] > self.L.chip_warn:
                u_pump = 1.0
            if pv["level"] < self.L.level_low_warn:
                u_V2 = 1.0; u_pump = min(u_pump, 0.5)
            if pv["Pcond"] > self.L.p_high_warn:
                u_V1 = 1.0; u_water = 1.0
            tgt = {"pump": u_pump, "V1": u_V1, "V2": u_V2, "water": u_water,
                   "chiller": u_chl, "3w": u_3w}
        for k in self.cmd:
            r = self.ramp.get(k, 0.2)
            self.cmd[k] = float(np.clip(tgt[k], self.cmd[k] - r, self.cmd[k] + r))
        return dict(self.cmd)


class Supervisor:
    def __init__(self, A):
        self.A = A; self.mode = "free"
        self.last_switch_t = -1e9; self.min_dwell = 60.0

    def optimize(self, pv, t):
        A = self.A
        x = pv.get("x_out", 0.4)
        pump = 0.6 + 1.5 * (x - 0.4)
        if pv["Tchip"] > A.T_chip_target_C:
            pump += 0.03 * (pv["Tchip"] - A.T_chip_target_C)
        pump = float(np.clip(pump, 0.2, 1.0))
        water = 0.4 + 0.06 * (pv["Tcond"] - A.T_cond_C)
        water = float(np.clip(water, 0.2, 1.0))
        want = self.mode
        if pv["Tw_in"] > 33 or pv["Pcond"] > 20:
            want = "chiller"
        elif pv.get("reuse_demand", False) and pv["Tw_out"] >= 45:
            want = "reuse"
        else:
            want = "free"
        if want != self.mode and (t - self.last_switch_t) > self.min_dwell:
            self.mode = want; self.last_switch_t = t
        chiller = 0.5 if self.mode == "chiller" else 0.0
        three_w = 1.0 if self.mode == "reuse" else 0.0
        return {"pump": pump, "water": water, "chiller": chiller, "3w": three_w,
                "mode": self.mode, "level_sp": 60.0,
                "T4_sp": A.T_cond_C - 2, "Pcond_sp": A.T_cond_C / 4}
