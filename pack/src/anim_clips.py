#!/usr/bin/env python3
"""Animation clips: keyframed poses of the character rig, the one source of
every animation in the game.

The style is cartoony and bouncy: straight one-piece limbs that swing wide,
the whole body squashing on impacts and stretching on the way up, moves that
wind up, snap through and overshoot before they settle.

A pose is a list of channels (CHANNELS below), in degrees, model pixels for
bob and fwd, and percent for sq. A clip is a set of keyframes over
normalized time 0..1; keys are interpolated with Catmull-Rom splines
(wrapping for looping clips) and sampled at SAMPLES evenly spaced points.

Writes:
  tc/anim_data.tc               the samples, and chan() to name channels
  tools/viewer/anim_data.json   the same samples and keyframes for the viewer

Conventions (rig.tc applies them):
  root_p  whole body pitch about the hips, positive tips forward
  root_y  whole body turn, positive turns to its left
  root_r  whole body roll, positive tips to its left
  bob     raise (px), fwd: shift forward (px)
  sq      squash and stretch (percent): positive is taller and thinner,
          negative shorter and wider (volume kept), about the feet
  t_p     torso lean forward, t_y twist to its left, t_r tilt to its left
  h_p     head nods down, h_y turns left, h_r tilts to its left
  a_*_p   arm swings forward (90 points straight ahead, 180 straight up)
  a_*_y   turns the arm's swing toward the body's left (with a_p 90 it
          sweeps the arm level, from its right to its left)
  a_*_o   arm moves out, away from the body
  l_*_p   leg swings forward, l_*_o moves out
  m_*/o_* held item pitch/yaw/roll relative to the hand (m_p negative
          tips the item forward, down the arm's line)
Right side is r, left side is l.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from character import BUILDS

BUILD = BUILDS["m"]

ROOT = Path(__file__).resolve().parents[2]

CHANNELS = [
    "root_p", "root_y", "root_r", "bob", "fwd", "sq",
    "t_p", "t_y", "t_r", "h_p", "h_y", "h_r",
    "a_r_p", "a_r_y", "a_r_o", "a_l_p", "a_l_y", "a_l_o",
    "l_r_p", "l_r_o", "l_l_p", "l_l_o",
    "m_p", "m_y", "m_r", "o_p", "o_y", "o_r",
]
IDX = {c: i for i, c in enumerate(CHANNELS)}
SAMPLES = 16
LOOP_SAMPLES = 24
# Most clip text per generated function (characters).
CHUNK = 7000

REST = dict.fromkeys(CHANNELS, 0.0)
REST.update(a_r_o=3, a_l_o=3, m_p=30, o_p=30)

# Masks: which channels a clip drives. "upper" clips leave the legs, the
# root and the squash to the locomotion clip while the character moves.
UPPER = [c for c in CHANNELS if c.startswith(("t_", "h_", "a_", "m_", "o_"))]


class Clip:
    def __init__(self, name: str, loop: bool = False, base: dict | None = None, hit: float = -1, mask: str = "full",
                 plant: bool = False):
        """plant: set bob each sample so the lowest point of the body
        touches the ground (a keyed positive bob lifts it off: a hop)."""
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
    """Catmull-Rom (uniform in key index) through keys at time t."""
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
    (build m): points of the body minus the body's half thickness there."""
    b = BUILD
    L, U, F = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    hip = (0, b["hip"], 0)
    if P["root_y"]:
        L, F = _rot(L, U, P["root_y"]), _rot(F, U, P["root_y"])
    if P["root_p"]:
        U, F = _rot(U, L, P["root_p"]), _rot(F, L, P["root_p"])
    if P["root_r"]:
        U, L = _rot(U, F, -P["root_r"]), _rot(L, F, -P["root_r"])
    ta, tu, tf = _basis(L, U, F, -P["t_p"], P["t_y"], -P["t_r"])
    H = b["neck"] - b["hip"]
    neck = _at(hip, tu, H)
    hu = _basis(ta, tu, tf, -P["h_p"], P["h_y"], -P["h_r"])[1]
    pts = [(hip, 2.4), (_at(hip, tu, H / 2), b["td"] / 2 + 0.2), (neck, 2.4), (_at(neck, hu, 4.25), 4.6)]
    sh = _at(hip, tu, b["sy"] - b["hip"])
    for side, k in ((-1, "r"), (1, "l")):
        at = _at(sh, ta, side * b["sx"])
        ab = _basis(ta, tu, tf, P[f"a_{k}_p"], P[f"a_{k}_y"], side * P[f"a_{k}_o"])[1]
        pts += [(at, 2.2), (_at(at, ab, -b["grip"]), 2.2), (_at(at, ab, 2 - b["al"]), 1.6)]
        hp = _at(hip, L, side * b["hx"])
        la, lb, lc = _basis(L, U, F, P[f"l_{k}_p"], 0, side * P[f"l_{k}_o"])
        sole = _at(hp, lb, -b["ll"])
        pts += [(_at(hp, lb, -b["ll"] / 2), 2.0), (sole, 0.0), (_at(sole, lc, 2.6), 0.0), (_at(sole, lc, -2.2), 0.0)]
    return min(p[1] - r for p, r in pts)


