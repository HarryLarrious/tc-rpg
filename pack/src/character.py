#!/usr/bin/env python3
"""The character rig: body parts, clothes, armor, hair, ears, beards, tails.

The look is stylized and blocky: one-piece arms and legs, a big square head,
a cartoon face (no nose) and flat, paper-thin ears. Every character is six
item displays: head, torso, two arms, two legs. Each part's item model
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

Writes pack/assets/rpg/{models,items,textures}, tc/rig_data.tc and
tools/viewer/rig_data.json.
"""

from __future__ import annotations

import json
import shutil

from common import (ASSETS, ROOT, Model, composite, fit_gui, make_texture, model_node, select_node, write_item)

SKIN, HAIR, EYE, CLOTH, ARM_MAIN, ARM_TRIM, HORN, PANTS = range(8)

# Per build, in model pixels (16 per block at scale 1; feet at y 0):
#   hip      height of the hip joints; hx: their x
#   tw/td    torso width and depth; neck: height of the torso's top
#   sx/sy    shoulder joint x and height (the arm's top is 2 px above it)
#   aw/al    arm thickness and length; grip: shoulder to the hand's center
#   lw/ll    leg thickness and length (hip joint to the sole)
BUILDS = {
    "m": dict(hip=11, hx=2.0, tw=8, td=4.5, neck=22, sx=6.0, sy=20, aw=4.0, al=11, lw=4.0, ll=11, bust=False),
    "f": dict(hip=11, hx=1.8, tw=7, td=4.0, neck=22, sx=5.25, sy=20, aw=3.5, al=11, lw=3.6, ll=11, bust=True),
    "dm": dict(hip=7, hx=2.5, tw=10, td=6.0, neck=17, sx=7.0, sy=15, aw=4.0, al=9, lw=5.0, ll=7, bust=False),
    "df": dict(hip=7, hx=2.25, tw=9, td=5.5, neck=17, sx=6.25, sy=15, aw=3.5, al=9, lw=4.5, ll=7, bust=True),
}
for _b in BUILDS.values():
    _b["grip"] = _b["al"] - 3.5

ARMORS = ["leather", "chain", "scale", "plate", "robe", "ranger", "noble", "bone"]
HAIRS = ["short", "long", "ponytail", "braid", "bun", "mohawk", "curly", "spiky", "bob", "shaggy"]
EARS = ["human", "elf", "cat", "wolf", "bear", "rabbit", "demon"]
BEARDS = ["stubble", "short", "full", "long", "braided", "goatee", "mustache"]
TAILS = ["cat", "wolf", "bear", "rabbit", "demon"]

# The head: x -HX..HX, y 0..HY (the neck joint at the origin), z -HZ..HZ,
# the face on +Z.
HX, HY, HZ = 4.5, 8.5, 4.25
FRONT = ("south",)  # decals only need the face toward +Z
FLAT = 0.15  # thickness of the flat (2D) ears

T: dict[str, str] = {}


def textures():
    for kind in ("skin", "cloth", "leather", "metal", "chain", "hair", "fur", "dark", "white", "bone"):
        T[kind] = make_texture(f"body_{kind}", kind)
    T["mouth"] = make_texture("body_mouth", "dark", rgb=(120, 52, 52))
    T["blush"] = make_texture("body_blush", "skin", rgb=(255, 176, 176))
    T["boot"] = make_texture("body_boot", "leather", rgb=(104, 70, 44))
    T["sole"] = make_texture("body_sole", "leather", rgb=(52, 38, 28))
    T["belt"] = make_texture("body_belt", "leather", rgb=(70, 48, 30))
    T["buckle"] = make_texture("body_buckle", "metal", rgb=(232, 196, 96))
    T["brow"] = make_texture("body_brow", "hair", rgb=(200, 200, 200))
    T["shade"] = make_texture("body_shade", "skin", rgb=(206, 206, 206))
    T["inner"] = make_texture("body_inner", "skin", rgb=(255, 186, 196))


def xs(side: float, a: float, b: float) -> tuple[float, float]:
    """The x range side*a..side*b, low to high."""
    return tuple(sorted((side * a, side * b)))


# ---------------------------------------------------------------- head


def head_base(female: bool = False) -> Model:
    m = Model()
    s = T["skin"]
    m.box((-HX, 0, -HZ), (HX, HY, HZ), s, SKIN)
    m.box((-1.8, -1.5, -1.6), (1.8, 0.2, 1.6), s, SKIN)
    z = HZ
    for side in (1, -1):
        # Eyes: a tall colored iris, a dark pupil and a glint (the glint on
        # the same side of both eyes, as if lit from one side).
        x0, x1 = xs(side, 0.9, 2.8)
        m.box((x0, 3.1, z), (x1, 5.6, z + 0.05), T["white"], EYE, faces=FRONT)
        p0, p1 = xs(side, 1.4, 2.3)
        m.box((p0, 3.3, z + 0.05), (p1, 4.9, z + 0.08), T["dark"], faces=FRONT)
        gx = side * 1.85
        m.box((gx - 0.05, 4.6, z + 0.08), (gx + 0.55, 5.2, z + 0.1), T["white"], faces=FRONT)
        # Brows (hair colored), arched on the female face.
        b0, b1 = xs(side, 0.8, 3.0)
        tilt = side * (7 if female else -5)
        m.box((b0, 6.05, z), (b1, 6.6, z + 0.09), T["brow"], HAIR, faces=FRONT,
              rot=("z", tilt, (side * 1.9, 6.3, z)))
        if female:
            l0, l1 = xs(side, 0.8, 3.15)
            m.box((l0, 5.35, z + 0.08), (l1, 5.75, z + 0.11), T["dark"], faces=FRONT)
            k0, k1 = xs(side, 2.95, 3.5)
            m.box((k0, 5.55, z + 0.08), (k1, 6.0, z + 0.11), T["dark"], faces=FRONT)
            c0, c1 = xs(side, 2.7, 4.0)
            m.box((c0, 2.5, z), (c1, 3.1, z + 0.03), T["blush"], SKIN, faces=FRONT)
    # A small smile.
    m.box((-0.9, 1.6, z), (0.9, 2.0, z + 0.06), T["mouth"], faces=FRONT)
    for side in (1, -1):
        c0, c1 = xs(side, 0.9, 1.35)
        m.box((c0, 1.9, z), (c1, 2.35, z + 0.06), T["mouth"], faces=FRONT)
    return m


