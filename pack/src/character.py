#!/usr/bin/env python3
"""The character rig: body parts, clothes, armor, hair, ears, beards, tails.

Every character is ten item displays: head, torso, upper arms, forearms
(with hands), thighs and shins (with feet). Each part's item model
(rpg:body/<part>) is a composite whose layers are picked by the item's
custom model data strings and tinted by its colors (see PLAN.md,
"Character rig"):

  strings[0] build: m, f, dm, df (dwarf builds are short and stocky)
  strings[1] armor piece on this part
  strings[2] hair style (head) / tail (torso)
  strings[3] ears or horns (head)
  strings[4] beard (head)

  colors: 0 skin, 1 hair, 2 eyes, 3 clothes, 4 armor main, 5 armor trim,
          6 horns, 7 trousers

Shapes use chamfered boxes (Model.rbox) and bars between two points
(Model.seg, any angle), so limbs read as rounded and hair, horns, ears and
tails curve.

Writes pack/assets/rpg/{models,items,textures}, tc/rig_data.tc and
tools/viewer/rig_data.json.
"""

from __future__ import annotations

import json
import math
import random

from common import (ROOT, Model, composite, fit_gui, make_texture, model_node, select_node, write_item)

SKIN, HAIR, EYE, CLOTH, ARM_MAIN, ARM_TRIM, HORN, PANTS = range(8)

# Per build, in model pixels (16 per block at scale 1; feet at y 0):
#   hip      height of the hip joints; hx: their x
#   tw/td    chest width and depth; ww waist width; pw pelvis width
#   neck     height of the neck joint (top of torso)
#   sx/sy    shoulder joint x and height
#   aw       arm thickness; ua/fa upper arm / forearm length (joint to joint,
#            forearm to the grip)
#   lw       leg thickness; th/sh thigh / shin length
BUILDS = {
    "m": dict(hip=12, hx=2.0, tw=8.4, td=4.4, ww=7.2, pw=7.6, neck=24, sx=5.9, sy=22.4, aw=3.8, ua=5.8, fa=4.6,
              lw=3.9, th=6.0, sh=6.0, bust=False),
    "f": dict(hip=12, hx=1.9, tw=7.4, td=4.0, ww=6.0, pw=7.8, neck=24, sx=5.1, sy=22.5, aw=3.2, ua=5.8, fa=4.6,
              lw=3.7, th=6.0, sh=6.0, bust=True),
    "dm": dict(hip=8, hx=2.5, tw=10.6, td=5.8, ww=9.6, pw=9.4, neck=18.5, sx=7.2, sy=17.0, aw=4.4, ua=4.6, fa=4.0,
               lw=4.8, th=4.0, sh=4.0, bust=False),
    "df": dict(hip=8, hx=2.3, tw=9.4, td=5.2, ww=8.0, pw=9.4, neck=18.5, sx=6.4, sy=17.0, aw=3.9, ua=4.6, fa=4.0,
               lw=4.4, th=4.0, sh=4.0, bust=True),
}

ARMORS = ["leather", "chain", "scale", "plate", "robe", "ranger", "noble", "bone"]
HAIRS = ["short", "long", "ponytail", "braid", "bun", "mohawk", "curly", "spiky", "bob", "shaggy"]
EARS = ["human", "elf", "cat", "wolf", "bear", "rabbit", "demon"]
BEARDS = ["stubble", "short", "full", "long", "braided", "goatee", "mustache"]
TAILS = ["cat", "wolf", "bear", "rabbit", "demon"]

T: dict[str, str] = {}


def textures():
    for kind in ("skin", "cloth", "leather", "metal", "chain", "hair", "fur", "dark", "white", "bone"):
        T[kind] = make_texture(f"body_{kind}", kind)
    T["lips"] = make_texture("body_lips", "skin", rgb=(196, 108, 104))
    T["boot"] = make_texture("body_boot", "leather", rgb=(104, 70, 44))
    T["sole"] = make_texture("body_sole", "leather", rgb=(52, 38, 28))
    T["belt"] = make_texture("body_belt", "leather", rgb=(70, 48, 30))
    T["buckle"] = make_texture("body_buckle", "metal", rgb=(232, 196, 96))
    T["brow"] = make_texture("body_brow", "hair", rgb=(200, 200, 200))
    T["pupil"] = make_texture("body_pupil", "dark", rgb=(20, 20, 24))
    T["shade"] = make_texture("body_shade", "skin", rgb=(214, 214, 214))
    T["iron"] = make_texture("body_iron", "metal", rgb=(150, 150, 156))


# ---------------------------------------------------------------- head
#
# Head frame: the neck joint at the origin, the skull from y 0.6 to 8.6,
# x and z -4..4, face toward +Z.


def head_base(female: bool = False) -> Model:
    m = Model()
    s = T["skin"]
    # Skull with a narrower jaw and chin.
    m.rbox((-4, 2.2, -4), (4, 8.6, 4), s, SKIN, r=0.7)
    m.rbox((-3.5, 0.6, -3.6), (3.5, 2.8, 3.8), s, SKIN, r=0.6)
    if not female:
        m.rbox((-1.5, 0.4, 2.8), (1.5, 1.4, 4.0), s, SKIN, r=0.3)
    m.rbox((-1.6, -1.2, -1.6), (1.6, 1.0, 1.4), s, SKIN, r=0.5)
    # Eyes: white, colored iris, dark pupil, a glint; lids above.
    for side in (1, -1):
        x0, x1 = sorted((side * 0.7, side * 2.9))
        m.box((x0, 4.0, 3.95), (x1, 5.4, 4.05), T["white"])
        ix0, ix1 = sorted((side * 1.1, side * 2.3))
        m.box((ix0, 4.0, 4.0), (ix1, 5.4, 4.1), T["white"], EYE)
        px0, px1 = sorted((side * 1.45, side * 1.95))
        m.box((px0, 4.3, 4.06), (px1, 5.1, 4.13), T["pupil"])
        gx = side * 1.45
        m.box((gx - 0.2, 4.9, 4.1), (gx + 0.15, 5.25, 4.16), T["white"])
        bx0, bx1 = sorted((side * 0.6, side * 3.2))
        tilt = side * (6 if female else -4)
        m.box((bx0, 5.85, 3.9), (bx1, 6.45, 4.25), T["brow"], HAIR, rot=("z", tilt, (side * 1.9, 6.1, 4)))
        if female:
            m.box((x0 - 0.15 * side, 5.3, 3.98), (x1 + 0.25 * side, 5.55, 4.14), T["pupil"])
    # Nose: bridge and tip.
    m.rbox((-0.55, 3.0, 3.9), (0.55, 4.6, 4.6), s, SKIN, r=0.2)
    m.rbox((-0.85, 2.7, 4.0), (0.85, 3.4, 4.85), s, SKIN, r=0.25)
    # Mouth.
    if female:
        m.box((-1.2, 1.55, 3.85), (1.2, 2.25, 3.95), T["lips"])
    else:
        m.box((-1.3, 1.75, 3.85), (1.3, 2.1, 3.92), T["shade"], SKIN)
    # Cheekbones.
    for side in (1, -1):
        x0, x1 = sorted((side * 2.6, side * 3.8))
        m.box((x0, 3.0, 3.6), (x1, 3.9, 3.95), s, SKIN)
    return m