# ---------------------------------------------------------------- clips

CLIPS: list[Clip] = []


def clip(*a, **kw) -> Clip:
    c = Clip(*a, **kw)
    CLIPS.append(c)
    return c


def toward(d: dict, k: float, base: dict | None = None) -> dict:
    """The pose d pulled toward base (REST by default) by 1 - k: k 0.4 is
    40% of the way from base to d."""
    base = base or REST
    return {c: base[c] + (v - base[c]) * k for c, v in d.items()}


def past(a: dict, b: dict, k: float) -> dict:
    """Overshoot: b pushed further along the line from a by k."""
    return {c: b[c] + (b[c] - a.get(c, REST[c])) * k for c in b}


# Locomotion ------------------------------------------------------------

# Idle: breathing that squashes and stretches, a slow sway, the head
# tilting against it.
clip("idle", loop=True).k(
    0, sq=-1.5, a_r_o=3, a_l_o=3, t_r=0, h_r=0, h_p=1).k(
    0.25, sq=2.5, a_r_o=6, a_l_o=6, t_r=1.5, h_r=-3, h_p=-1).k(
    0.5, sq=-1.5, a_r_o=3, a_l_o=3, t_r=0, h_r=0, h_p=1).k(
    0.75, sq=2.5, a_r_o=6, a_l_o=6, t_r=-1.5, h_r=3, h_p=-1)

# Walk: the right foot lands at 0. Straight legs and arms swing wide, the
# body squashes on each step and hops up through the passing pose.
WALK_HIT = dict(l_r_p=32, l_l_p=-30, a_r_p=-38, a_l_p=38, sq=-5, t_y=-7, t_r=0, h_p=4, h_r=0)
WALK_UP = dict(l_r_p=-2, l_l_p=4, a_r_p=-4, a_l_p=4, bob=1.3, sq=4, t_y=0, t_r=-3, h_p=-2, h_r=3)


def mirror(p: dict) -> dict:
    """The pose with right and left swapped (and side to side turns
    flipped)."""
    out = {}
    for c, v in p.items():
        if "_r_" in c:
            out[c.replace("_r_", "_l_")] = v
        elif "_l_" in c:
            out[c.replace("_l_", "_r_")] = v
        elif c in ("t_y", "t_r", "h_y", "h_r", "root_y", "root_r"):
            out[c] = -v
        else:
            out[c] = v
    return out


clip("walk", loop=True, base=dict(t_p=4), plant=True).k(
    0, **WALK_HIT).k(0.25, **WALK_UP).k(0.5, **mirror(WALK_HIT)).k(0.75, **mirror(WALK_UP))

# Run: leaning in, big strides and arm pumps, airborne between steps.
RUN_HIT = dict(l_r_p=55, l_l_p=-48, a_r_p=-62, a_l_p=68, a_r_o=10, a_l_o=10, sq=-8, bob=0, t_y=-11, t_r=0, h_p=-4,
               h_r=0)
RUN_UP = dict(l_r_p=-8, l_l_p=18, a_r_p=-10, a_l_p=16, a_r_o=12, a_l_o=12, sq=7, bob=2.6, t_y=0, t_r=-4, h_p=-10,
              h_r=4)