def cap(m: Model, y0: float = 6.6, top: float = 9.4, out: float = 0.45):
    m.box((-HX - out, y0, -HZ - out), (HX + out, top, HZ + out), T["hair"], HAIR)


def back(m: Model, y0: float, out: float = 0.5, thick: float = 1.4):
    m.box((-HX - out, y0, -HZ - out), (HX + out, 9.0, -HZ + thick), T["hair"], HAIR)


def sides(m: Model, y0: float, front: float = 1.6, out: float = 0.45):
    for side in (1, -1):
        x0, x1 = xs(side, HX - 0.4, HX + out)
        m.box((x0, y0, -HZ - 0.45), (x1, 9.0, front), T["hair"], HAIR)


def fringe(m: Model, cols, tilt: float = 0.0):
    """Bangs over the forehead: cols of (x0, x1, bottom y)."""
    for x0, x1, yb in cols:
        rot = ("z", tilt, ((x0 + x1) / 2, 9.0, HZ)) if tilt else None
        m.box((x0, yb, HZ - 0.3), (x1, 9.3, HZ + 0.7), T["hair"], HAIR, rot=rot)


def hair(style: str) -> Model:
    m = Model()
    h = T["hair"]
    W = HX + 0.45
    if style == "short":
        cap(m)
        back(m, 4.2)
        sides(m, 5.4)
        fringe(m, [(-W, -1.5, 6.1), (-1.5, 1.8, 6.6), (1.8, W, 7.1)])
        m.seg((0.8, 9.0, 2.6), (2.2, 10.5, 3.7), 2.8, 2.0, h, HAIR)
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.3, W)
            m.box((x0, 4.0, 0.4), (x1, 5.6, 1.6), h, HAIR)
    elif style == "long":
        cap(m)
        back(m, -5.0, thick=1.8)
        sides(m, -2.5, front=0.8)
        fringe(m, [(-W, -0.35, 6.3), (0.35, W, 6.3)])
        for side in (1, -1):
            x0, x1 = xs(side, 3.2, W)
            m.box((x0, -1.2, 2.2), (x1, 7.0, HZ + 0.5), h, HAIR)
        m.box((-3.0, -6.2, -HZ - 0.3), (3.0, -4.8, -HZ + 1.3), h, HAIR)
    elif style == "ponytail":
        cap(m)
        back(m, 4.5)
        sides(m, 5.6)
        fringe(m, [(-W, -1.0, 6.7), (-1.0, 2.5, 6.2), (2.5, W, 5.7)])
        m.box((-1.3, 6.2, -HZ - 1.1), (1.3, 7.8, -HZ - 0.3), T["belt"])
        m.seg((0, 7.0, -5.1), (0, 4.4, -7.3), 2.8, 2.6, h, HAIR)
        m.seg((0, 4.7, -7.2), (0, 0.4, -7.6), 2.6, 2.4, h, HAIR)
        m.seg((0, 0.8, -7.5), (0, -3.0, -6.8), 2.0, 1.8, h, HAIR)
    elif style == "braid":
        cap(m)
        back(m, 3.5)
        sides(m, 5.0)
        fringe(m, [(-W, 0.4, 6.4), (0.4, W, 6.9)])
        y = 3.8
        for i in range(5):
            off = 0.4 if i % 2 else -0.4
            m.box((off - 1.1, y - 1.9, -HZ - 1.2), (off + 1.1, y, -HZ + 0.3), h, HAIR)
            y -= 1.6
        m.box((-0.9, y - 0.8, -HZ - 1.0), (0.9, y + 0.3, -HZ + 0.1), T["belt"])
        m.box((-1.1, y - 2.4, -HZ - 1.1), (1.1, y - 0.8, -HZ + 0.2), h, HAIR)
    elif style == "bun":
        cap(m)
        back(m, 4.5)
        sides(m, 5.6)
        fringe(m, [(-W, W, 7.0)])
        m.box((-2.2, 8.2, -5.8), (2.2, 12.2, -1.8), h, HAIR, rot=("y", 45, (0, 10, -3.8)))
        m.box((-2.5, 8.6, -4.6), (2.5, 9.4, -3.0), T["belt"])
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.2, W)
            m.box((x0, 2.6, 2.4), (x1, 7.0, 3.6), h, HAIR)
    elif style == "mohawk":
        for i in range(5):
            z = 3.4 - i * 1.9
            m.seg((0, 8.0, z), (0, 11.8 - abs(i - 1.5) * 0.45, z - 1.3), 1.8, 1.9, h, HAIR)
        m.box((-0.9, 4.6, -HZ - 0.4), (0.9, 8.8, -HZ + 0.8), h, HAIR)
    elif style == "curly":
        cap(m, y0=6.0, top=9.8, out=0.7)
        back(m, 2.6, out=0.8)
        puffs = [(-2.6, 10.0, 1.4), (1.8, 10.2, -0.6), (-0.8, 10.0, -3.0), (0.6, 10.3, 2.6),
                 (-3.6, 8.7, 4.2), (0.2, 9.1, 4.6), (3.6, 8.5, 4.2),
                 (5.1, 7.0, 0.8), (-5.1, 7.0, 0.8), (5.0, 5.0, -2.2), (-5.0, 5.0, -2.2),
                 (-2.3, 4.2, -5.1), (2.3, 3.4, -5.1), (0.0, 7.4, -5.3)]
        for i, (x, y, zz) in enumerate(puffs):
            c = 1.8 if i % 3 else 2.0
            m.box((x - c, y - c, zz - c), (x + c, y + c, zz + c), h, HAIR,
                  rot=("y", 45, (x, y, zz)) if i % 2 else None)
    elif style == "spiky":
        cap(m)
        back(m, 4.5)
        sides(m, 5.6)
        for (x, zz, tx, ty, tz) in [(-2.4, 1.6, -5.0, 12.2, 2.4), (0.0, 1.8, 0.4, 12.8, 3.0), (2.4, 1.4, 5.0, 12.0, 2.2),
                                    (-2.6, -1.8, -5.4, 11.6, -3.4), (0.2, -2.0, 0.4, 12.4, -4.2),
                                    (2.6, -1.6, 5.4, 11.4, -3.2)]:
            m.seg((x, 8.8, zz), (tx, ty, tz), 2.6, 2.6, h, HAIR, twist=45)
        for x in (-3.0, 0.0, 3.0):
            m.seg((x, 9.2, HZ - 0.1), (x + 0.6, 6.2, HZ + 0.9), 2.6, 0.9, h, HAIR)
    elif style == "bob":
        cap(m)
        back(m, 1.0, out=0.7, thick=1.6)
        sides(m, 1.0, front=2.8, out=0.7)
        fringe(m, [(-W, W, 6.4)])
    elif style == "shaggy":
        cap(m)
        for i, yb in enumerate((1.5, 3.0, 0.4, 2.4, 1.2)):
            x0 = -HX - 0.5 + i * (2 * HX + 1) / 5
            m.box((x0, yb, -HZ - 0.5), (x0 + (2 * HX + 1) / 5, 9.0, -HZ + 1.4), h, HAIR)
        for side in (1, -1):
            for j, (zz, yb) in enumerate(((-HZ - 0.45, 2.2), (-1.4, 3.4), (0.4, 4.8))):
                x0, x1 = xs(side, HX - 0.4, HX + 0.5)
                m.box((x0, yb, zz), (x1, 9.0, zz + 1.9), h, HAIR)
        for k, (x0, x1, yb, tilt) in enumerate(((-W, -2.2, 5.6, -8), (-2.2, 0.0, 6.6, 6), (0.0, 2.4, 5.9, -6), (2.4, W, 6.8, 8))):
            fringe(m, [(x0, x1, yb)], tilt=tilt)
    else:
        raise ValueError(style)
    return m