def lock(m: Model, root, tip, w: float, d: float, tex: str = None, tint: int = HAIR):
    """One lock of hair (a bar from root to tip, tapering by halves)."""
    tex = tex or T["hair"]
    mid = [(root[i] + tip[i]) / 2 for i in range(3)]
    m.seg(root, mid, w, d, tex, tint)
    m.seg(mid, tip, w * 0.75, d * 0.8, tex, tint)


def scalp(m: Model, thick: float = 0.55, back_to: float = 3.5, side_to: float = 4.6, tex: str | None = None):
    """Hair cap over the skull: top, back down to back_to, sides to side_to."""
    h = tex or T["hair"]
    m.rbox((-4.2, 7.4, -4.25), (4.2, 9.0 + thick * 0.4, 4.1), h, HAIR, r=0.6)
    m.rbox((-4.25, back_to, -4.35), (4.25, 8.8, -3.0), h, HAIR, r=0.5)
    for side in (1, -1):
        x0, x1 = sorted((side * 3.6, side * 4.3))
        m.box((x0, side_to, -4.2), (x1, 8.6, 2.6), h, HAIR)


def fringe(m: Model, n: int, length: float, seed: int, sweep: float = 0.0):
    """Locks falling over the forehead."""
    rng = random.Random(seed)
    for i in range(n):
        x = -3.6 + 7.2 * (i + 0.5) / n
        L = length * rng.uniform(0.7, 1.15)
        root = (x, 8.6, 3.6)
        tip = (x + sweep + rng.uniform(-0.5, 0.5), 8.6 - L, 4.45)
        lock(m, root, tip, 7.4 / n + 0.5, 0.8)


def hair(style: str) -> Model:
    m = Model()
    h = T["hair"]
    rng = random.Random(style)
    if style == "short":
        scalp(m)
        fringe(m, 5, 2.4, 1, sweep=0.8)
        for side in (1, -1):
            lock(m, (side * 4.1, 6.5, 0.6), (side * 4.35, 4.0, 1.4), 1.2, 1.4)
    elif style == "long":
        scalp(m, back_to=2.0)
        fringe(m, 6, 2.0, 2, sweep=-0.4)
        for i in range(6):
            x = -3.4 + 6.8 * i / 5
            lock(m, (x, 6.5, -4.0), (x * 1.08, -6.0 + rng.uniform(-1.2, 0.8), -4.6 - abs(x) * 0.1), 1.6, 1.1)
        for side in (1, -1):
            for z in (-2.5, 0.2, 2.0):
                lock(m, (side * 4.2, 7.5, z), (side * 4.9, -3.5 + rng.uniform(-1, 1) - z * 0.6, z * 1.1 + 0.4), 1.4, 1.6)
    elif style == "ponytail":
        scalp(m, thick=0.2)
        fringe(m, 4, 1.4, 3, sweep=0.6)
        m.rbox((-1.1, 6.0, -5.2), (1.1, 7.6, -4.0), T["belt"], None, r=0.3)
        pts = [(0, 6.8, -5.0), (0, 5.2, -6.4), (0, 2.2, -6.8), (0, -0.8, -6.4), (0, -3.0, -5.8)]
        for i in range(len(pts) - 1):
            w = 2.4 - i * 0.45
            m.seg(pts[i], pts[i + 1], w, w * 0.9, h, HAIR, round_=True)
    elif style == "braid":
        scalp(m, back_to=4.5)
        fringe(m, 5, 1.6, 4, sweep=-0.6)
        y = 5.5
        for i in range(6):
            off = 0.5 if i % 2 else -0.5
            m.rbox((off - 1.0, y - 2.1, -5.4), (off + 1.0, y, -3.8), h, HAIR, r=0.4)
            y -= 1.8
        m.rbox((-0.8, y - 1.0, -5.2), (0.8, y + 0.2, -4.0), T["belt"], None, r=0.2)
        lock(m, (0, y - 0.8, -4.6), (0, y - 2.6, -4.7), 1.4, 1.0)
    elif style == "bun":
        scalp(m, back_to=4.0)
        fringe(m, 3, 1.0, 5)
        m.rbox((-2.0, 7.0, -6.3), (2.0, 10.6, -2.6), h, HAIR, r=1.0)
        m.rbox((-2.3, 7.8, -5.0), (2.3, 9.0, -3.6), T["belt"], None, r=0.3)
        for side in (1, -1):
            lock(m, (side * 3.9, 7.0, 2.5), (side * 4.2, 2.6, 3.0), 0.9, 0.8)
    elif style == "mohawk":
        scalp(m, thick=0, back_to=3.0, tex=T["shade"])
        for i in range(8):
            z = 3.4 - i * 1.0
            m.seg((0, 8.4, z), (0, 11.8 - abs(i - 3) * 0.35, z - 1.0), 1.5, 1.2, h, HAIR)
    elif style == "curly":
        for i in range(34):
            a = rng.uniform(0, 2 * math.pi)
            yy = rng.uniform(3.0, 9.4)
            r = 4.4 if yy < 8.4 else rng.uniform(0, 3.8)
            x, z = math.cos(a) * r, math.sin(a) * r - 0.4
            if z > 3.2 and yy < 7.5:
                continue
            c = rng.uniform(1.4, 2.2)
            m.rbox((x - c, yy - c, z - c), (x + c, yy + c, z + c), h, HAIR, r=c * 0.35)
    elif style == "spiky":
        scalp(m, thick=0.1, back_to=4.5)
        for i in range(11):
            a = 2 * math.pi * i / 11
            base = (math.cos(a) * 2.2, 8.8, math.sin(a) * 2.2 - 0.3)
            tip = (math.cos(a) * 4.8, 11.6 + rng.uniform(-0.6, 0.8), math.sin(a) * 4.4 - 0.6)
            lock(m, base, tip, 1.8, 1.8)
        fringe(m, 4, 2.0, 7, sweep=1.0)
    elif style == "bob":
        scalp(m, back_to=1.5, side_to=1.5)
        fringe(m, 7, 2.6, 8)
        for side in (1, -1):
            m.rbox((side * 4.05 - 0.75, 1.0, -4.4), (side * 4.05 + 0.75, 4.4, 3.4), h, HAIR, r=0.45)
        m.rbox((-4.5, 1.0, -4.8), (4.5, 4.0, -3.4), h, HAIR, r=0.5)
    elif style == "shaggy":
        scalp(m, back_to=2.5)
        fringe(m, 6, 3.0, 9, sweep=0.5)
        for i in range(10):
            a = math.pi + math.pi * i / 9
            root = (math.cos(a) * 4.0, 7.8, math.sin(a) * 4.0 - 0.3)
            tip = (math.cos(a) * 5.0, 2.0 + rng.uniform(-1.5, 1.0), math.sin(a) * 5.0 - 0.6)
            lock(m, root, tip, 1.8, 1.3)
    else:
        raise ValueError(style)
    return m


