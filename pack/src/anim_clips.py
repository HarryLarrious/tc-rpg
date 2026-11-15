#!/usr/bin/env python3
"""Animation clips: keyframed poses of the character rig, the one source of
every animation in the game.

A pose is a list of channels (CHANNELS below), in degrees, or model pixels
for bob and fwd. A clip is a set of keyframes over normalized time 0..1;
keys are interpolated with Catmull-Rom splines (wrapping for looping clips)
and sampled at SAMPLES evenly spaced points.

Writes:
  tc/anim_data.tc               the samples, and clipPose() to read them
  tools/viewer/anim_data.json   the same samples and keyframes for the viewer

Conventions (rig.tc applies them):
  root_p  whole body pitch about the hips, positive tips forward
  root_r  whole body roll, positive tips to its left
  bob     raise (px), fwd: shift forward (px)
  t_p     torso lean forward, t_y twist to its left, t_r tilt to its left
  h_p     head nods down, h_y turns left
  *_p     limb swings forward, *_o moves away from the body, *_y twists
  el_*    elbow bends (forearm comes forward/up), kn_*: knee bends back
  m_*/o_* held item pitch/yaw/roll relative to the hand
Right side is r, left side is l.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from character import BUILDS

BUILD = BUILDS["m"]

ROOT = Path(__file__).resolve().parents[2]

CHANNELS = [
    "root_p", "root_r", "bob", "fwd",
    "t_p", "t_y", "t_r", "h_p", "h_y",
    "ua_r_p", "ua_r_y", "ua_r_o", "el_r",
    "ua_l_p", "ua_l_y", "ua_l_o", "el_l",
    "th_r_p", "th_r_o", "kn_r", "th_l_p", "th_l_o", "kn_l",
    "m_p", "m_y", "m_r", "o_p", "o_y", "o_r",
]
IDX = {c: i for i, c in enumerate(CHANNELS)}
SAMPLES = 16
LOOP_SAMPLES = 24

REST = dict.fromkeys(CHANNELS, 0.0)
REST.update(ua_r_o=5, ua_l_o=5, el_r=12, el_l=12, kn_r=3, kn_l=3, m_p=-25, o_p=-20, th_r_o=2, th_l_o=2)

# Masks: which channels a clip drives. "upper" clips leave the legs (and
# the root) to the locomotion clip while the character moves.
UPPER = [c for c in CHANNELS if c.startswith(("t_", "h_", "ua_", "el_", "m_", "o_"))]


class Clip:
    def __init__(self, name: str, loop: bool = False, base: dict | None = None, hit: float = -1, mask: str = "full",
                 plant: bool = False):
        """plant: set bob each sample so the lowest point of the body
        touches the ground (a keyed positive bob lifts it off)."""
        self.name, self.loop, self.hit, self.mask, self.plant = name, loop, hit, mask, plant
        self.base = dict(REST)
        if base:
            self.base.update(base)
        self.keys: list[tuple[float, dict]] = []

    def k(self, t: float, **ch) -> "Clip":
        for c in ch:
            if c not in IDX:
                raise KeyError(f"{self.name}: unknown channel {c}")
        self.keys.append((t, ch))
        return self

    def poses(self) -> list[tuple[float, list[float]]]:
        """Keys as full poses: a channel a key leaves out keeps the clip's
        base value."""
        out = []
        for t, ch in sorted(self.keys, key=lambda k: k[0]):
            p = dict(self.base)
            p.update(ch)
            out.append((t, [p[c] for c in CHANNELS]))
        return out

    def sample(self, n: int) -> list[list[float]]:
        keys = self.poses()
        if self.loop:
            # Wrap: the key at t is also at t + 1 and t - 1.
            ext = [(t - 1, p) for t, p in keys] + keys + [(t + 1, p) for t, p in keys]
        else:
            ext = [(keys[0][0] - 1, keys[0][1])] + keys + [(keys[-1][0] + 1, keys[-1][1])]
        out = []
        for i in range(n):
            t = i / n if self.loop else i / (n - 1)
            out.append(catmull(ext, t))
        if self.plant:
            ib = IDX["bob"]
            for row in out:
                low = lowest(dict(zip(CHANNELS, row)))
                row[ib] = max(0.0, row[ib]) - low
        return out


def catmull(keys, t):
    """Catmull-Rom (centripetal-free, uniform in key index) through keys at
    time t."""
    j = 0
    while j + 1 < len(keys) and keys[j + 1][0] <= t:
        j += 1
    j = max(1, min(j, len(keys) - 3))
    t0, p0 = keys[j - 1]
    t1, p1 = keys[j]
    t2, p2 = keys[j + 1]
    t3, p3 = keys[j + 2]
    u = 0 if t2 == t1 else (t - t1) / (t2 - t1)
    u = max(0.0, min(1.0, u))
    out = []
    for a, b, c, d in zip(p0, p1, p2, p3):
        # Tangents scaled for uneven key spacing.
        m1 = (c - a) / max(1e-6, t2 - t0) * (t2 - t1)
        m2 = (d - b) / max(1e-6, t3 - t1) * (t2 - t1)
        u2, u3 = u * u, u * u * u
        out.append((2 * u3 - 3 * u2 + 1) * b + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * c + (u3 - u2) * m2)
    return out


# ---------------------------------------------------------------- ground
#
# The joints of the rig as tc/rig.tc places them (tools/viewer/rig.js has the
# same math), to find how far the body reaches below the hips.


def _rot(p, k, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    d = sum(k[i] * p[i] for i in range(3))
    x = (k[1] * p[2] - k[2] * p[1], k[2] * p[0] - k[0] * p[2], k[0] * p[1] - k[1] * p[0])
    return tuple(p[i] * c + x[i] * s + k[i] * d * (1 - c) for i in range(3))


def _basis(a, b, c, p, y, r):
    if y:
        c, a = _rot(c, b, y), _rot(a, b, y)
    if p:
        b, c = _rot(b, a, -p), _rot(c, a, -p)
    if r:
        b, a = _rot(b, c, r), _rot(a, c, r)
    return a, b, c


def _at(o, d, k):
    return tuple(o[i] + d[i] * k for i in range(3))


def lowest(P: dict) -> float:
    """Lowest surface point of the posed body in model pixels, with bob 0
    (build m): joint heights minus the thickness of the limb there."""
    b = BUILD
    L, U, F = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    hip = (0, b["hip"], 0)
    if P["root_p"]:
        U, F = _rot(U, L, P["root_p"]), _rot(F, L, P["root_p"])
    if P["root_r"]:
        U, L = _rot(U, F, -P["root_r"]), _rot(L, F, -P["root_r"])
    ta, tu, tf = _basis(L, U, F, -P["t_p"], P["t_y"], -P["t_r"])
    neck = _at(hip, tu, b["neck"] - b["hip"])
    ha, hu, hf = _basis(ta, tu, tf, -P["h_p"], P["h_y"], 0)
    pts = [(hip, 2.4), (_at(hip, tu, (b["neck"] - b["hip"]) / 2), b["td"] / 2 + 0.3), (neck, 2.2),
           (_at(neck, hu, 4.6), 4.2)]
    sh = _at(hip, tu, b["sy"] - b["hip"])
    for side, k in ((-1, "r"), (1, "l")):
        at = _at(sh, ta, side * b["sx"])
        ua = _basis(ta, tu, tf, P[f"ua_{k}_p"], P[f"ua_{k}_y"], side * P[f"ua_{k}_o"])
        el = _at(at, ua[1], -b["ua"])
        fa = _basis(*ua, P[f"el_{k}"], 0, 0)
        pts += [(at, 2.0), (el, 1.7), (_at(el, fa[1], -b["fa"]), 1.5)]
        hp = _at(hip, L, side * b["hx"])
        th = _basis(L, U, F, P[f"th_{k}_p"], 0, side * P[f"th_{k}_o"])
        kn = _at(hp, th[1], -b["th"])
        sn = _basis(*th, -P[f"kn_{k}"], 0, 0)
        sole = _at(kn, sn[1], -b["sh"])
        toe = _at(sole, sn[2], 2.0)
        pts += [(kn, 1.9), (sole, 0.0), (toe, 0.0)]
    return min(p[1] - r for p, r in pts)


# ---------------------------------------------------------------- clips

CLIPS: list[Clip] = []


def clip(*a, **kw) -> Clip:
    c = Clip(*a, **kw)
    CLIPS.append(c)
    return c


# Locomotion ------------------------------------------------------------

clip("idle", loop=True).k(
    0, bob=0, ua_r_o=5, ua_l_o=5, el_r=12, el_l=12, t_p=1, h_p=0).k(
    0.5, bob=0.25, ua_r_o=6.5, ua_l_o=6.5, el_r=16, el_l=16, t_p=0, h_p=-2)

# Walk: the right leg leads at 0. Contact, passing, contact, passing.
clip("walk", loop=True, base=dict(t_p=3), plant=True).k(
    0, th_r_p=26, kn_r=6, th_l_p=-20, kn_l=12, ua_r_p=-20, ua_l_p=22, el_r=14, el_l=22, t_y=-5, h_y=4).k(
    0.25, th_r_p=0, kn_r=8, th_l_p=6, kn_l=48, ua_r_p=0, ua_l_p=0, el_r=14, el_l=14, t_y=0, h_y=0).k(
    0.5, th_r_p=-20, kn_r=12, th_l_p=26, kn_l=6, ua_r_p=22, ua_l_p=-20, el_r=22, el_l=14, t_y=5, h_y=-4).k(
    0.75, th_r_p=6, kn_r=48, th_l_p=0, kn_l=8, ua_r_p=0, ua_l_p=0, el_r=14, el_l=14, t_y=0, h_y=0)

# Run: longer strides, high knees, pumping bent arms, leaning in.
clip("run", loop=True, base=dict(t_p=14, h_p=-10, el_r=85, el_l=85, ua_r_o=8, ua_l_o=8), plant=True).k(
    0, th_r_p=55, kn_r=30, th_l_p=-35, kn_l=40, ua_r_p=-40, ua_l_p=50, bob=0, t_y=-9).k(
    0.25, th_r_p=10, kn_r=20, th_l_p=20, kn_l=110, ua_r_p=0, ua_l_p=10, bob=1.0, t_y=0).k(
    0.5, th_r_p=-35, kn_r=40, th_l_p=55, kn_l=30, ua_r_p=50, ua_l_p=-40, bob=0, t_y=9).k(
    0.75, th_r_p=20, kn_r=110, th_l_p=10, kn_l=20, ua_r_p=10, ua_l_p=0, bob=1.0, t_y=0)

clip("air").k(
    0, th_r_p=40, kn_r=70, th_l_p=-15, kn_l=35, ua_r_p=-20, ua_l_p=15, ua_r_o=35, ua_l_o=35, el_r=35, el_l=40, t_p=6).k(
    1, th_r_p=40, kn_r=70, th_l_p=-15, kn_l=35, ua_r_p=-20, ua_l_p=15, ua_r_o=35, ua_l_o=35, el_r=35, el_l=40, t_p=6)

# Holding stances (upper body only, mixed over locomotion when idle).
clip("hold_1h", mask="upper").k(0, ua_r_p=14, el_r=40, m_p=-40).k(1, ua_r_p=14, el_r=40, m_p=-40)
clip("hold_2h", mask="upper").k(
    0, ua_r_p=20, ua_r_o=2, el_r=75, ua_l_p=30, ua_l_o=-8, el_l=80, t_y=10, m_p=-10, m_y=-20).k(
    1, ua_r_p=20, ua_r_o=2, el_r=75, ua_l_p=30, ua_l_o=-8, el_l=80, t_y=10, m_p=-10, m_y=-20)
clip("hold_staff", mask="upper").k(0, ua_r_p=12, ua_r_o=8, el_r=70, m_p=8).k(1, ua_r_p=12, ua_r_o=8, el_r=70, m_p=8)
clip("hold_bow", mask="upper").k(0, ua_l_p=20, el_l=40, o_p=-30, o_y=0).k(1, ua_l_p=20, el_l=40, o_p=-30)

# Moves ------------------------------------------------------------------

# Dodge roll: a forward roll in the direction of travel. The body tucks,
# pitches through a full turn and rises out of it.
clip("roll", base=dict(t_p=10), plant=True).k(
    0, root_p=0, th_r_p=10, th_l_p=10, kn_r=10, kn_l=10, ua_r_p=20, ua_l_p=20).k(
    0.15, root_p=40, t_p=40, th_r_p=80, th_l_p=70, kn_r=100, kn_l=110, ua_r_p=70, ua_l_p=70, el_r=80, el_l=80, h_p=45).k(
    0.5, root_p=190, t_p=50, th_r_p=115, th_l_p=115, kn_r=140, kn_l=140, ua_r_p=90, ua_l_p=90, el_r=110, el_l=110, h_p=50).k(
    0.8, root_p=320, t_p=35, th_r_p=90, th_l_p=60, kn_r=115, kn_l=85, ua_r_p=40, ua_l_p=40, el_r=60, el_l=60, h_p=20).k(
    1, root_p=360, t_p=8, th_r_p=15, th_l_p=-5, kn_r=20, kn_l=10, ua_r_p=10, ua_l_p=10, el_r=20, el_l=20, h_p=0)

clip("hurt", plant=True).k(0, t_p=0).k(
    0.25, t_p=-16, h_p=-18, ua_r_p=-15, ua_l_p=-15, ua_r_o=25, ua_l_o=25, el_r=40, el_l=40, bob=-0.5).k(
    1, t_p=0)

# Death: knees give, then the body falls back and lies still.
clip("death", plant=True).k(0, root_p=0).k(
    0.2, root_p=-5, kn_r=60, kn_l=50, th_r_p=30, th_l_p=25, t_p=20, h_p=20, ua_r_p=10, ua_l_p=10).k(
    0.45, root_p=-60, kn_r=40, kn_l=30, th_r_p=20, th_l_p=10, t_p=5, h_p=-10, ua_r_p=0, ua_l_p=5, ua_r_o=30, ua_l_o=25).k(
    0.6, root_p=-90, kn_r=10, kn_l=25, th_r_p=5, th_l_p=12, t_p=0, h_p=5, ua_r_p=5, ua_l_p=8, ua_r_o=55, ua_l_o=40, el_r=20, el_l=15, th_r_o=8, th_l_o=6).k(
    1, root_p=-90, kn_r=10, kn_l=25, th_r_p=5, th_l_p=12, t_p=0, h_p=5, h_y=25, ua_r_p=5, ua_l_p=8, ua_r_o=55, ua_l_o=40, el_r=20, el_l=15, th_r_o=8, th_l_o=6)

# Casting: both hands gather in front, then thrust out at the release.
clip("cast", hit=0.5, mask="upper").k(0).k(
    0.3, ua_r_p=60, ua_l_p=60, ua_r_o=-5, ua_l_o=-5, el_r=95, el_l=95, t_p=-5, h_p=-5, m_p=-90).k(
    0.5, ua_r_p=95, ua_l_p=95, ua_r_o=8, ua_l_o=8, el_r=10, el_l=10, t_p=8, m_p=-90).k(
    0.75, ua_r_p=80, ua_l_p=70, ua_r_o=10, ua_l_o=10, el_r=25, el_l=30, t_p=4, m_p=-80).k(1)

# Bow: draw (hold the end) and release.
clip("draw", mask="upper", base=dict(t_y=-35, h_y=35)).k(
    0, ua_l_p=60, el_l=30, ua_r_p=40, el_r=60, o_p=-30).k(
    0.5, ua_l_p=90, ua_l_o=-5, el_l=0, ua_r_p=85, ua_r_y=-20, el_r=150, o_p=-90, o_r=0).k(
    1, ua_l_p=90, ua_l_o=-5, el_l=0, ua_r_p=88, ua_r_y=-30, ua_r_o=10, el_r=160, o_p=-90)
clip("shoot", hit=0.15, mask="upper", base=dict(t_y=-35, h_y=35)).k(
    0, ua_l_p=90, ua_l_o=-5, el_l=0, ua_r_p=85, el_r=150, o_p=-90).k(
    0.2, ua_l_p=92, el_l=0, ua_r_p=70, ua_r_o=40, el_r=40, o_p=-90).k(
    1, ua_l_p=40, el_l=30, ua_r_p=15, el_r=20, o_p=-40)

# NPC gestures.
clip("wave", loop=True, mask="upper").k(0, ua_l_p=20, ua_l_o=70, el_l=100, ua_l_y=-30).k(
    0.5, ua_l_p=20, ua_l_o=95, el_l=70, ua_l_y=-30)
clip("talk", loop=True, mask="upper").k(0, ua_r_p=30, el_r=60, ua_r_o=10).k(
    0.33, ua_r_p=40, el_r=80, ua_r_o=20, h_p=-3).k(0.66, ua_r_p=25, el_r=50, ua_r_o=8, ua_l_p=20, el_l=40, h_p=2)


def attack(name: str, windup: dict, strike: dict, follow: dict | None = None, hit: float = 0.45,
           legs: dict | None = None):
    """An attack: anticipation, wind up, a fast strike through the hit
    point, follow through and recovery to the stance. legs: stance of the
    legs during the swing."""
    st = dict(legs or dict(th_r_p=-12, kn_r=15, th_l_p=22, kn_l=25, th_r_o=6, th_l_o=6))
    c = clip(name, hit=hit, mask="full", plant=True)
    c.k(0)
    w = dict(windup)
    w.update(st)
    c.k(0.3, **w)
    s = dict(strike)
    s.update(st)
    c.k(hit + 0.1, **s)
    if follow:
        f = dict(follow)
        f.update(st)
        c.k(min(0.8, hit + 0.25), **f)
    c.k(1)
    return c


# One-handed blades and blunt weapons: a cut from the right, a backhand
# from the left, and an overhead blow; the heavy is a spinning cleave.
attack("atk_blade_1",
       dict(ua_r_p=70, ua_r_o=75, ua_r_y=10, el_r=90, t_y=-40, t_p=4, m_p=-70, m_r=-20),
       dict(ua_r_p=80, ua_r_o=-25, el_r=15, t_y=35, t_p=8, m_p=-75, m_r=-10),
       dict(ua_r_p=60, ua_r_o=-40, el_r=25, t_y=40, m_p=-60))
attack("atk_blade_2",
       dict(ua_r_p=75, ua_r_o=-40, el_r=95, t_y=40, t_p=4, m_p=-80, m_r=170),
       dict(ua_r_p=85, ua_r_o=70, el_r=10, t_y=-38, t_p=8, m_p=-85, m_r=170),
       dict(ua_r_p=70, ua_r_o=85, el_r=25, t_y=-42, m_p=-70, m_r=170))
attack("atk_blade_3",
       dict(ua_r_p=165, ua_r_o=15, el_r=70, t_p=-12, h_p=-8, m_p=-20),
       dict(ua_r_p=45, ua_r_o=5, el_r=10, t_p=22, h_p=10, m_p=-55, fwd=2),
       dict(ua_r_p=20, el_r=20, t_p=18, m_p=-40, fwd=2), hit=0.5,
       legs=dict(th_r_p=-20, kn_r=20, th_l_p=35, kn_l=45))
attack("atk_blade_4",
       dict(ua_r_p=90, ua_r_o=80, el_r=60, t_y=-80, t_p=5, m_p=-80),
       dict(ua_r_p=80, ua_r_o=-30, el_r=5, t_y=80, t_p=12, m_p=-80, fwd=1),
       dict(ua_r_p=70, ua_r_o=-50, el_r=15, t_y=110, m_p=-70), hit=0.5,
       legs=dict(th_r_p=-25, kn_r=25, th_l_p=30, kn_l=45, th_r_o=10, th_l_o=10))

# Two-handed heavies: both hands on the hilt, big body turns.
TWO = dict(ua_l_o=-20)
attack("atk_heavy_1",
       dict(ua_r_p=80, ua_r_o=60, el_r=80, ua_l_p=70, ua_l_o=10, el_l=100, t_y=-55, t_p=5, m_p=-80, m_y=-10),
       dict(ua_r_p=75, ua_r_o=-15, el_r=20, ua_l_p=80, ua_l_o=-35, el_l=40, t_y=50, t_p=12, m_p=-80, fwd=1.5),
       dict(ua_r_p=60, ua_r_o=-25, el_r=35, ua_l_p=60, ua_l_o=-40, el_l=50, t_y=60, m_p=-70))
attack("atk_heavy_2",
       dict(ua_r_p=70, ua_r_o=-20, el_r=90, ua_l_p=75, ua_l_o=-40, el_l=80, t_y=55, t_p=5, m_p=-80, m_r=170),
       dict(ua_r_p=80, ua_r_o=55, el_r=20, ua_l_p=70, ua_l_o=15, el_l=40, t_y=-50, t_p=12, m_p=-80, m_r=170, fwd=1.5),
       dict(ua_r_p=65, ua_r_o=65, el_r=35, ua_l_p=55, ua_l_o=20, el_l=55, t_y=-60, m_p=-70, m_r=170))
attack("atk_heavy_3",
       dict(ua_r_p=170, ua_r_o=10, el_r=60, ua_l_p=170, ua_l_o=-10, el_l=60, t_p=-15, h_p=-10, m_p=-10),
       dict(ua_r_p=40, ua_r_o=5, el_r=5, ua_l_p=40, ua_l_o=-10, el_l=5, t_p=30, h_p=15, m_p=-45, fwd=3, bob=-1.5),
       dict(ua_r_p=25, el_r=10, ua_l_p=25, el_l=10, t_p=28, m_p=-30, fwd=3, bob=-1.5), hit=0.5,
       legs=dict(th_r_p=-25, kn_r=30, th_l_p=40, kn_l=60))
attack("atk_heavy_4",
       dict(ua_r_p=85, ua_r_o=70, el_r=50, ua_l_p=80, ua_l_o=0, el_l=70, t_y=-90, t_p=8, m_p=-85),
       dict(ua_r_p=80, ua_r_o=-20, el_r=10, ua_l_p=80, ua_l_o=-30, el_l=30, t_y=90, t_p=12, m_p=-85, fwd=1),
       dict(ua_r_p=70, ua_r_o=-30, el_r=20, ua_l_p=60, ua_l_o=-40, el_l=40, t_y=130, m_p=-80), hit=0.5,
       legs=dict(th_r_p=-25, kn_r=35, th_l_p=30, kn_l=45, th_r_o=12, th_l_o=12))

# Daggers and fists: quick jabs and slashes, a lunging stab.
attack("atk_dagger_1",
       dict(ua_r_p=20, ua_r_o=20, el_r=110, t_y=-20, m_p=20),
       dict(ua_r_p=88, ua_r_o=0, el_r=5, t_y=20, t_p=8, m_p=-90, fwd=1.5),
       hit=0.4)
attack("atk_dagger_2",
       dict(ua_r_p=80, ua_r_o=70, el_r=80, t_y=-30, m_p=-80),
       dict(ua_r_p=75, ua_r_o=-35, el_r=15, t_y=35, m_p=-80),
       hit=0.4)
attack("atk_dagger_3",
       dict(ua_r_p=150, ua_r_o=20, el_r=80, t_p=-8, m_p=60),
       dict(ua_r_p=70, ua_r_o=0, el_r=10, t_p=15, m_p=-95, fwd=2),
       hit=0.45)
attack("atk_dagger_4",
       dict(ua_r_p=10, ua_r_o=15, el_r=120, t_y=-30, t_p=-5, m_p=30),
       dict(ua_r_p=90, el_r=0, t_y=25, t_p=15, m_p=-95, fwd=4, bob=-1),
       hit=0.45, legs=dict(th_r_p=-35, kn_r=25, th_l_p=50, kn_l=70))
attack("atk_fist_1",
       dict(ua_r_p=30, ua_r_o=10, el_r=120, t_y=-15),
       dict(ua_r_p=88, ua_r_o=0, el_r=0, t_y=25, t_p=6, fwd=1), hit=0.4)
attack("atk_fist_2",
       dict(ua_l_p=30, ua_l_o=10, el_l=120, t_y=15),
       dict(ua_l_p=88, ua_l_o=0, el_l=0, t_y=-25, t_p=6, fwd=1), hit=0.4)
attack("atk_fist_3",
       dict(ua_r_p=-10, ua_r_o=20, el_r=130, t_p=-8, bob=-1.5),
       dict(ua_r_p=150, ua_r_o=5, el_r=40, t_p=-10, bob=1, h_p=-15), hit=0.45)
attack("atk_fist_4",
       dict(ua_r_p=10, el_r=120, ua_l_p=10, el_l=120, t_p=-5, bob=-1),
       dict(ua_r_p=90, el_r=0, ua_l_p=90, el_l=0, t_p=12, fwd=4), hit=0.45,
       legs=dict(th_r_p=-35, kn_r=25, th_l_p=50, kn_l=70))

# Spears and polearms: thrusts from a two-handed guard, a sweep, a lunge.
SPEAR_GUARD = dict(ua_r_p=30, el_r=70, ua_l_p=60, ua_l_o=-15, el_l=40, m_p=-100, t_y=-20)
attack("atk_spear_1",
       dict(SPEAR_GUARD, ua_r_p=20, el_r=100, t_y=-30),
       dict(SPEAR_GUARD, ua_r_p=75, el_r=10, ua_l_p=85, el_l=10, t_y=10, t_p=10, fwd=2.5), hit=0.42)
attack("atk_spear_2",
       dict(SPEAR_GUARD, ua_r_p=25, el_r=95, t_y=-35),
       dict(SPEAR_GUARD, ua_r_p=80, el_r=5, ua_l_p=85, el_l=5, t_y=15, t_p=12, fwd=3), hit=0.42)
attack("atk_spear_3",
       dict(ua_r_p=80, ua_r_o=60, el_r=60, ua_l_p=70, ua_l_o=20, el_l=60, t_y=-60, m_p=-90),
       dict(ua_r_p=80, ua_r_o=-20, el_r=15, ua_l_p=80, ua_l_o=-30, el_l=20, t_y=60, m_p=-90), hit=0.5)
attack("atk_spear_4",
       dict(SPEAR_GUARD, ua_r_p=10, el_r=120, t_y=-40, t_p=-5),
       dict(SPEAR_GUARD, ua_r_p=88, el_r=0, ua_l_p=88, el_l=0, t_y=20, t_p=18, fwd=6, bob=-1.5), hit=0.45,
       legs=dict(th_r_p=-40, kn_r=20, th_l_p=55, kn_l=75))

# Staves and wands: a two-handed sweep and an overhead smash.
attack("atk_staff_1",
       dict(ua_r_p=70, ua_r_o=70, el_r=80, ua_l_p=40, el_l=80, t_y=-40, m_p=-80),
       dict(ua_r_p=80, ua_r_o=-20, el_r=20, ua_l_p=60, ua_l_o=-20, el_l=40, t_y=40, m_p=-80))
attack("atk_staff_4",
       dict(ua_r_p=170, el_r=50, ua_l_p=160, el_l=50, t_p=-12, m_p=-10),
       dict(ua_r_p=50, el_r=5, ua_l_p=50, el_l=5, t_p=25, m_p=-50, fwd=2), hit=0.5,
       legs=dict(th_r_p=-25, kn_r=30, th_l_p=40, kn_l=55))

# Weapon arts.
attack("art_spin",
       dict(ua_r_p=85, ua_r_o=75, el_r=30, ua_l_p=40, ua_l_o=60, el_l=30, t_y=-60, m_p=-85),
       dict(ua_r_p=85, ua_r_o=70, el_r=10, ua_l_p=40, ua_l_o=60, el_l=30, t_y=60, m_p=-85, root_r=0), hit=0.5)
attack("art_slam",
       dict(ua_r_p=175, el_r=40, ua_l_p=175, el_l=40, t_p=-20, bob=3, m_p=-10),
       dict(ua_r_p=30, el_r=0, ua_l_p=30, el_l=0, t_p=35, bob=-3, m_p=-40, fwd=2), hit=0.55,
       legs=dict(th_r_p=50, kn_r=100, th_l_p=50, kn_l=100))
attack("art_roar",
       dict(ua_r_p=10, ua_r_o=60, el_r=90, ua_l_p=10, ua_l_o=60, el_l=90, t_p=10, h_p=10),
       dict(ua_r_p=20, ua_r_o=80, el_r=60, ua_l_p=20, ua_l_o=80, el_l=60, t_p=-15, h_p=-25), hit=0.4)


# ---------------------------------------------------------------- output


def fmt(x: float) -> str:
    s = f"{x:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def main() -> None:
    names = [c.name for c in CLIPS]
    if len(set(names)) != len(names):
        raise SystemExit("duplicate clip names")
    data = {}
    lines = [
        "// Generated by pack/src/anim_clips.py: do not edit.",
        "// Animation clips sampled evenly over normalized time.",
        "",
        "/** Per clip: the samples, flattened (samples x channels), as text:",
        " * one string per clip keeps the plot's code data small. animSamples()",
        " * parses a clip into animData on first use. */",
        "declare global animStr: dict[str];",
        "declare global animData: dict[list];",
        "/** Per clip: [samples, loop 0/1, hit time (-1 none), upper-only 0/1]. */",
        "declare global animMeta: dict[list];",
        "",
        "/** Channels in a pose. */",
        "function poseLen(): num {",
        f"    return {len(CHANNELS)};",
        "}",
        "",
        "/** The rest pose. */",
        "function poseZero(): list[num] {",
        f"    return [{', '.join(fmt(REST[c]) for c in CHANNELS)}];",
        "}",
        "",
        "function loadAnimData {",
        "    global animStr = {};",
        "    global animData = {};",
        "    global animMeta = {};",
    ]
    for c in CLIPS:
        n = LOOP_SAMPLES if c.loop else SAMPLES
        smp = c.sample(n)
        flat = [fmt(v) for row in smp for v in row]
        lines.append(f"    global animStr[\"{c.name}\"] = \"{','.join(flat)}\";")
        lines.append(f"    global animMeta[\"{c.name}\"] = [{n}, {int(c.loop)}, {fmt(c.hit)}, {int(c.mask == 'upper')}];")
        data[c.name] = {"loop": c.loop, "hit": c.hit, "mask": c.mask, "samples": [[round(v, 2) for v in r] for r in smp],
                        "keys": [[t, [round(v, 2) for v in p]] for t, p in c.poses()]}
    lines += ["}", "", "/** Index of channel name in a pose (generated). */"]
    lines += ["function chan(name: str): num {",
              "    line c = {" + ", ".join(f"{c}: {i + 1}" for i, c in enumerate(CHANNELS)) + "};",
              "    return line c[name] as num;", "}", ""]
    (ROOT / "tc/anim_data.tc").write_text("\n".join(lines) + "\n")
    out = ROOT / "tools/viewer/anim_data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"channels": CHANNELS, "rest": [REST[c] for c in CHANNELS], "clips": data}))
    print(f"anim: {len(CLIPS)} clips, {len(CHANNELS)} channels")


if __name__ == "__main__":
    main()