clip("run", loop=True, base=dict(t_p=14), plant=True).k(
    0, **RUN_HIT).k(0.25, **RUN_UP).k(0.5, **mirror(RUN_HIT)).k(0.75, **mirror(RUN_UP))

# In the air: arms thrown up, legs kicking, stretched tall (played as a
# loop so the arms and legs flail).
AIR = dict(a_r_p=165, a_l_p=150, a_r_o=14, a_l_o=22, l_r_p=26, l_l_p=-14, l_r_o=4, l_l_o=4, sq=6, h_p=-6, t_p=-4,
           m_p=60, o_p=60)
clip("air", loop=True).k(0, **AIR).k(0.5, **mirror(AIR))

# Landing (added over locomotion): squash flat, arms fling out, spring back.
clip("land").k(0).k(
    0.18, sq=-16, a_r_o=38, a_l_o=38, l_r_o=8, l_l_o=8, h_p=10, t_p=8).k(
    0.45, sq=8, a_r_o=8, a_l_o=8, h_p=-5, t_p=-3).k(
    0.72, sq=-3, a_r_o=5, a_l_o=5, h_p=2).k(1)

# Holding stances (upper body only, added over locomotion).
clip("hold_1h", mask="upper").k(0, a_r_p=28, a_r_o=6, m_p=10).k(1, a_r_p=28, a_r_o=6, m_p=10)
clip("hold_2h", mask="upper").k(
    0, a_r_p=42, a_r_y=28, a_r_o=0, t_y=12, h_y=-8, m_p=-5, m_y=0).k(
    1, a_r_p=42, a_r_y=28, a_r_o=0, t_y=12, h_y=-8, m_p=-5, m_y=0)
clip("hold_staff", mask="upper").k(0, a_r_p=22, a_r_o=10, m_p=35).k(1, a_r_p=22, a_r_o=10, m_p=35)
clip("hold_bow", mask="upper").k(0, a_l_p=26, a_l_o=6, o_p=60).k(1, a_l_p=26, a_l_o=6, o_p=60)

# Moves ------------------------------------------------------------------

# Dodge roll: squash down, dive forward stretched, tuck into a ball and
# roll over, land in a squash and pop up with the arms flung out.
clip("roll", plant=True).k(0).k(
    0.1, sq=-12, t_p=18, h_p=12, a_r_p=-30, a_l_p=-30, l_r_p=10, l_l_p=10).k(
    0.24, root_p=60, sq=10, bob=2, t_p=10, a_r_p=170, a_l_p=170, a_r_o=8, a_l_o=8, l_r_p=-25, l_l_p=-15).k(
    0.42, root_p=190, sq=-8, t_p=45, h_p=40, a_r_p=110, a_l_p=110, a_r_o=-4, a_l_o=-4, l_r_p=95, l_l_p=95).k(
    0.62, root_p=310, sq=-4, t_p=30, h_p=20, a_r_p=70, a_l_p=70, l_r_p=60, l_l_p=40).k(
    0.76, root_p=360, sq=-15, t_p=10, h_p=8, a_r_p=10, a_l_p=10, a_r_o=40, a_l_o=40, l_r_p=10, l_l_p=-6,
    l_r_o=6, l_l_o=6).k(
    0.88, root_p=360, sq=9, bob=0.6, t_p=-4, h_p=-6, h_r=6, a_r_o=55, a_l_o=55).k(
    1, root_p=360)

# Hurt: knocked back in a squash, wobbles back upright.
clip("hurt", plant=True).k(0).k(
    0.18, t_p=-20, h_p=-24, h_r=-8, sq=-12, a_r_p=-25, a_l_p=-20, a_r_o=30, a_l_o=34, fwd=-1.5).k(
    0.42, t_p=6, h_p=8, h_r=6, sq=6, a_r_o=10, a_l_o=12).k(
    0.68, t_p=-3, h_p=-3, h_r=-3, sq=-2).k(1)