def ears(kind: str) -> Model:
    m = Model()
    s, f = T["skin"], T["fur"]
    if kind == "human":
        for side in (1, -1):
            x0, x1 = sorted((side * 3.9, side * 4.6))
            m.rbox((x0, 3.4, -0.6), (x1, 5.6, 1.0), s, SKIN, r=0.25)
    elif kind in ("elf", "demon"):
        for side in (1, -1):
            x0, x1 = sorted((side * 3.9, side * 4.6))
            m.rbox((x0, 3.3, -0.6), (x1, 5.4, 0.9), s, SKIN, r=0.25)
            m.seg((side * 4.3, 4.8, 0.1), (side * 6.6, 7.0, -0.9), 0.9, 1.4, s, SKIN)
            m.seg((side * 6.4, 6.8, -0.8), (side * 7.6, 8.2, -1.4), 0.6, 0.8, s, SKIN)
        if kind == "demon":
            for side in (1, -1):
                pts = [(side * 2.6, 8.4, 1.0), (side * 3.4, 10.2, 0.4), (side * 4.4, 11.4, -1.0),
                       (side * 5.2, 11.6, -2.8), (side * 5.4, 10.8, -4.2)]
                for i in range(len(pts) - 1):
                    w = 1.9 - i * 0.38
                    m.seg(pts[i], pts[i + 1], w, w, T["bone"], HORN, round_=True)
    elif kind in ("cat", "wolf"):
        tall = 3.4 if kind == "cat" else 4.2
        for side in (1, -1):
            bx = side * 2.6
            for i in range(4):
                y0 = 8.2 + i * tall / 4
                w = 3.0 - i * 0.7
                m.rbox((bx - w / 2 + side * i * 0.25, y0, -0.7), (bx + w / 2 + side * i * 0.25, y0 + tall / 4 + 0.2, 0.7), f, HAIR, r=0.2)
            m.box((bx - 1.0, 8.6, 0.68), (bx + 1.0, 8.2 + tall * 0.7, 0.78), T["shade"], SKIN)
    elif kind == "bear":
        for side in (1, -1):
            x = side * 3.1
            m.rbox((x - 1.5, 7.6, -0.8), (x + 1.5, 10.4, 0.8), f, HAIR, r=0.6)
            m.rbox((x - 0.85, 8.2, 0.7), (x + 0.85, 9.8, 0.9), T["shade"], SKIN, r=0.2)
    elif kind == "rabbit":
        for side in (1, -1):
            x = side * 1.9
            m.seg((x, 8.4, 0), (x + side * 1.4, 13.5, -0.6), 1.9, 1.1, f, HAIR, round_=True)
            m.seg((x + side * 1.4, 13.3, -0.6), (x + side * 3.6, 16.0, -1.8), 1.7, 1.0, f, HAIR, round_=True)
            m.seg((x + side * 0.2, 9.0, 0.6), (x + side * 1.4, 13.2, 0.0), 1.0, 0.2, T["shade"], SKIN)
    else:
        raise ValueError(kind)
    return m


def beard(kind: str) -> Model:
    m = Model()
    h = T["hair"]
    rng = random.Random(kind)
    if kind == "stubble":
        m.box((-3.55, 0.6, 3.3), (3.55, 3.0, 3.86), T["shade"], HAIR)
    elif kind == "mustache":
        for side in (1, -1):
            m.seg((side * 0.3, 2.45, 4.3), (side * 2.6, 1.6, 4.1), 1.0, 0.7, h, HAIR, round_=True)
    elif kind == "goatee":
        m.rbox((-1.2, -0.6, 3.2), (1.2, 1.6, 4.3), h, HAIR, r=0.35)
        for side in (1, -1):
            m.seg((side * 0.3, 2.45, 4.3), (side * 1.9, 1.8, 4.1), 0.9, 0.6, h, HAIR)
    else:
        size = {"short": 1.0, "full": 1.6, "long": 2.6, "braided": 2.2}[kind]
        m.rbox((-3.7, 0.2, 1.4), (3.7, 3.0, 4.3), h, HAIR, r=0.6)
        for side in (1, -1):
            m.seg((side * 0.3, 2.45, 4.3), (side * 2.4, 1.7, 4.2), 1.0, 0.7, h, HAIR, round_=True)
        if kind == "braided":
            for side in (1, -1):
                y = 0.2
                for i in range(4):
                    x = side * 1.5 + (0.3 if i % 2 else -0.3)
                    m.rbox((x - 0.9, y - 2.0, 2.4), (x + 0.9, y, 4.1), h, HAIR, r=0.35)
                    y -= 1.7
                m.rbox((side * 1.5 - 0.7, y - 0.7, 2.6), (side * 1.5 + 0.7, y + 0.2, 3.9), T["buckle"], None, r=0.2)
        else:
            for i in range(7):
                x = -3.0 + i
                L = size * 3.2 * (1 - abs(x) / 5) + rng.uniform(-0.6, 0.6)
                lock(m, (x, 0.8, 3.6), (x * 0.8, 0.8 - L, 3.4 - L * 0.25), 1.5, 1.4)
    return m