def flat(m: Model, x0, x1, y0, y1, z, tex, tint, rot=None, dz: float = 0.0):
    """A paper-thin plane facing forward (a 2D cut out)."""
    m.box((x0, y0, z + dz - FLAT / 2), (x1, y1, z + dz + FLAT / 2), tex, tint, rot=rot)


def ears(kind: str) -> Model:
    m = Model()
    s, f, inner = T["skin"], T["fur"], T["inner"]
    if kind == "human":
        for side in (1, -1):
            rot = ("xyz", (0, side * 32, 0), (side * HX, 3.9, -0.4))
            flat(m, *xs(side, HX - 0.2, HX + 1.3), 2.8, 5.1, -0.4, s, SKIN, rot)
            flat(m, *xs(side, HX + 0.25, HX + 0.95), 3.3, 4.6, -0.4, T["shade"], SKIN, rot, dz=0.12)
    elif kind in ("elf", "demon"):
        for side in (1, -1):
            rot = ("xyz", (0, side * 28, side * 22), (side * HX, 4.0, -0.4))
            flat(m, *xs(side, HX - 0.2, HX + 2.0), 3.2, 5.2, -0.4, s, SKIN, rot)
            flat(m, *xs(side, HX + 1.9, HX + 3.4), 4.0, 5.5, -0.4, s, SKIN, rot)
            flat(m, *xs(side, HX + 3.3, HX + 4.4), 4.6, 5.6, -0.4, s, SKIN, rot)
            flat(m, *xs(side, HX + 0.4, HX + 2.6), 3.7, 4.8, -0.4, T["shade"], SKIN, rot, dz=0.12)
        if kind == "demon":
            for side in (1, -1):
                pts = [(side * 2.4, 8.2, 0.8), (side * 3.4, 10.4, 0.0), (side * 4.6, 11.6, -1.6), (side * 5.0, 11.4, -3.6)]
                for i in range(len(pts) - 1):
                    w = 2.0 - i * 0.5
                    m.seg(pts[i], pts[i + 1], w, w, T["bone"], HORN)
    elif kind == "cat":
        for side in (1, -1):
            c = (side * 2.5, 8.9, -0.6)
            rot = ("xyz", (0, 0, 45), c)
            flat(m, c[0] - 1.8, c[0] + 1.8, c[1] - 1.8, c[1] + 1.8, c[2], f, HAIR, rot)
            flat(m, c[0] - 1.0, c[0] + 1.0, c[1] - 0.4, c[1] + 1.6, c[2], inner, SKIN, ("xyz", (0, 0, 45), c), dz=0.12)
    elif kind == "wolf":
        for side in (1, -1):
            bx = side * 2.6
            rot = ("xyz", (0, 0, side * -10), (bx, 8.4, -0.6))
            for i, (w, hgt) in enumerate(((3.6, 1.5), (2.6, 1.4), (1.6, 1.3), (0.7, 1.0))):
                y0 = 8.4 + sum(t[1] for t in ((3.6, 1.5), (2.6, 1.4), (1.6, 1.3))[:i])
                flat(m, bx - w / 2, bx + w / 2, y0, y0 + hgt, -0.6, f, HAIR, rot)
            flat(m, bx - 1.0, bx + 1.0, 9.0, 11.6, -0.6, inner, SKIN, rot, dz=0.12)
    elif kind == "bear":
        for side in (1, -1):
            c = (side * 3.3, 9.0)
            flat(m, c[0] - 1.6, c[0] + 1.6, c[1] - 1.1, c[1] + 1.1, -0.6, f, HAIR)
            flat(m, c[0] - 1.1, c[0] + 1.1, c[1] - 1.6, c[1] + 1.6, -0.6, f, HAIR, dz=0.01)
            flat(m, c[0] - 0.8, c[0] + 0.8, c[1] - 0.8, c[1] + 0.8, -0.6, inner, SKIN, dz=0.12)
    elif kind == "rabbit":
        for side in (1, -1):
            x = side * 1.9
            rot = ("xyz", (-8, 0, side * -12), (x, 8.2, -0.6))
            flat(m, x - 1.2, x + 1.2, 8.0, 15.8, -0.6, f, HAIR, rot)
            flat(m, x - 0.6, x + 0.6, 9.0, 15.0, -0.6, inner, SKIN, rot, dz=0.12)
    else:
        raise ValueError(kind)
    return m