# Death: a squash, a stretched hop with the arms up, a flop onto the back,
# one bounce and stillness.
DEAD = dict(root_p=-90, root_y=30, a_r_p=8, a_l_p=12, a_r_o=70, a_l_o=60, l_r_o=12, l_l_o=9, l_r_p=6, l_l_p=-4,
            h_y=25, h_p=6)
clip("death", plant=True).k(0).k(
    0.14, sq=-12, h_p=20, a_r_o=20, a_l_o=20, t_p=10).k(
    0.3, bob=4, sq=12, root_p=-20, root_y=15, a_r_p=165, a_l_p=155, a_r_o=10, a_l_o=14, h_p=-20, l_r_p=20).k(
    0.52, **dict(DEAD, sq=-14)).k(
    0.64, **dict(DEAD, root_p=-82, bob=1.6, sq=7, a_r_o=55, a_l_o=48)).k(
    0.78, **dict(DEAD, sq=-4)).k(
    1, **DEAD)

# Casting: arms swing wide to gather, then thrust forward, overshoot and
# spring back.
CAST = dict(a_r_p=98, a_l_p=98, a_r_o=-6, a_l_o=-6, t_p=10, h_p=-4, m_p=-60)
clip("cast", hit=0.5, mask="upper").k(0).k(
    0.25, a_r_p=40, a_l_p=40, a_r_o=55, a_l_o=55, t_p=-8, h_p=-10, m_p=40).k(
    0.42, a_r_p=70, a_l_p=70, a_r_o=30, a_l_o=30, t_p=-2).k(
    0.52, **CAST).k(
    0.62, **past(dict(a_r_p=70, a_l_p=70, t_p=-2), CAST, 0.25)).k(
    0.78, **toward(CAST, 0.85)).k(1)

# Bow: draw (hold the end) and release. The body turns side on, the bow
# arm points at the target, the string hand pulls back.
DRAWN = dict(t_y=-38, h_y=36, a_l_p=90, a_l_y=36, a_l_o=0, a_r_p=88, a_r_y=58, a_r_o=0, o_p=0, m_p=0)
clip("draw", mask="upper").k(
    0, t_y=-20, h_y=18, a_l_p=60, a_l_y=20, a_r_p=40, a_r_y=30, o_p=20).k(
    0.55, **dict(DRAWN, a_l_p=96, t_y=-42)).k(
    0.8, **dict(DRAWN, a_l_p=88)).k(
    1, **DRAWN)
clip("shoot", hit=0.15, mask="upper").k(
    0, **DRAWN).k(
    0.15, **dict(DRAWN, a_r_p=95, a_r_y=-10, a_r_o=45, a_l_p=100)).k(
    0.35, **dict(DRAWN, a_r_p=70, a_r_y=-20, a_r_o=35, a_l_p=84)).k(
    0.6, t_y=-15, h_y=12, a_l_p=50, a_l_y=10, a_r_p=20, a_r_o=10, o_p=40).k(
    1)

# NPC gestures.
clip("wave", loop=True, mask="upper").k(
    0, a_l_p=150, a_l_o=22, a_l_y=10, h_r=5, t_r=2, o_p=60).k(
    0.5, a_l_p=155, a_l_o=52, a_l_y=10, h_r=-2, t_r=-1, o_p=60)
clip("talk", loop=True, mask="upper").k(
    0, a_r_p=38, a_r_o=14, a_l_p=8, h_p=0, h_r=2).k(
    0.33, a_r_p=55, a_r_o=26, a_l_p=12, a_l_o=10, h_p=-4, h_r=-3).k(
    0.66, a_r_p=30, a_r_o=10, a_l_p=34, a_l_o=18, h_p=3, h_r=4)