def helmet(kind: str) -> Model:
    m = Model()
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def shell(tex, tint, y0=0.4, top=9.4, open_face=True):
        m.rbox((-4.7, 6.6, -4.75), (4.7, top, 4.6), tex, tint, r=0.9)
        m.rbox((-4.75, y0, -4.8), (4.75, 7.2, -3.0), tex, tint, r=0.5)
        for side in (1, -1):
            x0, x1 = sorted((side * 3.9, side * 4.8))
            m.rbox((x0, y0, -4.4), (x1, 7.2, 3.4 if open_face else 4.6), tex, tint, r=0.3)
        if not open_face:
            m.rbox((-4.7, y0, 3.9), (4.7, 3.7, 4.8), tex, tint, r=0.3)
            m.rbox((-4.7, 5.6, 3.9), (4.7, 7.2, 4.8), tex, tint, r=0.3)
            m.box((-0.5, 3.7, 4.0), (0.5, 5.6, 4.85), tex, tint)
            for x in (-2.5, -1.2, 1.2, 2.5):
                m.box((x - 0.2, 1.0, 4.75), (x + 0.2, 3.2, 4.9), T["pupil"])

    if kind == "leather":
        m.rbox((-4.5, 5.8, -4.6), (4.5, 9.2, 4.4), lea, ARM_MAIN, r=0.9)
        m.box((-4.65, 5.6, -4.7), (4.65, 6.4, 4.55), lea, ARM_TRIM)
        for side in (1, -1):
            x0, x1 = sorted((side * 3.9, side * 4.6))
            m.rbox((x0, 2.0, -2.0), (x1, 6.0, 1.5), lea, ARM_MAIN, r=0.3)
    elif kind == "chain":
        shell(T["chain"], ARM_MAIN)
        m.rbox((-3.6, -1.4, -3.6), (3.6, 1.0, 3.4), T["chain"], ARM_MAIN, r=0.6)
        m.box((-4.8, 6.3, -4.85), (4.8, 6.9, 4.65), lea, ARM_TRIM)
    elif kind == "scale":
        shell(met, ARM_MAIN, top=9.6)
        m.box((-4.85, 5.9, -4.9), (4.85, 6.7, 4.7), met, ARM_TRIM)
        m.rbox((-4.9, 5.9, 4.2), (4.9, 6.7, 5.8), met, ARM_TRIM, r=0.2)
        m.box((-0.4, 9.3, -3.8), (0.4, 10.4, 3.8), met, ARM_TRIM)
    elif kind == "plate":
        shell(met, ARM_MAIN, open_face=False, top=9.8)
        m.box((-0.45, 9.4, -4.4), (0.45, 10.6, 4.4), met, ARM_TRIM)
        m.box((-4.85, 3.8, 4.3), (4.85, 4.2, 4.95), met, ARM_TRIM)
        # Plume.
        for i in range(5):
            m.seg((0, 10.4, 2.0 - i * 1.6), (0, 12.2 + (2 - abs(i - 2)) * 0.5, 0.2 - i * 2.2), 0.9, 1.6, clo, ARM_TRIM)
    elif kind == "robe":
        m.rbox((-6.4, 7.6, -6.4), (6.4, 8.4, 6.2), clo, ARM_MAIN, r=0.3)
        pts = [(0, 8.2, 0), (0, 11.0, -0.6), (0, 13.2, -2.0), (0, 14.8, -4.0), (0, 15.4, -6.0)]
        widths = [8.8, 6.6, 4.4, 2.6, 1.4]
        for i in range(len(pts) - 1):
            m.seg(pts[i], pts[i + 1], widths[i], widths[i], clo, ARM_MAIN, round_=True)
        m.box((-4.5, 8.3, -4.5), (4.5, 9.3, 4.3), clo, ARM_TRIM)
    elif kind == "ranger":
        m.rbox((-4.9, 2.0, -4.9), (4.9, 9.5, 3.4), clo, ARM_MAIN, r=0.9)
        m.rbox((-4.4, 7.2, 3.0), (4.4, 9.3, 5.0), clo, ARM_MAIN, r=0.5)
        m.seg((0, 8.4, -4.4), (0, 5.4, -7.0), 3.0, 1.4, clo, ARM_MAIN, round_=True)
        m.rbox((-4.6, -0.8, -4.4), (4.6, 2.2, 3.2), clo, ARM_MAIN, r=0.6)
    elif kind == "noble":
        m.rbox((-4.5, 8.2, -4.5), (4.5, 9.6, 4.4), met, ARM_TRIM, r=0.2)
        for i in range(8):
            a = 2 * math.pi * i / 8
            x, z = math.cos(a) * 4.4, math.sin(a) * 4.4
            m.seg((x, 9.4, z), (x * 1.04, 11.0, z * 1.04), 0.8, 0.8, met, ARM_TRIM)
        m.rbox((-0.7, 8.4, 4.3), (0.7, 9.4, 4.8), T["white"], ARM_MAIN, r=0.2)
    elif kind == "bone":
        shell(T["bone"], ARM_MAIN, top=9.6)
        for side in (1, -1):
            pts = [(side * 4.4, 8.0, 0.5), (side * 6.2, 10.0, 0.2), (side * 7.0, 12.5, -0.8)]
            for i in range(2):
                m.seg(pts[i], pts[i + 1], 1.6 - i * 0.5, 1.6 - i * 0.5, T["bone"], ARM_TRIM, round_=True)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- torso
#
# Torso frame: the hip joint center at the origin, up to the neck at
# b["neck"] - b["hip"].


def torso_base(b: dict) -> Model:
    m = Model()
    H = b["neck"] - b["hip"]
    tw, td, ww, pw = b["tw"], b["td"], b["ww"], b["pw"]
    c = T["cloth"]
    # Pelvis, waist, chest (tunic), with a collar opening.
    m.rbox((-pw / 2, -0.6, -td / 2 + 0.1), (pw / 2, H * 0.22, td / 2 - 0.1), T["cloth"], PANTS, r=0.6)
    m.rbox((-ww / 2, H * 0.15, -td / 2 + 0.2), (ww / 2, H * 0.55, td / 2 - 0.1), c, CLOTH, r=0.6)
    m.rbox((-tw / 2, H * 0.5, -td / 2), (tw / 2, H - 0.2, td / 2), c, CLOTH, r=0.8)
    m.rbox((-1.8, H - 1.2, td / 2 - 0.3), (1.8, H, td / 2 + 0.05), T["skin"], SKIN, r=0.3)
    m.box((-0.3, H - 3.0, td / 2 - 0.02), (0.3, H - 1.2, td / 2 + 0.08), T["shade"], CLOTH)
    # Belt with buckle and pouch.
    m.rbox((-pw / 2 - 0.15, H * 0.17, -td / 2 - 0.1), (pw / 2 + 0.15, H * 0.17 + 1.1, td / 2 + 0.1), T["belt"], None, r=0.2)
    m.rbox((-0.8, H * 0.17 - 0.1, td / 2), (0.8, H * 0.17 + 1.2, td / 2 + 0.35), T["buckle"], None, r=0.15)
    m.rbox((pw / 2 - 2.2, H * 0.17 - 1.6, td / 2 - 0.2), (pw / 2 - 0.6, H * 0.17 + 0.3, td / 2 + 0.7), T["leather"], PANTS, r=0.3)
    if b["bust"]:
        for side in (1, -1):
            x = side * tw * 0.22
            m.rbox((x - 1.7, H * 0.62, td / 2 - 0.4), (x + 1.7, H * 0.84, td / 2 + 1.0), c, CLOTH, r=0.7)
    # Shoulders: rounded caps that hide the arm joints.
    for side in (1, -1):
        x = side * (tw / 2 - 0.3)
        m.rbox((x - 1.6, H - 2.6, -td / 2 + 0.3), (x + 1.6, H - 0.2, td / 2 - 0.3), c, CLOTH, r=0.8)
    return m