def beard(kind: str) -> Model:
    m = Model()
    h = T["hair"]
    z = HZ

    def mustache(y=2.2):
        m.box((-2.4, y, z - 0.2), (2.4, y + 0.9, z + 0.6), h, HAIR)
        for side in (1, -1):
            x0, x1 = xs(side, 1.8, 2.7)
            m.box((x0, y - 1.0, z - 0.2), (x1, y + 0.4, z + 0.55), h, HAIR)

    if kind == "stubble":
        m.box((-HX, 0, z - 0.4), (HX, 2.6, z + 0.03), T["shade"], HAIR, faces=FRONT)
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.1, HX + 0.03)
            m.box((x0, 0, -1.5), (x1, 3.6, z), T["shade"], HAIR)
    elif kind == "mustache":
        mustache()
    elif kind == "goatee":
        m.box((-1.3, -1.6, z - 0.6), (1.3, 1.4, z + 0.5), h, HAIR)
        mustache()
    else:
        drop = {"short": 1.6, "full": 3.2, "long": 3.2, "braided": 3.2}[kind]
        m.box((-HX - 0.3, -drop, 0.6), (HX + 0.3, 2.2, z + 0.6), h, HAIR)
        mustache()
        if kind == "long":
            m.box((-3.0, -drop - 4.2, 1.6), (3.0, -drop + 0.2, z + 0.4), h, HAIR)
            m.box((-1.6, -drop - 6.0, 2.2), (1.6, -drop - 4.0, z + 0.1), h, HAIR)
        elif kind == "braided":
            for side in (1, -1):
                y = -drop
                for i in range(3):
                    x = side * 1.8 + (0.3 if i % 2 else -0.3)
                    m.box((x - 0.9, y - 1.8, 2.2), (x + 0.9, y + 0.2, z + 0.2), h, HAIR)
                    y -= 1.6
                m.box((side * 1.8 - 0.7, y - 0.6, 2.4), (side * 1.8 + 0.7, y + 0.4, z), T["buckle"])
    return m