def attack(name: str, windup: dict, strike: dict, follow: dict | None = None, hit: float = 0.45,
           legs: dict | None = None):
    """An attack in five beats: a squashed anticipation, the wind up held
    stretched, a snap through the hit point, an overshoot past it and a
    springy settle back to the stance. legs: the stance of the legs."""
    st = dict(legs or dict(l_r_p=-14, l_l_p=20, l_r_o=5, l_l_o=5))
    follow = follow or past(windup, strike, 0.18)
    c = clip(name, hit=hit, plant=True)
    c.k(0)
    c.k(0.12, **toward(windup, 0.45), **toward(st, 0.5), sq=-7)
    c.k(hit - 0.08, **windup, **st, sq=5)
    c.k(hit + 0.05, **strike, **st, sq=-7)
    c.k(min(0.8, hit + 0.2), **follow, **st, sq=4)
    settle = dict(toward(follow, 0.45), **toward(st, 0.5), sq=-2)
    end = {}
    if abs(follow.get("root_y", 0)) > 180:
        # A full spin ends a turn round, not unwound back to 0.
        settle["root_y"] = end["root_y"] = math.copysign(360, follow["root_y"])
    c.k(min(0.9, hit + 0.36), **settle)
    c.k(1, **end)
    return c


# One-handed blades and blunt weapons. Level sweeps swing the straight arm
# with a_*_y; m_p -90 lays the blade along the arm.
attack("atk_blade_1",
       dict(a_r_p=88, a_r_y=-75, a_r_o=4, t_y=-35, t_p=2, m_p=-95, m_r=-10),
       dict(a_r_p=88, a_r_y=45, a_r_o=0, t_y=30, t_p=8, m_p=-90, m_r=-10, fwd=1.5),
       dict(a_r_p=82, a_r_y=70, t_y=42, t_p=6, m_p=-85, m_r=-10, fwd=1.5))
attack("atk_blade_2",
       dict(a_r_p=85, a_r_y=70, t_y=38, t_p=2, m_p=-95, m_r=180),
       dict(a_r_p=88, a_r_y=-50, t_y=-32, t_p=8, m_p=-90, m_r=180, fwd=1.5),
       dict(a_r_p=82, a_r_y=-75, t_y=-42, t_p=6, m_p=-85, m_r=180, fwd=1.5))
attack("atk_blade_3",
       dict(a_r_p=178, a_r_o=8, t_p=-14, h_p=-8, m_p=-10),
       dict(a_r_p=45, a_r_o=4, t_p=24, h_p=10, m_p=-70, fwd=2.5),
       dict(a_r_p=25, t_p=28, h_p=12, m_p=-60, fwd=2.5), hit=0.5,
       legs=dict(l_r_p=-24, l_l_p=34, l_r_o=4, l_l_o=4))
attack("atk_blade_4",
       dict(a_r_p=88, a_r_y=-80, root_y=-40, t_y=-30, t_p=4, m_p=-95),
       dict(a_r_p=88, a_r_y=40, root_y=200, t_y=20, t_p=10, m_p=-90, fwd=1.5),
       dict(a_r_p=85, a_r_y=50, root_y=330, t_y=25, m_p=-85, fwd=1.5), hit=0.5,
       legs=dict(l_r_p=-24, l_l_p=28, l_r_o=10, l_l_o=10))

# Two-handed heavies: the left hand stays on the hilt (rig IK); big body
# turns and slams.
attack("atk_heavy_1",
       dict(a_r_p=95, a_r_y=-60, t_y=-50, t_p=4, m_p=-80, m_y=-10),
       dict(a_r_p=85, a_r_y=50, t_y=48, t_p=12, m_p=-85, fwd=2),
       dict(a_r_p=80, a_r_y=70, t_y=60, t_p=10, m_p=-80, fwd=2))
attack("atk_heavy_2",
       dict(a_r_p=90, a_r_y=75, t_y=50, t_p=4, m_p=-85, m_r=180),
       dict(a_r_p=85, a_r_y=-45, t_y=-48, t_p=12, m_p=-85, m_r=180, fwd=2),
       dict(a_r_p=80, a_r_y=-60, t_y=-60, t_p=10, m_p=-80, m_r=180, fwd=2))
attack("atk_heavy_3",
       dict(a_r_p=180, a_r_y=20, t_p=-18, h_p=-10, m_p=0, bob=1),
       dict(a_r_p=40, a_r_y=20, t_p=32, h_p=14, m_p=-60, fwd=3.5),
       dict(a_r_p=25, a_r_y=20, t_p=34, h_p=14, m_p=-50, fwd=3.5), hit=0.5,
       legs=dict(l_r_p=-28, l_l_p=40, l_r_o=6, l_l_o=6))