def torso_armor(kind: str, b: dict) -> Model:
    m = Model()
    H = b["neck"] - b["hip"]
    tw, td, ww, pw = b["tw"] + 0.8, b["td"] + 0.8, b["ww"] + 0.8, b["pw"] + 0.8
    bust = b["bust"]
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def body(tex, tint, y0=0.0, r=0.8):
        m.rbox((-pw / 2, y0, -td / 2 + 0.2), (pw / 2, H * 0.3, td / 2 - 0.1), tex, tint, r=r * 0.8)
        m.rbox((-ww / 2, H * 0.2, -td / 2 + 0.2), (ww / 2, H * 0.58, td / 2 - 0.1), tex, tint, r=r * 0.8)
        m.rbox((-tw / 2, H * 0.5, -td / 2), (tw / 2, H - 0.1, td / 2), tex, tint, r=r)
        if bust:
            for side in (1, -1):
                x = side * tw * 0.22
                m.rbox((x - 1.8, H * 0.62, td / 2 - 0.5), (x + 1.8, H * 0.85, td / 2 + 0.9), tex, tint, r=0.7)

    def skirt(tex, tint, length, flare=0.6, front=True, back=True, sides=True):
        """Panels hanging from the hips (front, back and sides apart, so
        the legs swing between them)."""
        if front:
            m.seg((0, 0.6, td / 2 - 0.1), (0, -length, td / 2 + flare), pw * 0.5, 0.6, tex, tint)
        if back:
            m.seg((0, 0.6, -td / 2 + 0.1), (0, -length, -td / 2 - flare), pw * 0.7, 0.6, tex, tint)
        if sides:
            for side in (1, -1):
                m.seg((side * (pw / 2 - 0.2), 0.6, 0), (side * (pw / 2 + flare), -length * 0.85, 0), 0.6, td * 0.75, tex, tint)

    if kind == "leather":
        body(lea, ARM_MAIN, 0.2)
        for side in (1, -1):
            m.box((side * 1.4 - 0.25, H * 0.25, td / 2 - 0.02), (side * 1.4 + 0.25, H - 0.3, td / 2 + 0.12), lea, ARM_TRIM)
        m.rbox((-pw / 2 - 0.1, H * 0.17, -td / 2 - 0.1), (pw / 2 + 0.1, H * 0.17 + 1.2, td / 2 + 0.1), lea, ARM_TRIM, r=0.2)
        skirt(lea, ARM_MAIN, 2.6, 0.4)
    elif kind == "chain":
        body(T["chain"], ARM_MAIN)
        skirt(T["chain"], ARM_MAIN, 4.0, 0.5)
        m.rbox((-pw / 2 - 0.1, H * 0.17, -td / 2 - 0.1), (pw / 2 + 0.1, H * 0.17 + 1.1, td / 2 + 0.1), lea, ARM_TRIM, r=0.2)
        m.rbox((-2.6, H - 1.0, -td / 2 + 0.4), (2.6, H + 0.8, td / 2 - 0.4), T["chain"], ARM_MAIN, r=0.6)
    elif kind == "scale":
        body(lea, ARM_TRIM)
        rows = 6
        for i in range(rows):
            y = H - 0.8 - i * (H - 1.5) / rows
            w = (tw if y > H * 0.5 else ww) + 0.2
            m.seg((0, y + 0.6, td / 2 + 0.05), (0, y - 1.3, td / 2 + 0.45), w, 0.4, met, ARM_MAIN)
            m.seg((0, y + 0.6, -td / 2 - 0.05), (0, y - 1.3, -td / 2 - 0.45), w, 0.4, met, ARM_MAIN)
        skirt(met, ARM_MAIN, 3.2, 0.6)
    elif kind == "plate":
        body(met, ARM_MAIN, H * 0.1, r=1.1)
        # Breastplate ridge and gorget.
        m.seg((0, H * 0.35, td / 2 + 0.05), (0, H - 0.5, td / 2 + 0.6), 0.9, 0.7, met, ARM_MAIN)
        m.rbox((-3.0, H - 0.9, -td / 2 + 0.3), (3.0, H + 1.3, td / 2 - 0.3), met, ARM_MAIN, r=0.6)
        m.box((-3.1, H + 0.6, -td / 2 + 0.25), (3.1, H + 1.0, td / 2 - 0.25), met, ARM_TRIM)
        # Faulds: overlapping lames over the hips.
        for i in range(3):
            y = H * 0.12 - i * 1.4
            m.rbox((-pw / 2 - 0.3 - i * 0.2, y - 1.2, -td / 2 - 0.2), (pw / 2 + 0.3 + i * 0.2, y + 0.4, td / 2 + 0.2 + i * 0.2), met, ARM_MAIN, r=0.35)
            m.box((-pw / 2 - 0.35 - i * 0.2, y - 1.25, td / 2 + 0.15 + i * 0.2), (pw / 2 + 0.35 + i * 0.2, y - 0.95, td / 2 + 0.3 + i * 0.2), met, ARM_TRIM)
        for x in (-2.4, 2.4):
            m.rbox((x - 0.35, H * 0.62, td / 2 + 0.3), (x + 0.35, H * 0.62 + 0.7, td / 2 + 0.6), met, ARM_TRIM, r=0.1)
    elif kind == "robe":
        body(clo, ARM_MAIN, -0.5)
        skirt(clo, ARM_MAIN, 9.0, 1.4)
        m.box((-0.8, -9.0, td / 2 + 0.05), (0.8, H, td / 2 + 0.25), clo, ARM_TRIM)
        m.rbox((-pw / 2 - 0.3, H * 0.17, -td / 2 - 0.3), (pw / 2 + 0.3, H * 0.17 + 1.0, td / 2 + 0.3), clo, ARM_TRIM, r=0.3)
        m.rbox((-3.2, H - 1.2, -td / 2 - 0.3), (3.2, H + 0.6, td / 2 + 0.3), clo, ARM_TRIM, r=0.5)
    elif kind == "ranger":
        body(lea, PANTS, 0.4)
        # Cloak: a mantle over the shoulders and a cape down the back.
        m.rbox((-tw / 2 - 0.6, H - 2.4, -td / 2 - 0.6), (tw / 2 + 0.6, H + 0.4, td / 2 + 0.6), clo, ARM_MAIN, r=0.8)
        m.seg((0, H - 0.5, -td / 2 - 0.6), (0, -6.0, -td / 2 - 2.4), tw + 0.8, 0.5, clo, ARM_MAIN)
        m.seg((tw / 2 - 1.2, H - 0.5, td / 2 + 0.2), (-tw / 2 + 1.2, 0.5, td / 2 + 0.4), 1.0, 0.5, lea, ARM_TRIM)
        m.rbox((-0.9, H - 2.0, td / 2 + 0.4), (0.9, H - 0.6, td / 2 + 0.9), T["buckle"], None, r=0.2)
    elif kind == "noble":
        body(clo, ARM_MAIN, -0.3)
        for y in (H * 0.3, H * 0.45, H * 0.6, H * 0.75):
            m.rbox((-0.4, y, td / 2 + 0.05), (0.4, y + 0.8, td / 2 + 0.4), T["buckle"], ARM_TRIM, r=0.15)
        m.seg((0, H - 0.4, -td / 2 - 0.4), (0, -8.5, -td / 2 - 2.6), tw + 1.6, 0.5, clo, ARM_TRIM)
        m.rbox((-tw / 2 - 0.6, H - 1.3, -td / 2 - 0.6), (tw / 2 + 0.6, H + 0.6, td / 2 + 0.6), T["white"], None, r=0.5)
        skirt(clo, ARM_MAIN, 2.2, 0.3, back=False)
    elif kind == "bone":
        body(lea, ARM_MAIN, 0.2)
        for i in range(5):
            y = H * 0.45 + i * 1.15
            for side in (1, -1):
                m.seg((side * 0.4, y, td / 2 + 0.2), (side * (tw / 2 - 0.2), y - 0.6, td / 2), 0.5, 0.5, T["bone"], ARM_TRIM)
        skirt(T["fur"], ARM_MAIN, 4.0, 0.9)
        for side in (1, -1):
            m.seg((side * (tw / 2 - 1.0), H, 0), (side * (tw / 2 + 1.6), H + 2.6, -0.4), 1.2, 1.2, T["bone"], ARM_TRIM, round_=True)
    else:
        raise ValueError(kind)
    return m


