#!/usr/bin/env python3
"""Weapons, shields and effect models.

Weapons are modelled with the grip at the origin, the blade (or head) along
+Y and the edge along +Z, in pixels of a 16 px block, then written at half
size (Model k=0.5) so long weapons fit the model bounds; tc/rig.tc draws held
items at twice the rig scale. Tints: 0 head/blade (material), 1 handle,
2 accent (guard, gem). strings[0] picks the shape variant ("1".."3").

Effect models (rpg:fx/*) are bright (light 15) and tinted by color 0.

Writes pack/assets/rpg/{models,items,textures} and tc/item_data.tc.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from common import (ASSETS, EMPTY, NS, ROOT, Model, make_slash_texture, make_texture, model_node,
                    select_node, write_item)

T = {}
HEAD, HANDLE, ACCENT = 0, 1, 2


def textures():
    for kind in ("metal", "wood", "leather", "gem", "bone", "white", "dark", "glow"):
        T[kind] = make_texture(f"wpn_{kind}", kind)
    T["slash"] = make_slash_texture("fx_slash")
    T["rune"] = rune_texture()


def rune_texture() -> str:
    """A magic circle: rings, a star and glyph ticks, white on clear."""
    n = 128
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = n / 2
    for r, w in ((62, 3), (55, 2), (40, 2), (22, 2)):
        d.ellipse((c - r, c - r, c + r, c + r), outline=(255, 255, 255, 255), width=w)
    pts = [(c + 40 * math.cos(math.radians(90 + i * 144)), c - 40 * math.sin(math.radians(90 + i * 144))) for i in range(6)]
    d.line(pts, fill=(255, 255, 255, 230), width=2)
    rng = random.Random(7)
    for i in range(24):
        a = math.radians(i * 15)
        r0, r1 = 56, 61
        if i % 2:
            d.line((c + r0 * math.cos(a), c + r0 * math.sin(a), c + r1 * math.cos(a), c + r1 * math.sin(a)),
                   fill=(255, 255, 255, 255), width=2)
        else:
            x, y = c + 48 * math.cos(a), c + 48 * math.sin(a)
            g = rng.choice(["L", "T", "X", "V"])
            s = 3
            if g == "L":
                d.line((x - s, y - s, x - s, y + s, x + s, y + s), fill=(255, 255, 255, 255), width=1)
            elif g == "T":
                d.line((x - s, y - s, x + s, y - s), fill=(255, 255, 255, 255), width=1)
                d.line((x, y - s, x, y + s), fill=(255, 255, 255, 255), width=1)
            elif g == "X":
                d.line((x - s, y - s, x + s, y + s), fill=(255, 255, 255, 255), width=1)
                d.line((x - s, y + s, x + s, y - s), fill=(255, 255, 255, 255), width=1)
            else:
                d.line((x - s, y - s, x, y + s, x + s, y - s), fill=(255, 255, 255, 255), width=1)
    path = ASSETS / "textures/item/fx_rune.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return f"{NS}:item/fx_rune"


# ---------------------------------------------------------------- weapon shapes


def blade(m: Model, y0: float, y1: float, w: float, th: float = 0.8, tip: float = 3, curve: int = 0):
    """A straight double-edged blade from y0 to y1, w wide, with a tip."""
    m.box((-th / 2, y0, -w / 2), (th / 2, y1, w / 2), T["metal"], HEAD)
    m.box((-th / 2 + 0.1, y1, -w / 3), (th / 2 - 0.1, y1 + tip * 0.6, w / 3), T["metal"], HEAD)
    m.box((-th / 2 + 0.15, y1 + tip * 0.6, -w / 6), (th / 2 - 0.15, y1 + tip, w / 6), T["metal"], HEAD)
    m.box((-th / 2 - 0.05, y0 + 1, -0.25), (th / 2 + 0.05, y1 - 2, 0.25), T["dark"], HEAD)


def grip(m: Model, y0: float, y1: float, r: float = 0.7, tex: str = "leather"):
    m.box((-r, y0, -r), (r, y1, r), T[tex], HANDLE)


def sword(v: int, length: float = 16, gl: float = 3.5) -> Model:
    m = Model(0.5)
    grip(m, -gl, gl)
    m.box((-1.1, -gl - 1.4, -1.1), (1.1, -gl, 1.1), T["metal"], ACCENT)
    if v == 1:
        m.box((-1, gl, -3.8), (1, gl + 1.2, 3.8), T["metal"], ACCENT)
        blade(m, gl + 1.2, gl + 1.2 + length, 2.6)
    elif v == 2:
        m.box((-1, gl, -2.2), (1, gl + 1.2, 2.2), T["metal"], ACCENT)
        for s in (1, -1):
            m.box((-0.8, gl + 0.2, s * 2), (0.8, gl + 2.8, s * 3.4), T["metal"], ACCENT,
                  rot=("x", s * -22.5, (0, gl + 0.6, s * 2.7)))
        m.box((-1.2, gl + 0.1, -0.9), (1.2, gl + 1.3, 0.9), T["gem"], ACCENT, light=6)
        blade(m, gl + 1.2, gl + 1.2 + length, 2.2, tip=4)
    else:
        m.box((-1, gl, -3), (1, gl + 1, 3), T["metal"], ACCENT)
        m.box((-0.4, gl + 1, -1.2), (0.4, gl + 1 + length * 0.7, 2.2), T["metal"], HEAD)
        m.box((-0.4, gl + 1 + length * 0.7, -0.8), (0.4, gl + 1 + length, 2.4), T["metal"], HEAD,
              rot=("x", 22.5, (0, gl + 1 + length * 0.7, 0)))
    return m


def greatsword(v: int) -> Model:
    m = Model(0.5)
    grip(m, -7, 6, 0.8)
    m.box((-1.4, -8.6, -1.4), (1.4, -7, 1.4), T["metal"], ACCENT)
    m.box((-1.4, 6, -6 if v != 2 else -4.5), (1.4, 7.6, 6 if v != 2 else 4.5), T["metal"], ACCENT)
    if v == 3:
        m.box((-0.6, 7.6, -2.2), (0.6, 11, 2.2), T["leather"], HANDLE)
        blade(m, 11, 38, 3.6, th=1.1, tip=4)
    else:
        blade(m, 7.6, 37, 4.0 if v == 1 else 3.2, th=1.1, tip=5)
    if v == 2:
        for s in (1, -1):
            m.box((-0.5, 12, s * 1.8), (0.5, 15, s * 2.8), T["metal"], HEAD)
    return m


def dagger(v: int) -> Model:
    m = Model(0.5)
    grip(m, -2.6, 2.6, 0.6)
    m.box((-0.9, -3.6, -0.9), (0.9, -2.6, 0.9), T["metal"], ACCENT)
    if v == 1:
        m.box((-0.9, 2.6, -2.6), (0.9, 3.4, 2.6), T["metal"], ACCENT)
        blade(m, 3.4, 10, 1.8, th=0.6, tip=2.5)
    elif v == 2:
        m.box((-0.9, 2.6, -1.6), (0.9, 3.4, 1.6), T["metal"], ACCENT)
        m.box((-0.3, 3.4, -0.6), (0.3, 9, 1.4), T["metal"], HEAD)
        m.box((-0.3, 8, -0.2), (0.3, 12, 1.2), T["metal"], HEAD, rot=("x", -22.5, (0, 9, 0)))
    else:
        m.box((-0.9, 2.6, -2), (0.9, 3.4, 2), T["metal"], ACCENT)
        m.box((-0.5, 3.4, -0.5), (0.5, 12, 0.5), T["metal"], HEAD)
        m.box((-0.3, 12, -0.3), (0.3, 14, 0.3), T["metal"], HEAD)
    return m


def polearm(kind: str, v: int) -> Model:
    m = Model(0.5)
    top = 36 if kind == "spear" else 38
    grip(m, -14, top, 0.65, "wood")
    m.box((-0.9, -15, -0.9), (0.9, -14, 0.9), T["metal"], ACCENT)
    for y in (-2, 6):
        m.box((-0.8, y, -0.8), (0.8, y + 2.5, 0.8), T["leather"], ACCENT)
    if kind == "spear":
        m.box((-0.9, top - 1, -0.9), (0.9, top + 1.5, 0.9), T["metal"], ACCENT)
        if v == 1:
            blade(m, top + 1.5, top + 7, 3.2, th=0.7, tip=3)
        elif v == 2:
            blade(m, top + 1.5, top + 9, 1.8, th=0.8, tip=2)
            m.box((-0.6, top + 1.5, -3), (0.6, top + 2.4, 3), T["metal"], HEAD)
        else:
            m.box((-0.5, top + 1.5, -0.5), (0.5, top + 10, 0.5), T["metal"], HEAD)
            m.box((-0.4, top + 4, -2.5), (0.4, top + 5, 2.5), T["metal"], HEAD,
                  rot=("x", 22.5, (0, top + 4.5, 0)))
    else:  # halberd
        m.box((-0.9, top - 1, -0.9), (0.9, top + 1, 0.9), T["metal"], ACCENT)
        m.box((-0.5, top - 8, 0.5), (0.5, top, 7 if v != 3 else 5.5), T["metal"], HEAD)
        m.box((-0.45, top - 9, 6), (0.45, top + 1, 7.4 if v != 3 else 6.4), T["metal"], HEAD)
        m.box((-0.5, top - 5, -4), (0.5, top - 3, -0.5), T["metal"], HEAD)
        blade(m, top + 1, top + 7, 1.6, th=0.6, tip=2)
    return m


def axe(kind: str, v: int) -> Model:
    m = Model(0.5)
    big = kind == "greataxe"
    lo, hi = (-9, 30) if big else (-5, 15)
    grip(m, lo, hi, 0.75 if big else 0.65, "wood")
    m.box((-0.9, lo - 1, -0.9), (0.9, lo, 0.9), T["metal"], ACCENT)
    hh = 9 if big else 6
    w = 8 if big else 5.5
    y0 = hi - hh + 1
    m.box((-0.9, y0, -1.2), (0.9, hi + 1, 1.2), T["metal"], ACCENT)
    sides = (1, -1) if (big and v != 2) or (not big and v == 3) else (1,)
    for s in sides:
        m.box((-0.5, y0 + 1, s * 1.2), (0.5, hi, s * (w - 1.2)), T["metal"], HEAD)
        m.box((-0.4, y0 - 1, s * (w - 1.6)), (0.4, hi + 2, s * w), T["metal"], HEAD)
    if len(sides) == 1:
        m.box((-0.5, hi - 3, -1.2), (0.5, hi - 1, -3.5), T["metal"], HEAD)
    return m


def blunt(kind: str, v: int) -> Model:
    m = Model(0.5)
    big = kind == "warhammer"
    lo, hi = (-9, 28) if big else (-4, 13)
    grip(m, lo, hi, 0.75 if big else 0.7, "wood" if big else "leather")
    m.box((-1, lo - 1.2, -1), (1, lo, 1), T["metal"], ACCENT)
    if big:
        m.box((-2.6, hi, -5.5 if v != 3 else -4), (2.6, hi + 6, 5.5 if v != 3 else 4), T["metal"], HEAD)
        m.box((-2.9, hi + 0.5, 5.5), (2.9, hi + 5.5, 6.2), T["metal"], ACCENT)
        if v == 2:
            m.box((-0.7, hi + 2, -8.5), (0.7, hi + 4, -5.5), T["metal"], HEAD)
        m.box((-0.6, hi + 6, -0.6), (0.6, hi + 9, 0.6), T["metal"], HEAD)
    else:
        if v == 1:
            m.box((-2, hi, -2), (2, hi + 6, 2), T["metal"], HEAD)
            for ax in ("x", "z"):
                a, b = ((-3, hi + 0.5, -0.5), (3, hi + 5.5, 0.5)) if ax == "x" else ((-0.5, hi + 0.5, -3), (0.5, hi + 5.5, 3))
                m.box(a, b, T["metal"], HEAD)
        elif v == 2:
            m.box((-2.5, hi, -2.5), (2.5, hi + 5, 2.5), T["metal"], HEAD)
            m.box((-2, hi + 0.5, -2), (2, hi + 4.5, 2), T["metal"], HEAD, rot=("y", 45, (0, hi + 2.5, 0)))
            m.box((-0.5, hi + 5, -0.5), (0.5, hi + 7, 0.5), T["metal"], ACCENT)
        else:
            m.box((-1.8, hi, -1.8), (1.8, hi + 7, 1.8), T["metal"], HEAD)
            for y in (hi + 1.5, hi + 4.5):
                m.box((-2.6, y, -2.6), (2.6, y + 1, 2.6), T["metal"], ACCENT)
    return m


def scythe(v: int) -> Model:
    m = Model(0.5)
    grip(m, -12, 34, 0.7, "wood" if v != 3 else "bone")
    m.box((-0.8, 4, -0.8), (0.8, 6, 2.6), T["wood"], HANDLE)
    m.box((-1, 32, -1), (1, 35, 1), T["metal"], ACCENT)
    # Blade: sweeps from the top toward -Z (backward) and curves down.
    m.box((-0.45, 31, -12), (0.45, 34, -1), T["metal"], HEAD)
    m.box((-0.45, 29.5, -19), (0.45, 32, -11), T["metal"], HEAD, rot=("x", -22.5, (0, 32.5, -11.5)))
    m.box((-0.4, 25.5, -23), (0.4, 28, -17.5), T["metal"], HEAD, rot=("x", -45, (0, 28, -18)))
    if v == 2:
        m.box((-0.45, 34, -1), (0.45, 38, 0.6), T["metal"], HEAD)
    return m


def gauntlet(v: int) -> Model:
    m = Model(0.5)
    # Around the fist: the hand sits at the origin; the knuckles face +Y.
    m.box((-2.6, -6, -2.6), (2.6, 2.6, 2.6), T["metal"], HEAD)
    m.box((-2.9, -6.5, -2.9), (2.9, -4.5, 2.9), T["leather"], HANDLE)
    m.box((-2.2, 2.6, -2.4), (2.2, 3.6, 2.4), T["metal"], ACCENT)
    if v >= 2:
        for x in (-1.4, 0, 1.4):
            m.box((x - 0.4, 3.6, -0.4), (x + 0.4, 5.2 if v == 2 else 6.5, 0.4), T["metal"], ACCENT)
    return m


def staff(v: int) -> Model:
    m = Model(0.5)
    grip(m, -14, 30, 0.75, "wood" if v != 3 else "bone")
    m.box((-1, -15, -1), (1, -14, 1), T["metal"], ACCENT)
    if v == 1:
        for s in (1, -1):
            m.box((-0.6, 28, s * 0.5), (0.6, 35, s * 2.2), T["wood"], HANDLE, rot=("x", s * 22.5, (0, 29, 0)))
        m.box((-1.6, 31, -1.6), (1.6, 34.2, 1.6), T["gem"], ACCENT, light=15)
    elif v == 2:
        m.box((-2.2, 30, -2.2), (2.2, 31, 2.2), T["metal"], ACCENT)
        m.box((-1.4, 31, -1.4), (1.4, 37, 1.4), T["gem"], ACCENT, light=15, rot=("y", 45, (0, 34, 0)))
    else:
        m.box((-1, 30, -1), (1, 32, 1), T["bone"], HANDLE)
        m.box((-2.5, 32, -2.5), (2.5, 36.5, 2.5), T["bone"], HANDLE)
        m.box((-0.8, 33.5, 2.4), (0.8, 35, 2.6), T["gem"], ACCENT, light=15)
    return m


def wand(v: int) -> Model:
    m = Model(0.5)
    grip(m, -3, 3, 0.55, "leather")
    m.box((-0.45, 3, -0.45), (0.45, 12 if v != 2 else 13, 0.45), T["wood"], HANDLE)
    if v == 1:
        m.box((-0.9, 12, -0.9), (0.9, 14, 0.9), T["gem"], ACCENT, light=15)
    elif v == 2:
        m.box((-0.7, 13, -0.7), (0.7, 16, 0.7), T["gem"], ACCENT, light=15, rot=("y", 45, (0, 14, 0)))
        m.box((-1.1, 12.4, -1.1), (1.1, 13.2, 1.1), T["metal"], HEAD)
    else:
        m.box((-0.6, 12, -0.6), (0.6, 13, 0.6), T["metal"], HEAD)
        for s in (1, -1):
            m.box((-0.3, 12.5, s * 0.4), (0.3, 15.5, s * 1.4), T["metal"], HEAD, rot=("x", s * 22.5, (0, 13, 0)))
        m.box((-0.7, 14, -0.7), (0.7, 15.4, 0.7), T["gem"], ACCENT, light=15)
    m.box((-0.7, -3.6, -0.7), (0.7, -3, 0.7), T["metal"], HEAD)
    return m


def bow(kind: str, v: int) -> Model:
    m = Model(0.5)
    if kind == "bow":
        grip(m, -2.5, 2.5, 0.8, "leather")
        L = 12 if v != 2 else 15
        for s in (1, -1):
            m.box((-0.6, s * 2.5, -0.6), (0.6, s * 9, 0.6), T["wood"], HEAD)
            a, b = ((-0.5, 8.5, -0.5), (0.5, L + 2, 0.5)) if s > 0 else ((-0.5, -L - 2, -0.5), (0.5, -8.5, 0.5))
            m.box(a, b, T["wood"], HEAD, rot=("x", s * -22.5, (0, s * 9, 0)))
            m.box((-0.7, s * 2.5, -0.7), (0.7, s * 3.4, 0.7), T["metal"], ACCENT)
        m.box((-0.1, -L, -5.2), (0.1, L, -5.0), T["white"])
    else:
        # Crossbow: stock along +Y (the aim), prod across X at the front.
        m.box((-0.8, -8, -1), (0.8, 12, 1), T["wood"], HANDLE)
        m.box((-0.5, -8, -2.5), (0.5, -2, -1), T["wood"], HANDLE)
        m.box((-9, 10, -0.6), (9, 11.2, 0.6), T["wood"], HEAD)
        m.box((-1, 9, -1.3), (1, 12, 1.3), T["metal"], ACCENT)
        m.box((-8.6, 4, -0.15), (8.6, 4.3, 0.15), T["white"])
        m.box((-0.3, 4, 1), (0.3, 11, 1.4), T["metal"], ACCENT)
    return m


def shield(v: int) -> Model:
    m = Model(0.5)
    # Held on the forearm: the face looks out along -X (away from a left
    # arm), long axis along the arm (+Z of the item is the arm's down).
    if v == 1:
        m.box((-1.2, -8, -6), (0, 8, 6), T["wood"], HEAD)
        m.box((-1.5, -8.3, -6.3), (-0.1, 8.3, -5.6), T["metal"], ACCENT)
        m.box((-1.5, -8.3, 5.6), (-0.1, 8.3, 6.3), T["metal"], ACCENT)
        m.box((-1.9, -1.5, -1.5), (-1.2, 1.5, 1.5), T["metal"], ACCENT)
    elif v == 2:
        m.box((-1.2, -10, -5.5), (0, 8, 5.5), T["metal"], HEAD)
        m.box((-1.2, -14, -3), (0, -10, 3), T["metal"], HEAD)
        m.box((-1.6, -12, -0.6), (-1.1, 7, 0.6), T["metal"], ACCENT)
        m.box((-1.6, 1, -5), (-1.1, 2.2, 5), T["metal"], ACCENT)
    else:
        m.box((-1.2, -7, -7), (0, 7, 7), T["metal"], HEAD, rot=("x", 45, (0, 0, 0)))
        m.box((-1.6, -4, -4), (-1.1, 4, 4), T["gem"], ACCENT)
    return m


# ---------------------------------------------------------------- effects


def crescent_texture(name: str, full: bool) -> str:
    """A bright crescent (or full ring) fading toward its inner edge and its
    tail, on a clear 128 px texture."""
    n = 128
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    px = img.load()
    c = n / 2
    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            r = math.hypot(dx, dy) / c
            if not 0.62 < r < 0.98:
                continue
            ang = math.degrees(math.atan2(dx, -dy))  # 0 at the top, +90 right
            if full:
                tail = 1.0
            else:
                if not -95 < ang < 95:
                    continue
                tail = (ang + 95) / 190  # fades toward the start of the swing
            edge = 1 - abs(r - 0.9) / 0.28
            a = max(0.0, min(1.0, edge)) ** 1.5 * tail ** 1.3
            px[x, y] = (255, 255, 255, int(255 * a))
    path = ASSETS / "textures/item" / f"{name}.png"
    img.save(path)
    return f"{NS}:item/{name}"


def fx_slash(full: bool) -> Model:
    """One flat quad in the XZ plane (32 px across) carrying a crescent:
    the arc runs across the front (+Z) from -X to +X."""
    m = Model(1.0)
    tex = crescent_texture("fx_ring" if full else "fx_crescent", full)
    m.box((-16, -0.05, -16), (16, 0.05, 16), tex, 0, light=15, faces=("up", "down"))
    m.elements[-1]["faces"]["up"]["uv"] = [0, 16, 16, 0]
    m.elements[-1]["faces"]["down"]["uv"] = [0, 0, 16, 16]
    return m


def fx_slash_old(full: bool) -> Model:
    """A flat ring of plates in the XZ plane (radius 14 px), facing +Z for
    the half arc; texture bright at the outer edge."""
    m = Model(1.0)
    R, w = 14.0, 4.0
    steps = 16 if full else 9
    span = 360 if full else 180
    for i in range(steps):
        ang = -90 + span * (i + 0.5) / steps if not full else span * (i + 0.5) / steps
        a = math.radians(ang)
        cx, cz = R * math.sin(a), R * math.cos(a)
        seg = 2 * math.pi * R * (span / 360) / steps + 0.6
        # Plate whose length runs along the tangent: build it along X at the
        # center, then rotate about Y by the nearest allowed angle.
        tang = (ang + 90) % 180
        base = 0 if tang < 45 or tang >= 135 else 90
        rot = ((tang - base + 90) % 180) - 90
        rot = max(-45, min(45, round(rot / 22.5) * 22.5))
        if base == 0:
            a0, b0 = (cx - seg / 2, -0.2, cz - w / 2), (cx + seg / 2, 0.2, cz + w / 2)
        else:
            a0, b0 = (cx - w / 2, -0.2, cz - seg / 2), (cx + w / 2, 0.2, cz + seg / 2)
        m.box(a0, b0, T["slash"], 0, rot=("y", -rot, (cx, 0, cz)), light=15, faces=("up", "down"))
    return m


def fx_orb() -> Model:
    m = Model(1.0)
    m.box((-3, -3, -3), (3, 3, 3), T["glow"], 0, light=15)
    m.box((-2.6, -2.6, -2.6), (2.6, 2.6, 2.6), T["glow"], 0, light=15, rot=("y", 45, (0, 0, 0)))
    m.box((-2.6, -2.6, -2.6), (2.6, 2.6, 2.6), T["glow"], 0, light=15, rot=("x", 45, (0, 0, 0)))
    m.box((-1.6, -1.6, -1.6), (1.6, 1.6, 1.6), T["white"], light=15)
    return m


def fx_bolt() -> Model:
    m = Model(1.0)
    m.box((-1.2, -1.2, -7), (1.2, 1.2, 4), T["glow"], 0, light=15, rot=("z", 45, (0, 0, 0)))
    m.box((-0.8, -0.8, -9), (0.8, 0.8, 6), T["white"], light=15)
    return m


def fx_shard() -> Model:
    m = Model(1.0)
    m.box((-2, 0, -2), (2, 10, 2), T["glow"], 0, light=8, rot=("y", 45, (0, 0, 0)))
    m.box((-1.2, 9, -1.2), (1.2, 14, 1.2), T["glow"], 0, light=8, rot=("y", 45, (0, 9, 0)))
    m.box((-1.5, 0, -1.5), (1.5, 7, 1.5), T["glow"], 0, light=8, rot=("x", 22.5, (0, 0, 0)))
    return m


def fx_rune() -> Model:
    m = Model(1.0)
    m.box((-16, -0.1, -16), (16, 0.1, 16), T["rune"], 0, light=15, faces=("up", "down"))
    m.elements[-1]["faces"]["up"]["uv"] = [0, 0, 16, 16]
    m.elements[-1]["faces"]["down"]["uv"] = [0, 16, 16, 0]
    return m


def fx_arrow() -> Model:
    m = Model(1.0)
    m.box((-0.4, -0.4, -7), (0.4, 0.4, 7), T["wood"], HANDLE)
    m.box((-0.2, -1.6, -7), (0.2, 1.6, -3.5), T["white"])
    m.box((-1.6, -0.2, -7), (1.6, 0.2, -3.5), T["white"])
    m.box((-0.8, -0.8, 7), (0.8, 0.8, 9), T["metal"], HEAD, rot=("z", 45, (0, 0, 8)))
    return m


def fx_cube() -> Model:
    """A plain tinted bright cube (walls, particles of earth, beams)."""
    m = Model(1.0)
    m.box((-8, -8, -8), (8, 8, 8), T["glow"], 0, light=12)
    return m


# ---------------------------------------------------------------- write

WEAPONS = {
    # type: (builder, variants)
    "sword": (lambda v: sword(v), 3),
    "longsword": (lambda v: sword(v, 22, 5), 3),
    "greatsword": (greatsword, 3),
    "dagger": (dagger, 3),
    "spear": (lambda v: polearm("spear", v), 3),
    "halberd": (lambda v: polearm("halberd", v), 3),
    "axe": (lambda v: axe("axe", v), 3),
    "greataxe": (lambda v: axe("greataxe", v), 3),
    "mace": (lambda v: blunt("mace", v), 3),
    "warhammer": (lambda v: blunt("warhammer", v), 3),
    "scythe": (scythe, 2),
    "gauntlets": (gauntlet, 3),
    "staff": (staff, 3),
    "wand": (wand, 3),
    "bow": (lambda v: bow("bow", v), 2),
    "crossbow": (lambda v: bow("crossbow", v), 1),
    "shield": (shield, 3),
}


def gui_display(m: Model) -> dict:
    """Display transforms so the weapon fits a GUI slot diagonally."""
    ys = [c for el in m.elements for c in (el["from"][1], el["to"][1])]
    zs = [c for el in m.elements for c in (el["from"][2], el["to"][2])]
    ext = max(max(ys) - min(ys), max(zs) - min(zs), 1)
    s = min(1.6, 22 / ext)
    cy = (max(ys) + min(ys)) / 2 - 8
    cz = (max(zs) + min(zs)) / 2 - 8
    # After rotating Y by 90 the model's Z runs along screen X.
    gui = {"rotation": [0, 90, -45], "translation": [round(-cz * s * 0.7 - cy * s * 0.7, 2) * 0, 0, 0],
           "scale": [s, s, s]}
    shift_x = -(cz * 0.707 - cy * 0.707) * s
    shift_y = -(cz * 0.707 + cy * 0.707) * s
    gui["translation"] = [round(max(-80, min(80, shift_x)), 2), round(max(-80, min(80, shift_y)), 2), 0]
    return {"gui": gui, "ground": {"scale": [s * 0.5] * 3}, "fixed": {"rotation": [0, 90, 0], "scale": [s] * 3}}


def first_person_empty(node: dict) -> dict:
    """Hides the item in first person (the camera player holds it)."""
    return {"type": "minecraft:select", "property": "minecraft:display_context",
            "cases": [{"when": ["firstperson_righthand", "firstperson_lefthand", "thirdperson_righthand",
                                "thirdperson_lefthand", "head"], "model": EMPTY}],
            "fallback": node}


def main() -> None:
    textures()
    for wt, (fn, nv) in WEAPONS.items():
        cases = {}
        for v in range(1, nv + 1):
            m = fn(v)
            m.display = gui_display(m)
            cases[str(v)] = model_node(m.save(f"weapon/{wt}_{v}"))
        write_item(f"weapon/{wt}", first_person_empty(select_node(0, cases, cases["1"])))
    for name, m in (("slash", fx_slash(False)), ("ring", fx_slash(True)), ("orb", fx_orb()), ("bolt", fx_bolt()),
                    ("shard", fx_shard()), ("rune", fx_rune()), ("arrow", fx_arrow()), ("cube", fx_cube())):
        write_item(f"fx/{name}", model_node(m.save(f"fx/{name}")))
    write_item("empty", EMPTY)
    print(f"weapons: {len(WEAPONS)} types; fx: 8 models")


if __name__ == "__main__":
    main()