attack("atk_heavy_4",
       dict(a_r_p=92, a_r_y=-70, root_y=-50, t_y=-35, t_p=6, m_p=-90),
       dict(a_r_p=90, a_r_y=40, root_y=250, t_y=25, t_p=12, m_p=-90, fwd=1.5),
       dict(a_r_p=88, a_r_y=50, root_y=345, t_y=25, t_p=10, m_p=-85, fwd=1.5), hit=0.5,
       legs=dict(l_r_p=-26, l_l_p=30, l_r_o=12, l_l_o=12))

# Daggers and fists: quick jabs and slashes, a lunging stab.
attack("atk_dagger_1",
       dict(a_r_p=30, a_r_o=12, t_y=-22, m_p=-20),
       dict(a_r_p=92, a_r_o=0, t_y=22, t_p=8, m_p=-95, fwd=2),
       hit=0.4)
attack("atk_dagger_2",
       dict(a_r_p=85, a_r_y=-70, t_y=-30, m_p=-90),
       dict(a_r_p=85, a_r_y=40, t_y=32, m_p=-90),
       hit=0.4)
attack("atk_dagger_3",
       dict(a_r_p=170, a_r_o=12, t_p=-10, m_p=20),
       dict(a_r_p=60, a_r_o=0, t_p=16, m_p=-110, fwd=2),
       hit=0.45)
attack("atk_dagger_4",
       dict(a_r_p=10, a_r_o=14, t_y=-30, t_p=-6, m_p=0),
       dict(a_r_p=92, t_y=25, t_p=16, m_p=-95, fwd=5, bob=1),
       hit=0.45, legs=dict(l_r_p=-38, l_l_p=50))
attack("atk_fist_1",
       dict(a_r_p=20, a_r_o=10, t_y=-18),
       dict(a_r_p=92, a_r_o=0, t_y=25, t_p=8, fwd=1.5), hit=0.4)
attack("atk_fist_2",
       dict(a_l_p=20, a_l_o=10, t_y=18),
       dict(a_l_p=92, a_l_o=0, t_y=-25, t_p=8, fwd=1.5), hit=0.4)
attack("atk_fist_3",
       dict(a_r_p=-20, a_r_o=16, t_p=-8, bob=0),
       dict(a_r_p=170, a_r_o=4, t_p=-12, h_p=-16, bob=3), hit=0.45)
attack("atk_fist_4",
       dict(a_r_p=10, a_l_p=10, a_r_o=12, a_l_o=12, t_p=-6),
       dict(a_r_p=92, a_l_p=92, a_r_o=-4, a_l_o=-4, t_p=14, fwd=5), hit=0.45,
       legs=dict(l_r_p=-38, l_l_p=50))

# Spears and polearms (two-handed: rig IK keeps the left hand on the
# shaft): thrusts, a sweep and a lunge.
SPEAR = dict(a_r_p=60, a_r_y=20, t_y=-25, m_p=-90)
attack("atk_spear_1",
       dict(SPEAR, a_r_p=40, t_y=-35, fwd=-1),
       dict(SPEAR, a_r_p=88, a_r_y=10, t_y=10, t_p=10, fwd=3), hit=0.42)
attack("atk_spear_2",
       dict(SPEAR, a_r_p=35, t_y=-40, fwd=-1),
       dict(SPEAR, a_r_p=90, a_r_y=5, t_y=15, t_p=12, fwd=3.5), hit=0.42)
attack("atk_spear_3",
       dict(a_r_p=88, a_r_y=-70, t_y=-55, m_p=-90),
       dict(a_r_p=88, a_r_y=45, t_y=50, m_p=-90), hit=0.5)
attack("atk_spear_4",
       dict(SPEAR, a_r_p=20, t_y=-45, t_p=-8, fwd=-1.5),
       dict(SPEAR, a_r_p=92, a_r_y=5, t_y=20, t_p=20, fwd=7, bob=1), hit=0.45,
       legs=dict(l_r_p=-42, l_l_p=55))

# Staves and wands: a sweep and an overhead smash.
attack("atk_staff_1",
       dict(a_r_p=88, a_r_y=-70, t_y=-40, m_p=-90),
       dict(a_r_p=88, a_r_y=40, t_y=40, m_p=-90))