def tail(kind: str, b: dict) -> Model:
    m = Model()
    z = -b["td"] / 2 + 0.3
    f = T["fur"]
    if kind == "cat":
        pts = [(0, 0.8, z), (0, 0.0, z - 2.5), (0.6, 0.4, z - 5.0), (1.2, 2.2, z - 7.0), (1.0, 4.6, z - 8.0), (0.2, 6.4, z - 7.6)]
        for i in range(len(pts) - 1):
            m.seg(pts[i], pts[i + 1], 1.35, 1.35, f, HAIR, round_=True)
    elif kind == "wolf":
        pts = [(0, 1.0, z), (0, -0.6, z - 2.6), (0, -2.8, z - 4.6), (0, -5.0, z - 5.4)]
        widths = [1.8, 2.8, 2.6, 1.6]
        for i in range(len(pts) - 1):
            m.seg(pts[i], pts[i + 1], widths[i + 1], widths[i + 1], f, HAIR, round_=True)
        m.seg(pts[2], pts[3], 1.2, 1.2, T["white"], None)
    elif kind == "bear":
        m.rbox((-1.3, 0.2, z - 2.0), (1.3, 2.6, z + 0.3), f, HAIR, r=0.8)
    elif kind == "rabbit":
        m.rbox((-1.7, 0.0, z - 3.0), (1.7, 3.4, z + 0.3), T["white"], HAIR, r=1.2)
    elif kind == "demon":
        pts = [(0, 0.8, z), (0, -0.8, z - 2.8), (0, -3.2, z - 5.0), (0, -4.2, z - 7.6), (0, -3.4, z - 9.8)]
        for i in range(len(pts) - 1):
            w = 0.9 - i * 0.1
            m.seg(pts[i], pts[i + 1], w, w, T["skin"], SKIN, round_=True)
        tip = pts[-1]
        m.seg((tip[0], tip[1] - 1.0, tip[2]), (tip[0], tip[1] + 1.4, tip[2] - 1.0), 0.5, 2.2, T["bone"], HORN)
        m.seg((tip[0], tip[1], tip[2] + 0.2), (tip[0], tip[1] + 0.2, tip[2] - 2.0), 0.5, 2.4, T["bone"], HORN)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- limbs
#
# Upper arm frame: the shoulder joint at the origin, hanging along -Y to
# the elbow at -ua. Forearm frame: the elbow at the origin, the grip at -fa,
# fingers curled around +Z (the item points out of the fist along +Z).
# Thigh frame: hip joint at the origin, the knee at -th. Shin frame: the
# knee at the origin, the sole at -sh, toes toward +Z.


def uarm_base(b: dict) -> Model:
    m = Model()
    w, L = b["aw"], b["ua"]
    h = w / 2
    m.rbox((-h, -L - 0.6, -h), (h, 1.4, h), T["skin"], SKIN, r=w * 0.28)
    # Sleeve.
    m.rbox((-h - 0.2, -L * 0.55, -h - 0.2), (h + 0.2, 1.6, h + 0.2), T["cloth"], CLOTH, r=w * 0.3)
    m.box((-h - 0.25, -L * 0.55 - 0.1, -h - 0.25), (h + 0.25, -L * 0.55 + 0.5, h + 0.25), T["shade"], CLOTH)
    return m


def hand(m: Model, w: float, y: float, tex: str, tint: int):
    """A fist around the grip at height y (its center), knuckles forward."""
    h = w / 2
    m.rbox((-h, y - 1.0, -h - 0.1), (h, y + 1.3, h), tex, tint, r=0.4)
    # Fingers curled over the front, thumb on the side.
    for i in range(4):
        fx = -h + 0.15 + (w - 0.3) * (i + 0.5) / 4
        m.rbox((fx - w / 9, y - 0.9 + (0.15 if i in (1, 2) else 0), h - 0.2), (fx + w / 9, y + 0.3, h + 0.85), tex, tint, r=0.2)
    m.seg((h - 0.2, y + 0.9, -0.2), (h - 0.4, y - 0.4, h + 0.5), 0.9, 0.9, tex, tint, round_=True)


def farm_base(b: dict) -> Model:
    m = Model()
    w, L = b["aw"] * 0.92, b["fa"]
    h = w / 2
    m.rbox((-h, -L + 0.8, -h), (h, 1.0, h), T["skin"], SKIN, r=w * 0.3)
    hand(m, w * 0.95, -L, T["skin"], SKIN)
    return m


def thigh_base(b: dict) -> Model:
    m = Model()
    w, L = b["lw"], b["th"]
    h = w / 2
    m.rbox((-h, -L - 0.8, -h), (h, 0.8, h), T["cloth"], PANTS, r=w * 0.28)
    m.box((-h - 0.05, -L * 0.6, h - 0.1), (h + 0.05, -L * 0.6 + 0.3, h + 0.05), T["shade"], PANTS)
    return m


def foot(m: Model, w: float, L: float, tex: str, tint, sole: bool = True):
    h = w / 2
    m.rbox((-h - 0.25, -L, -h - 0.4), (h + 0.25, -L + 1.6, h + 2.0), tex, tint, r=0.5)
    if sole:
        m.box((-h - 0.3, -L - 0.05, -h - 0.45), (h + 0.3, -L + 0.35, h + 2.05), T["sole"])


def shin_base(b: dict) -> Model:
    m = Model()
    w, L = b["lw"] * 0.92, b["sh"]
    h = w / 2
    m.rbox((-h, -L * 0.45, -h), (h, 0.8, h), T["cloth"], PANTS, r=w * 0.28)
    # Boot with cuff and buckle strap.
    m.rbox((-h - 0.25, -L + 0.5, -h - 0.25), (h + 0.25, -L * 0.42, h + 0.25), T["boot"], None, r=0.4)
    m.rbox((-h - 0.45, -L * 0.48, -h - 0.45), (h + 0.45, -L * 0.48 + 1.0, h + 0.45), T["boot"], None, r=0.3)
    m.box((-h - 0.3, -L * 0.75, -h - 0.3), (h + 0.3, -L * 0.75 + 0.5, h + 0.3), T["belt"])
    m.box((h + 0.2, -L * 0.75 - 0.1, -0.4), (h + 0.4, -L * 0.75 + 0.6, 0.4), T["buckle"])
    foot(m, w, L, T["boot"], None)
    return m