def helmet(kind: str) -> Model:
    m = Model()
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    O = 0.5
    X, Z = HX + O, HZ + O

    def shell(tex, tint, y0=0.0, top=9.6, closed=False):
        m.box((-X, 6.0, -Z), (X, top, Z), tex, tint)
        m.box((-X, y0, -Z), (X, 6.0, -HZ + 0.8), tex, tint)
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.3, X)
            m.box((x0, y0, -Z), (x1, 6.0, Z if closed else 3.4), tex, tint)
        if closed:
            m.box((-X, y0, HZ), (X, 6.0, Z), tex, tint)
            m.box((-3.6, 4.0, Z), (3.6, 4.9, Z + 0.05), T["dark"], faces=FRONT)
            for x in (-2.4, -1.2, 0, 1.2, 2.4):
                m.box((x - 0.2, 1.0, Z), (x + 0.2, 3.0, Z + 0.05), T["dark"], faces=FRONT)

    if kind == "leather":
        m.box((-X + 0.1, 6.0, -Z + 0.1), (X - 0.1, 9.4, Z - 0.1), lea, ARM_MAIN)
        m.box((-X - 0.1, 6.0, -Z - 0.1), (X + 0.1, 6.9, Z + 0.1), lea, ARM_TRIM)
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.2, X)
            m.box((x0, 2.4, -1.8), (x1, 6.0, 1.4), lea, ARM_MAIN)
    elif kind == "chain":
        shell(T["chain"], ARM_MAIN, y0=-0.6)
        m.box((-4.2, -1.8, -4.2), (4.2, 0.2, 3.6), T["chain"], ARM_MAIN)
        m.box((-X - 0.1, 6.0, -Z - 0.1), (X + 0.1, 6.7, Z + 0.1), lea, ARM_TRIM)
    elif kind == "scale":
        shell(met, ARM_MAIN)
        m.box((-X - 0.3, 5.6, -Z - 0.3), (X + 0.3, 6.4, Z + 0.9), met, ARM_TRIM)
        m.box((-0.45, 9.4, -4.0), (0.45, 10.5, 4.0), met, ARM_TRIM)
    elif kind == "plate":
        shell(met, ARM_MAIN, top=9.8, closed=True)
        m.box((-0.5, 9.6, -4.4), (0.5, 10.6, 4.4), met, ARM_TRIM)
        for i in range(4):
            m.seg((0, 10.4, 2.4 - i * 1.8), (0, 12.6 - abs(i - 1) * 0.5, 0.6 - i * 2.3), 1.0, 1.8, clo, ARM_TRIM)
    elif kind == "robe":
        # A floppy pointed wizard hat.
        m.box((-6.8, 7.6, -6.8), (6.8, 8.4, 6.8), clo, ARM_MAIN)
        m.box((-4.7, 8.4, -4.7), (4.7, 10.6, 4.7), clo, ARM_MAIN)
        m.box((-4.8, 8.4, -4.8), (4.8, 9.4, 4.8), clo, ARM_TRIM)
        m.seg((0, 10.4, 0), (0, 13.0, -0.8), 6.6, 6.6, clo, ARM_MAIN)
        m.seg((0, 12.8, -0.8), (0, 15.0, -2.4), 4.6, 4.6, clo, ARM_MAIN)
        m.seg((0, 14.8, -2.3), (0, 16.2, -4.6), 2.8, 2.8, clo, ARM_MAIN)
        m.seg((0, 16.0, -4.4), (0, 15.6, -6.6), 1.6, 1.6, clo, ARM_TRIM)
    elif kind == "ranger":
        m.box((-X - 0.1, 6.4, -Z - 0.1), (X + 0.1, 9.9, Z + 0.1), clo, ARM_MAIN)
        m.box((-X - 0.1, -0.4, -Z - 0.1), (X + 0.1, 6.4, -HZ + 0.9), clo, ARM_MAIN)
        for side in (1, -1):
            x0, x1 = xs(side, HX - 0.3, X + 0.1)
            m.box((x0, -0.4, -Z - 0.1), (x1, 6.4, 3.8), clo, ARM_MAIN)
        m.seg((0, 8.6, -4.8), (0, 5.2, -7.6), 3.4, 1.6, clo, ARM_MAIN)
        m.box((-4.8, -1.8, -4.6), (4.8, 0.4, 3.8), clo, ARM_MAIN)
        m.box((-X - 0.15, 6.4, Z - 0.6), (X + 0.15, 7.2, Z + 0.2), clo, ARM_TRIM)
    elif kind == "noble":
        m.box((-4.7, 8.2, -4.5), (4.7, 9.8, 4.5), met, ARM_TRIM)
        for x, zz in ((0, 4.0), (-4.2, 0), (4.2, 0), (0, -4.0), (-3.0, 3.0), (3.0, 3.0), (-3.0, -3.0), (3.0, -3.0)):
            m.box((x - 0.6, 9.8, zz - 0.6), (x + 0.6, 11.2 if x == 0 else 10.8, zz + 0.6), met, ARM_TRIM)
        m.box((-0.7, 8.6, 4.5), (0.7, 9.6, 4.8), T["white"], ARM_MAIN)
    elif kind == "bone":
        shell(T["bone"], ARM_MAIN, top=9.8)
        for side in (1, -1):
            pts = [(side * 4.6, 7.6, 0.4), (side * 6.6, 9.4, 0.0), (side * 7.4, 12.0, -0.8)]
            for i in range(2):
                w = 1.8 - i * 0.6
                m.seg(pts[i], pts[i + 1], w, w, T["bone"], ARM_TRIM)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- torso
#
# Torso frame: the hips' center at the origin, the top at neck - hip.


def torso_base(b: dict) -> Model:
    m = Model()
    H = b["neck"] - b["hip"]
    hw, hd = b["tw"] / 2, b["td"] / 2
    c = T["cloth"]
    m.box((-hw, 2.4, -hd), (hw, H, hd), c, CLOTH)
    m.box((-hw + 0.05, -0.6, -hd + 0.05), (hw - 0.05, 2.5, hd - 0.05), c, PANTS)
    # Belt and buckle, an open collar.
    m.box((-hw - 0.15, 2.0, -hd - 0.15), (hw + 0.15, 3.0, hd + 0.15), T["belt"])
    m.box((-0.7, 1.9, hd + 0.1), (0.7, 3.1, hd + 0.35), T["buckle"])
    m.box((-1.5, H - 1.4, hd), (1.5, H, hd + 0.04), T["skin"], SKIN, faces=FRONT)
    m.box((-0.6, H - 2.3, hd), (0.6, H - 1.4, hd + 0.04), T["skin"], SKIN, faces=FRONT)
    if b["bust"]:
        m.box((-hw + 0.6, H - 5.4, hd - 0.2), (hw - 0.6, H - 2.4, hd + 0.9), c, CLOTH)
    return m