attack("atk_staff_4",
       dict(a_r_p=178, t_p=-14, m_p=0, bob=1),
       dict(a_r_p=50, t_p=26, m_p=-60, fwd=2.5), hit=0.5,
       legs=dict(l_r_p=-26, l_l_p=40))

# Weapon arts.
attack("art_spin",
       dict(a_r_p=90, a_r_o=70, a_l_p=60, a_l_o=70, root_y=-30, m_p=-90),
       dict(a_r_p=90, a_r_o=75, a_l_p=60, a_l_o=75, root_y=330, m_p=-90, bob=1.5),
       dict(a_r_p=88, a_r_o=70, a_l_p=55, a_l_o=70, root_y=380, m_p=-85), hit=0.5)
attack("art_slam",
       dict(a_r_p=180, a_l_p=180, t_p=-20, bob=4, m_p=0),
       dict(a_r_p=35, a_l_p=35, t_p=34, m_p=-60, fwd=2), hit=0.55,
       legs=dict(l_r_p=-20, l_l_p=30, l_r_o=14, l_l_o=14))
attack("art_roar",
       dict(a_r_p=20, a_r_o=40, a_l_p=20, a_l_o=40, t_p=14, h_p=14),
       dict(a_r_p=40, a_r_o=85, a_l_p=40, a_l_o=85, t_p=-16, h_p=-28, bob=1), hit=0.4,
       legs=dict(l_r_o=12, l_l_o=12))


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
        "/** Version of the loaded clip data (see animVersion). */",
        "declare global animVer: str;",
        "",
        "/** Version of the clip data in this code: when it differs from",
        " * animVer, the loaded clips are stale (reload with loadClips). */",
        "function animVersion(): str {",
        "    return \"@VER@\";",
        "}",
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
        "/** Loads every clip. The clips are split over small functions",
        " * (clipsN): DiamondFire can't pick a very large code line back up,",
        " * so one huge function could never be replaced on the plot. */",
        "function loadClips {",
        "    global animStr = {};",
        "    global animData = {};",
        "    global animMeta = {};",
        "    global stanceDelta = {};",
        "    global animVer = animVersion();",
    ]
    chunks: list[list[str]] = [[]]
    size = 0
    for c in CLIPS:
        n = LOOP_SAMPLES if c.loop else SAMPLES
        smp = c.sample(n)
        flat = [fmt(v) for row in smp for v in row]
        body = [f"    global animStr[\"{c.name}\"] = \"{','.join(flat)}\";",
                f"    global animMeta[\"{c.name}\"] = [{n}, {int(c.loop)}, {fmt(c.hit)}, {int(c.mask == 'upper')}];"]
        if size and size + len(body[0]) > CHUNK:
            chunks.append([])
            size = 0
        chunks[-1] += body
        size += len(body[0])
        data[c.name] = {"loop": c.loop, "hit": c.hit, "mask": c.mask, "samples": [[round(v, 2) for v in r] for r in smp],
                        "keys": [[t, [round(v, 2) for v in p]] for t, p in c.poses()]}
    lines += [f"    clips{i + 1}();" for i in range(len(chunks))]
    lines.append("}")
    for i, body in enumerate(chunks):
        lines += ["", f"function clips{i + 1} {{"] + body + ["}"]
    lines += ["", "/** Index of channel name in a pose (generated). */"]
    lines += ["function chan(name: str): num {",
              "    line c = {" + ", ".join(f"{c}: {i + 1}" for i, c in enumerate(CHANNELS)) + "};",
              "    return line c[name] as num;", "}", ""]
    text = "\n".join(lines) + "\n"
    text = text.replace("@VER@", hashlib.sha1(text.encode()).hexdigest()[:10])
    (ROOT / "tc/anim_data.tc").write_text(text)
    out = ROOT / "tools/viewer/anim_data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"channels": CHANNELS, "rest": [REST[c] for c in CHANNELS], "upper": UPPER, "clips": data}))
    print(f"anim: {len(CLIPS)} clips, {len(CHANNELS)} channels")


if __name__ == "__main__":
    main()