def uarm_armor(kind: str, b: dict) -> Model:
    m = Model()
    w, L = b["aw"], b["ua"]
    h = w / 2 + 0.35
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def pauldron(tex, tint, lames, big=1.0):
        for i in range(lames):
            y = 1.8 - i * 1.35
            s = big * (1.0 - i * 0.12)
            m.rbox((-h - 0.9 * s, y - 1.5, -h - 0.7 * s), (h + 0.9 * s, y + 0.7, h + 0.7 * s), tex, tint, r=0.6)
            m.box((-h - 0.95 * s, y - 1.55, -h - 0.75 * s), (h + 0.95 * s, y - 1.25, h + 0.75 * s), tex, ARM_TRIM)

    if kind == "leather":
        m.rbox((-h, -L * 0.8, -h), (h, 1.6, h), lea, ARM_MAIN, r=0.6)
        m.rbox((-h - 0.4, 0.2, -h - 0.4), (h + 0.4, 2.2, h + 0.4), lea, ARM_TRIM, r=0.6)
    elif kind == "chain":
        m.rbox((-h, -L - 0.4, -h), (h, 1.8, h), T["chain"], ARM_MAIN, r=0.6)
    elif kind == "scale":
        m.rbox((-h, -L * 0.7, -h), (h, 1.5, h), lea, ARM_TRIM, r=0.5)
        pauldron(met, ARM_MAIN, 3)
    elif kind == "plate":
        m.rbox((-h, -L - 0.2, -h), (h, 0.5, h), met, ARM_MAIN, r=0.6)
        pauldron(met, ARM_MAIN, 3, 1.25)
    elif kind == "robe":
        m.rbox((-h - 0.2, -L - 0.4, -h - 0.2), (h + 0.2, 1.8, h + 0.2), clo, ARM_MAIN, r=0.7)
    elif kind == "ranger":
        m.rbox((-h, -L * 0.8, -h), (h, 1.6, h), clo, ARM_MAIN, r=0.6)
    elif kind == "noble":
        m.rbox((-h - 0.7, -L * 0.6, -h - 0.7), (h + 0.7, 1.8, h + 0.7), clo, ARM_MAIN, r=1.0)
        for i in range(3):
            x = -h + 0.6 + i * (2 * h - 1.2) / 2
            m.box((x - 0.2, -L * 0.6 + 0.2, h + 0.65), (x + 0.2, 1.6, h + 0.8), clo, ARM_TRIM)
    elif kind == "bone":
        m.rbox((-h, -L * 0.7, -h), (h, 1.5, h), lea, ARM_MAIN, r=0.5)
        for i in range(3):
            m.seg((0.5 * (i - 1), 2.0, 0.4 * (i - 1)), (0.8 * (i - 1) + 1.2, 4.2 - abs(i - 1) * 0.8, 0.6 * (i - 1) - 0.4), 0.8, 0.8, T["bone"], ARM_TRIM, round_=True)
    else:
        raise ValueError(kind)
    return m


def farm_armor(kind: str, b: dict) -> Model:
    m = Model()
    w, L = b["aw"] * 0.92, b["fa"]
    h = w / 2 + 0.3
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    if kind in ("leather", "ranger", "bone"):
        tex = lea
        m.rbox((-h, -L + 1.2, -h), (h, -0.4, h), tex, ARM_MAIN, r=0.5)
        for y in (-L * 0.25, -L * 0.55):
            m.box((-h - 0.08, y, -h - 0.08), (h + 0.08, y + 0.4, h + 0.08), lea, ARM_TRIM)
        if kind == "ranger":
            m.rbox((h - 0.2, -L + 1.4, -h), (h + 0.6, -0.6, h), lea, ARM_TRIM, r=0.2)
        if kind == "bone":
            m.seg((h, -L * 0.3, 0), (h + 1.5, -L * 0.1, -0.5), 0.6, 0.6, T["bone"], ARM_TRIM)
    elif kind == "chain":
        m.rbox((-h, -L + 0.8, -h), (h, 1.0, h), T["chain"], ARM_MAIN, r=0.5)
        hand(m, w * 1.05, -L, lea, ARM_TRIM)
    elif kind == "scale":
        m.rbox((-h, -L + 1.0, -h), (h, -0.2, h), met, ARM_MAIN, r=0.5)
        hand(m, w * 1.05, -L, lea, ARM_TRIM)
    elif kind == "plate":
        # Couter (elbow cop), vambrace, gauntlet.
        m.rbox((-h - 0.3, -0.9, -h - 0.4), (h + 0.3, 1.3, h + 0.2), met, ARM_MAIN, r=0.7)
        m.rbox((-h, -L + 1.0, -h), (h, -0.6, h), met, ARM_MAIN, r=0.6)
        m.box((-h - 0.05, -L + 1.0, -h - 0.05), (h + 0.05, -L + 1.4, h + 0.05), met, ARM_TRIM)
        hand(m, w * 1.12, -L, met, ARM_MAIN)
        m.rbox((-h - 0.35, -L + 0.4, -h - 0.35), (h + 0.35, -L + 1.6, h + 0.35), met, ARM_MAIN, r=0.4)
    elif kind == "robe":
        # A bell sleeve flaring past the wrist.
        m.seg((0, 1.0, 0), (0, -L + 1.2, 0.6), w + 0.8, w + 0.8, clo, ARM_MAIN, round_=True)
        m.seg((0, -L + 2.0, 0.4), (0, -L + 0.6, 1.2), w + 2.0, w + 2.0, clo, ARM_TRIM)
    elif kind == "noble":
        m.rbox((-h - 0.5, -L + 1.0, -h - 0.5), (h + 0.5, -L + 2.2, h + 0.5), T["white"], None, r=0.4)
        m.rbox((-h, -L + 2.0, -h), (h, 0.6, h), clo, ARM_MAIN, r=0.5)
    else:
        raise ValueError(kind)
    return m


def thigh_armor(kind: str, b: dict) -> Model:
    m = Model()
    w, L = b["lw"], b["th"]
    h = w / 2 + 0.35
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    if kind in ("leather", "ranger", "bone"):
        m.rbox((-h, -L, -h), (h, 0.4, h), lea, ARM_MAIN, r=0.6)
        if kind == "bone":
            m.rbox((-h - 0.3, -L * 0.4, -h - 0.3), (h + 0.3, 0.6, h + 0.3), T["fur"], ARM_TRIM, r=0.6)
    elif kind == "chain":
        m.rbox((-h, -L - 0.4, -h), (h, 0.4, h), T["chain"], ARM_MAIN, r=0.6)
    elif kind == "scale":
        for i in range(3):
            y = -i * L / 3
            m.seg((0, y + 0.4, h - 0.1), (0, y - L / 3 - 0.2, h + 0.4), 2 * h + 0.2, 0.5, met, ARM_MAIN)
        m.rbox((-h, -L, -h), (h, 0.4, h - 0.1), lea, ARM_TRIM, r=0.5)
    elif kind == "plate":
        m.rbox((-h, -L + 0.6, -h), (h, 0.4, h), met, ARM_MAIN, r=0.7)
        m.box((-h - 0.05, -L * 0.35, -h - 0.05), (h + 0.05, -L * 0.35 + 0.3, h + 0.05), met, ARM_TRIM)
    elif kind == "robe":
        pass
    elif kind == "noble":
        m.rbox((-h, -L * 0.55, -h), (h, 0.6, h), clo, ARM_MAIN, r=0.8)
        m.box((-h - 0.05, -L * 0.55, -h - 0.05), (h + 0.05, -L * 0.55 + 0.4, h + 0.05), clo, ARM_TRIM)
    else:
        raise ValueError(kind)
    if not m.elements:
        m.box((0, 0, 0), (0.01, 0.01, 0.01), T["dark"])
    return m