def torso_armor(kind: str, b: dict) -> Model:
    m = Model()
    H = b["neck"] - b["hip"]
    hw, hd = b["tw"] / 2 + 0.4, b["td"] / 2 + 0.4
    bust = b["bust"]
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def shell(tex, tint, y0=0.5, y1=H + 0.2):
        m.box((-hw, y0, -hd), (hw, y1, hd), tex, tint)
        if bust:
            m.box((-hw + 0.7, H - 5.6, hd - 0.2), (hw - 0.7, H - 2.2, hd + 0.9), tex, tint)

    def belt(tex, tint):
        m.box((-hw - 0.1, 1.8, -hd - 0.1), (hw + 0.1, 3.0, hd + 0.1), tex, tint)

    if kind == "leather":
        shell(lea, ARM_MAIN, 1.0)
        belt(lea, ARM_TRIM)
        for side in (1, -1):
            x0, x1 = xs(side, 1.4, 1.9)
            m.box((x0, 3.0, hd), (x1, H, hd + 0.15), lea, ARM_TRIM)
    elif kind == "chain":
        shell(T["chain"], ARM_MAIN, -2.0)
        belt(lea, ARM_TRIM)
    elif kind == "scale":
        shell(met, ARM_MAIN, -1.5)
        for i in range(4):
            y = H - 1 - i * 2.4
            m.box((-hw - 0.1, y - 0.6, hd), (hw + 0.1, y, hd + 0.2), met, ARM_TRIM)
            m.box((-hw - 0.1, y - 0.6, -hd - 0.2), (hw + 0.1, y, -hd), met, ARM_TRIM)
    elif kind == "plate":
        shell(met, ARM_MAIN, 2.0)
        m.box((-hw + 0.6, 4.0, hd), (hw - 0.6, H - 1.0, hd + 0.8), met, ARM_MAIN)
        m.box((-0.3, 4.0, hd + 0.8), (0.3, H - 1.0, hd + 1.0), met, ARM_TRIM)
        m.box((-hw - 0.2, 0.0, -hd - 0.2), (hw + 0.2, 2.2, hd + 0.2), met, ARM_TRIM)
        m.box((-hw, -3.0, -hd), (hw, 0.0, hd), T["chain"], ARM_MAIN)
        m.box((-3.2, H - 0.6, -hd + 0.2), (3.2, H + 1.2, hd - 0.2), met, ARM_MAIN)
    elif kind == "robe":
        shell(clo, ARM_MAIN, -1.0)
        m.box((-hw - 0.4, -9.5, -hd - 0.4), (hw + 0.4, 0.0, hd + 0.4), clo, ARM_MAIN)
        m.box((-1.0, -9.5, hd + 0.4), (1.0, H, hd + 0.55), clo, ARM_TRIM)
        m.box((-hw - 0.5, 1.8, -hd - 0.5), (hw + 0.5, 2.8, hd + 0.5), clo, ARM_TRIM)
        m.box((-3.0, H - 1.0, -hd - 0.3), (3.0, H + 0.6, hd + 0.3), clo, ARM_TRIM)
    elif kind == "ranger":
        shell(lea, PANTS, 0.5)
        # Cloak: a mantle over the shoulders and a cape down the back.
        m.box((-hw - 0.4, H - 2.0, -hd - 0.5), (hw + 0.4, H + 0.6, hd + 0.5), clo, ARM_MAIN)
        m.seg((0, H, -hd - 0.5), (0, -6.0, -hd - 2.0), 2 * hw + 0.6, 0.5, clo, ARM_MAIN)
        m.seg((hw - 1.2, H - 0.5, hd + 0.1), (-hw + 1.2, 0.8, hd + 0.3), 1.0, 0.5, lea, ARM_TRIM)
    elif kind == "noble":
        shell(clo, ARM_MAIN, -2.0)
        m.seg((0, H, -hd - 0.4), (0, -8.0, -hd - 2.2), 2 * hw + 1.2, 0.5, clo, ARM_TRIM)
        m.box((-hw - 0.4, H - 1.2, -hd - 0.4), (hw + 0.4, H + 0.6, hd + 0.4), T["white"])
        for y in (3.0, 5.5, 8.0):
            m.box((-0.4, y, hd), (0.4, y + 0.8, hd + 0.2), met, ARM_TRIM)
    elif kind == "bone":
        shell(lea, ARM_MAIN, 1.0)
        for i in range(4):
            y = H - 2.5 - i * 2.2
            m.box((-hw + 0.5, y, hd), (hw - 0.5, y + 0.8, hd + 0.4), T["bone"], ARM_TRIM)
        for side in (1, -1):
            m.seg((side * (hw - 1.0), H, 0), (side * (hw + 1.4), H + 2.4, -0.4), 1.3, 1.3, T["bone"], ARM_TRIM)
    else:
        raise ValueError(kind)
    return m


def tail(kind: str, b: dict) -> Model:
    m = Model()
    z = -b["td"] / 2 + 0.3
    f = T["fur"]

    def chain(pts, widths, tex=f, tint=HAIR):
        for i in range(len(pts) - 1):
            m.seg(pts[i], pts[i + 1], widths[i], widths[i], tex, tint)

    if kind == "cat":
        chain([(0, 1.2, z), (0, 0.6, z - 3.0), (0.4, 1.6, z - 6.0), (0.8, 4.4, z - 7.6), (0.4, 6.8, z - 7.4)], [1.6] * 4)
    elif kind == "wolf":
        chain([(0, 1.4, z), (0, -0.4, z - 3.0), (0, -3.0, z - 5.0), (0, -5.2, z - 5.6)], [2.2, 3.2, 2.4])
        m.seg((0, -3.6, z - 5.2), (0, -5.6, z - 5.7), 1.6, 1.6, T["white"], None)
    elif kind == "bear":
        m.box((-1.4, 0.6, z - 2.2), (1.4, 3.0, z + 0.3), f, HAIR)
    elif kind == "rabbit":
        m.box((-1.8, 0.4, z - 3.2), (1.8, 3.8, z + 0.3), T["white"], HAIR, rot=("y", 45, (0, 2.1, z - 1.4)))
    elif kind == "demon":
        chain([(0, 1.0, z), (0, -0.8, z - 3.0), (0, -3.2, z - 5.2), (0, -4.0, z - 8.0)], [1.0, 0.9, 0.8], T["skin"], SKIN)
        tip = (0, -4.0, z - 8.6)
        m.box((-0.3, tip[1] - 1.3, tip[2] - 1.3), (0.3, tip[1] + 1.3, tip[2] + 1.3), T["bone"], HORN,
              rot=("x", 45, tip))
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- limbs
#
# Arm frame: the shoulder joint at the origin, the arm's top 2 px above it,
# hanging along -Y; the hand is the bottom 3 px and a held item sits at
# -grip. Leg frame: the hip joint at the origin, the sole at -ll, toes
# toward +Z.