def shin_armor(kind: str, b: dict) -> Model:
    m = Model()
    w, L = b["lw"] * 0.92, b["sh"]
    h = w / 2 + 0.35
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    if kind in ("leather", "ranger", "noble"):
        m.rbox((-h, -L + 0.5, -h), (h, -0.4, h), lea, ARM_MAIN, r=0.6)
        m.rbox((-h - 0.3, -1.4, -h - 0.3), (h + 0.3, 0.0, h + 0.3), lea, ARM_TRIM, r=0.4)
        foot(m, w + 0.3, L, lea, ARM_MAIN)
    elif kind == "chain":
        m.rbox((-h, -L * 0.5, -h), (h, 0.6, h), T["chain"], ARM_MAIN, r=0.6)
        m.rbox((-h - 0.1, -L + 0.5, -h - 0.1), (h + 0.1, -L * 0.5, h + 0.1), lea, ARM_TRIM, r=0.5)
        foot(m, w + 0.3, L, lea, ARM_TRIM)
    elif kind == "scale":
        m.rbox((-h, -L + 0.6, -h), (h, 0.2, h), met, ARM_MAIN, r=0.6)
        foot(m, w + 0.3, L, lea, ARM_TRIM)
    elif kind == "plate":
        # Poleyn (knee cop), greave, sabaton lames.
        m.rbox((-h - 0.2, -1.4, -h + 0.2), (h + 0.2, 1.4, h + 0.9), met, ARM_MAIN, r=0.8)
        m.seg((0, -0.6, h + 0.7), (0, 0.6, h + 1.3), 0.6, 0.6, met, ARM_TRIM)
        m.rbox((-h, -L + 0.8, -h), (h, -0.8, h), met, ARM_MAIN, r=0.7)
        for i in range(3):
            z = h + 1.4 - i * 0.9
            m.rbox((-h - 0.3, -L - 0.05, z - 1.2), (h + 0.3, -L + 1.7 - i * 0.15, z), met, ARM_MAIN, r=0.45)
        m.rbox((-h - 0.3, -L - 0.05, -h - 0.5), (h + 0.3, -L + 1.8, h - 0.5), met, ARM_MAIN, r=0.45)
    elif kind == "robe":
        foot(m, w + 0.1, L, clo, ARM_MAIN)
    elif kind == "bone":
        m.rbox((-h, -L + 0.5, -h), (h, -0.4, h), T["fur"], ARM_MAIN, r=0.7)
        for y in (-L * 0.3, -L * 0.6):
            m.box((-h - 0.1, y, -h - 0.1), (h + 0.1, y + 0.4, h + 0.1), lea, ARM_TRIM)
        foot(m, w + 0.4, L, T["fur"], ARM_MAIN)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- write


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


PARTS = {
    # part: (base builder, armor builder, armor slot)
    "torso": (torso_base, torso_armor, "torso"),
    "uarm": (uarm_base, uarm_armor, "arm"),
    "farm": (farm_base, farm_armor, "arm"),
    "thigh": (thigh_base, thigh_armor, "leg"),
    "shin": (shin_base, shin_armor, "leg"),
}


def main() -> None:
    textures()
    n = lambda m, rel: model_node(m.save(rel))

    female_head = n(head_base(True), "body/head_f")
    head_layers = [select_node(0, {"f": female_head, "df": female_head}, n(head_base(), "body/head"))]
    head_layers.append(select_node(1, {k: n(helmet(k), f"body/helmet_{k}") for k in ARMORS}))
    head_layers.append(select_node(2, {k: n(hair(k), f"body/hair_{k}") for k in HAIRS}))
    head_layers.append(select_node(3, {k: n(ears(k), f"body/ears_{k}") for k in EARS}))
    head_layers.append(select_node(4, {k: n(beard(k), f"body/beard_{k}") for k in BEARDS}))
    write_item("body/head", composite(*head_layers))

    for part, (base_fn, armor_fn, _slot) in PARTS.items():
        cases = {}
        for bid, b in BUILDS.items():
            layers = [n(base_fn(b), f"body/{bid}/{part}"),
                      select_node(1, {k: n(armor_fn(k, b), f"body/{bid}/{part}_{k}") for k in ARMORS})]
            if part == "torso":
                layers.append(select_node(2, {k: n(tail(k, b), f"body/{bid}/tail_{k}") for k in TAILS}))
            cases[bid] = composite(*layers)
        write_item(f"body/{part}", select_node(0, cases, cases["m"]))

    # Inventory icons of armor pieces: the man's piece, posed for a slot.
    for slot, fns in (("head", [lambda k: helmet(k)]), ("torso", [lambda k: torso_armor(k, BUILDS["m"])]),
                      ("arm", [lambda k: uarm_armor(k, BUILDS["m"]), lambda k: farm_armor(k, BUILDS["m"])]),
                      ("leg", [lambda k: thigh_armor(k, BUILDS["m"]), lambda k: shin_armor(k, BUILDS["m"])])):
        cases = {}
        for k in ARMORS:
            m = fns[0](k)
            if len(fns) > 1:
                # Stack the lower piece under the upper one.
                low = fns[1](k)
                drop = BUILDS["m"]["ua"] if slot == "arm" else BUILDS["m"]["th"]
                for el in low.elements:
                    el = json.loads(json.dumps(el))
                    el["from"][1] -= drop
                    el["to"][1] -= drop
                    if "rotation" in el:
                        el["rotation"]["origin"][1] -= drop
                    m.elements.append(el)
                for key, tex in low.textures.items():
                    m.tex(tex)
                # Texture keys differ between the models: remap by id.
                remap = {f"#{key}": f"#{m.tex(tex)}" for key, tex in low.textures.items()}
                for el in m.elements[-len(low.elements):]:
                    for face in el["faces"].values():
                        face["texture"] = remap.get(face["texture"], face["texture"])
            m.display = fit_gui(m)
            cases[k] = model_node(m.save(f"icon/armor_{slot}_{k}"))
        write_item(f"armor/{slot}", select_node(0, cases, cases["leather"]))

    # Rig data for the plot code and the viewer.
    keys = ["hip", "hx", "neck", "sx", "sy", "ua", "fa", "th", "sh", "td"]
    lines = [
        "// Generated by pack/src/character.py: do not edit.",
        "// Rig joints per build in model pixels (1/16 block at scale 1), feet at y 0.",
        "",
        "/** Per build: [hipY, hipX, neckY, shoulderX, shoulderY, upperArm, foreArm,",
        " * thigh, shin, torsoDepth]. */",
        "declare global rigBuild: dict[list];",
        "",
        "function loadRigData {",
        "    global rigBuild = {};",
    ]
    for bid, b in BUILDS.items():
        b = dict(b, td=b["td"])
        lines.append(f"    global rigBuild[\"{bid}\"] = [{', '.join(fmt(b[k]) for k in keys)}];")
    lines += ["}", "",
              "/** Option lists for the character designer. */",
              "function rigOptions(kind: str): list[str] {"]
    for kind, vals in (("armor", ARMORS), ("hair", HAIRS), ("ears", EARS), ("beard", BEARDS), ("tail", TAILS)):
        lines.append(f"    if (kind == \"{kind}\") {{ return [{', '.join(json.dumps(v) for v in vals)}]; }}")
    lines += ["    return [];", "}", ""]
    (ROOT / "tc/rig_data.tc").write_text("\n".join(lines))
    view = ROOT / "tools/viewer/rig_data.json"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(json.dumps({"builds": {bid: {k: b[k] for k in keys} for bid, b in BUILDS.items()},
                                "armors": ARMORS, "hairs": HAIRS, "ears": EARS, "beards": BEARDS, "tails": TAILS}, indent=1))
    print(f"character: {len(BUILDS)} builds, {len(ARMORS)} armors, {len(HAIRS)} hair, {len(EARS)} ears, "
          f"{len(BEARDS)} beards, {len(TAILS)} tails")


if __name__ == "__main__":
    main()