def arm_base(b: dict) -> Model:
    m = Model()
    h, low = b["aw"] / 2, 2 - b["al"]
    m.box((-h, low, -h), (h, 2, h), T["skin"], SKIN)
    m.box((-h - 0.25, -3.6, -h - 0.25), (h + 0.25, 2.25, h + 0.25), T["cloth"], CLOTH)
    return m


def arm_armor(kind: str, b: dict) -> Model:
    m = Model()
    h, low = b["aw"] / 2 + 0.35, 2 - b["al"]
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def glove(tex, tint, top=4.0):
        m.box((-h, low - 0.1, -h), (h, low + top, h), tex, tint)

    def pauldron(tex, tint, big=1.0):
        m.box((-h - 0.7 * big, -1.0, -h - 0.6 * big), (h + 0.7 * big, 2.8, h + 0.6 * big), tex, tint)
        m.box((-h - 0.8 * big, -1.2, -h - 0.7 * big), (h + 0.8 * big, -0.6, h + 0.7 * big), tex, ARM_TRIM)

    if kind == "leather":
        glove(lea, ARM_MAIN, 4.6)
        m.box((-h - 0.1, low + 4.0, -h - 0.1), (h + 0.1, low + 4.8, h + 0.1), lea, ARM_TRIM)
        m.box((-h - 0.2, 0.0, -h - 0.2), (h + 0.2, 2.6, h + 0.2), lea, ARM_MAIN)
    elif kind == "chain":
        m.box((-h, -4.2, -h), (h, 2.4, h), T["chain"], ARM_MAIN)
        glove(lea, ARM_TRIM, 3.4)
    elif kind == "scale":
        pauldron(met, ARM_MAIN)
        glove(met, ARM_TRIM, 4.6)
    elif kind == "plate":
        pauldron(met, ARM_MAIN, 1.3)
        m.box((-h, -5.0, -h), (h, -1.0, h), met, ARM_MAIN)
        glove(met, ARM_MAIN, 4.8)
        m.box((-h - 0.15, low + 3.6, -h - 0.15), (h + 0.15, low + 4.4, h + 0.15), met, ARM_TRIM)
    elif kind == "robe":
        m.box((-h - 0.3, low + 2.4, -h - 0.3), (h + 0.3, 2.5, h + 0.3), clo, ARM_MAIN)
        m.box((-h - 1.0, low + 1.6, -h - 1.0), (h + 1.0, low + 3.6, h + 1.0), clo, ARM_TRIM)
    elif kind == "ranger":
        glove(lea, ARM_TRIM, 5.0)
        m.box((-h - 0.2, -2.0, -h - 0.2), (h + 0.2, 2.5, h + 0.2), clo, ARM_MAIN)
    elif kind == "noble":
        m.box((-h, low + 3.4, -h), (h, 2.5, h), clo, ARM_MAIN)
        m.box((-h - 0.35, low + 2.8, -h - 0.35), (h + 0.35, low + 3.9, h + 0.35), T["white"])
    elif kind == "bone":
        m.box((-h - 0.6, -1.0, -h - 0.5), (h + 0.6, 3.0, h + 0.5), T["bone"], ARM_TRIM)
        glove(lea, ARM_MAIN, 4.6)
        m.seg((0, 2.6, 0), (0.8, 4.6, -0.4), 1.0, 1.0, T["bone"], ARM_TRIM)
    else:
        raise ValueError(kind)
    return m


def leg_base(b: dict) -> Model:
    m = Model()
    h, L = b["lw"] / 2, b["ll"]
    m.box((-h, -L, -h), (h, 0.5, h), T["cloth"], PANTS)
    m.box((-h - 0.2, -L, -h - 0.2), (h + 0.2, -L + 3.2, h + 0.7), T["boot"])
    m.box((-h - 0.3, -L + 2.8, -h - 0.3), (h + 0.3, -L + 3.6, h + 0.4), T["boot"])
    m.box((-h - 0.25, -L - 0.05, -h - 0.25), (h + 0.25, -L + 0.5, h + 0.75), T["sole"])
    return m


def leg_armor(kind: str, b: dict) -> Model:
    m = Model()
    h, L = b["lw"] / 2 + 0.35, b["ll"]
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def boot(tex, tint, top=3.8):
        m.box((-h - 0.1, -L - 0.05, -h - 0.1), (h + 0.1, -L + top, h + 0.6), tex, tint)

    if kind == "leather":
        m.box((-h, -L + 3.0, -h), (h, -0.5, h), lea, ARM_MAIN)
        boot(lea, ARM_TRIM)
    elif kind == "chain":
        m.box((-h, -L + 3.0, -h), (h, 0.2, h), T["chain"], ARM_MAIN)
        boot(lea, ARM_TRIM)
    elif kind == "scale":
        m.box((-h, -L * 0.5, -h), (h, 0.2, h), met, ARM_MAIN)
        boot(met, ARM_TRIM, 4.4)
    elif kind == "plate":
        m.box((-h, -L * 0.5, -h), (h, 0.2, h), met, ARM_MAIN)
        m.box((-h - 0.3, -L * 0.5 - 1.0, -h - 0.1), (h + 0.3, -L * 0.5 + 0.6, h + 0.7), met, ARM_TRIM)
        boot(met, ARM_MAIN, L * 0.5 - 1.0)
    elif kind == "robe":
        boot(lea, ARM_TRIM, 3.4)
    elif kind == "ranger":
        boot(lea, ARM_TRIM, 5.4)
        m.box((-h - 0.05, -4.0, -h - 0.05), (h + 0.05, 0.2, h + 0.05), clo, ARM_MAIN)
    elif kind == "noble":
        m.box((-h, -L + 3.4, -h), (h, 0.2, h), clo, ARM_MAIN)
        boot(T["leather"], ARM_TRIM, 4.0)
    elif kind == "bone":
        m.box((-h, -L * 0.5, -h), (h, -L * 0.5 + 2.4, h + 0.4), T["bone"], ARM_TRIM)
        boot(T["fur"], ARM_MAIN)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- write


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


PARTS = {
    # part: (base builder, armor builder)
    "torso": (torso_base, torso_armor),
    "arm": (arm_base, arm_armor),
    "leg": (leg_base, leg_armor),
}

# rig_data order (tc/rig.tc reads these by index).
RIG_KEYS = ["hip", "hx", "neck", "sx", "sy", "al", "grip", "ll", "td"]


def main() -> None:
    # Start clean: body models from older rigs would linger otherwise.
    for d in (ASSETS / "models/body", ASSETS / "items/body"):
        shutil.rmtree(d, ignore_errors=True)
    for f in (ASSETS / "models/icon").glob("armor_*.json"):
        f.unlink()
    textures()
    n = lambda m, rel: model_node(m.save(rel))

    female_head = n(head_base(True), "body/head_f")
    head_layers = [select_node(0, {"f": female_head, "df": female_head}, n(head_base(), "body/head"))]
    head_layers.append(select_node(1, {k: n(helmet(k), f"body/helmet_{k}") for k in ARMORS}))
    head_layers.append(select_node(2, {k: n(hair(k), f"body/hair_{k}") for k in HAIRS}))
    head_layers.append(select_node(3, {k: n(ears(k), f"body/ears_{k}") for k in EARS}))
    head_layers.append(select_node(4, {k: n(beard(k), f"body/beard_{k}") for k in BEARDS}))
    write_item("body/head", composite(*head_layers))

    for part, (base_fn, armor_fn) in PARTS.items():
        cases = {}
        for bid, b in BUILDS.items():
            layers = [n(base_fn(b), f"body/{bid}/{part}"),
                      select_node(1, {k: n(armor_fn(k, b), f"body/{bid}/{part}_{k}") for k in ARMORS})]
            if part == "torso":
                layers.append(select_node(2, {k: n(tail(k, b), f"body/{bid}/tail_{k}") for k in TAILS}))
            cases[bid] = composite(*layers)
        write_item(f"body/{part}", select_node(0, cases, cases["m"]))

    # Inventory icons of armor pieces: the man's piece.
    for slot, fn in (("head", helmet), ("torso", lambda k: torso_armor(k, BUILDS["m"])),
                     ("arm", lambda k: arm_armor(k, BUILDS["m"])), ("leg", lambda k: leg_armor(k, BUILDS["m"]))):
        cases = {}
        for k in ARMORS:
            m = fn(k)
            m.display = fit_gui(m)
            cases[k] = model_node(m.save(f"icon/armor_{slot}_{k}"))
        write_item(f"armor/{slot}", select_node(0, cases, cases["leather"]))

    # Rig data for the plot code and the viewer.
    lines = [
        "// Generated by pack/src/character.py: do not edit.",
        "// Rig joints per build in model pixels (1/16 block at scale 1), feet at y 0.",
        "",
        "/** Per build: [hipY, hipX, neckY, shoulderX, shoulderY, armLength, grip",
        " * (shoulder to hand), legLength, torsoDepth]. */",
        "declare global rigBuild: dict[list];",
        "",
        "function loadRigData {",
        "    global rigBuild = {};",
    ]
    for bid, b in BUILDS.items():
        lines.append(f"    global rigBuild[\"{bid}\"] = [{', '.join(fmt(b[k]) for k in RIG_KEYS)}];")
    lines += ["}", "",
              "/** Option lists for the character designer. */",
              "function rigOptions(kind: str): list[str] {"]
    for kind, vals in (("armor", ARMORS), ("hair", HAIRS), ("ears", EARS), ("beard", BEARDS), ("tail", TAILS)):
        lines.append(f"    if (kind == \"{kind}\") {{ return [{', '.join(json.dumps(v) for v in vals)}]; }}")
    lines += ["    return [];", "}", ""]
    (ROOT / "tc/rig_data.tc").write_text("\n".join(lines))
    view = ROOT / "tools/viewer/rig_data.json"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(json.dumps({"builds": {bid: {k: b[k] for k in RIG_KEYS} for bid, b in BUILDS.items()},
                                "armors": ARMORS, "hairs": HAIRS, "ears": EARS, "beards": BEARDS, "tails": TAILS}, indent=1))
    print(f"character: {len(BUILDS)} builds, {len(ARMORS)} armors, {len(HAIRS)} hair, {len(EARS)} ears, "
          f"{len(BEARDS)} beards, {len(TAILS)} tails")


if __name__ == "__main__":
    main()
