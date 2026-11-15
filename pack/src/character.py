#!/usr/bin/env python3
"""The character rig: body parts, clothes, armor, hair, ears, beards, tails.

Every character is six item displays (head, torso, two arms, two legs). Each
part's item model (rpg:body/<part>) is a composite whose layers are picked by
the item's custom model data strings and tinted by its colors (see PLAN.md,
"Character rig"):

  strings[0] build: m, f, dm, df (dwarf builds are short and stocky)
  strings[1] armor piece on this part
  strings[2] hair style (head) / tail (torso)
  strings[3] ears or horns (head)
  strings[4] beard (head)

  colors: 0 skin, 1 hair, 2 eyes, 3 clothes, 4 armor main, 5 armor trim,
          6 horns, 7 trousers

Writes pack/assets/rpg/{models,items,textures} and tc/rig_data.tc.
"""

from __future__ import annotations

from common import (ROOT, Model, composite, fit_gui, make_texture, model_node, select_node, write_item)

SKIN, HAIR, EYE, CLOTH, ARM_MAIN, ARM_TRIM, HORN, PANTS = range(8)

BUILDS = {
    # tw/th/td torso size, aw/al arm width/length, lw/ll leg width/length,
    # sh shoulder x, hip leg x.
    "m": dict(tw=8, th=12, td=4, aw=4, al=12, lw=4, ll=12, sh=6, hip=2, bust=False),
    "f": dict(tw=7, th=12, td=4, aw=3, al=12, lw=3.5, ll=12, sh=5, hip=1.75, bust=True),
    "dm": dict(tw=10, th=10, td=6, aw=4, al=10, lw=5, ll=8, sh=7, hip=2.5, bust=False),
    "df": dict(tw=9, th=10, td=5, aw=3.5, al=10, lw=4.5, ll=8, sh=6.25, hip=2.25, bust=True),
}

ARMORS = ["leather", "chain", "scale", "plate", "robe", "ranger", "noble", "bone"]
HAIRS = ["short", "long", "ponytail", "braid", "bun", "mohawk", "curly", "spiky", "bob", "shaggy"]
EARS = ["human", "elf", "cat", "wolf", "bear", "rabbit", "demon"]
BEARDS = ["stubble", "short", "full", "long", "braided", "goatee", "mustache"]
TAILS = ["cat", "wolf", "bear", "rabbit", "demon"]

T = {}


def textures():
    for kind in ("skin", "cloth", "leather", "metal", "chain", "hair", "fur", "dark", "white", "bone"):
        T[kind] = make_texture(f"body_{kind}", kind)
    T["lips"] = make_texture("body_lips", "skin", rgb=(190, 96, 96))
    T["boot"] = make_texture("body_boot", "leather", rgb=(110, 74, 46))
    T["belt"] = make_texture("body_belt", "leather", rgb=(70, 48, 30))
    T["buckle"] = make_texture("body_buckle", "metal", rgb=(230, 190, 90))


# ---------------------------------------------------------------- head


def head_base(female: bool = False) -> Model:
    m = Model()
    s = T["skin"]
    m.box((-4, 0, -4), (4, 8, 4), s, SKIN)
    m.box((-1.5, -1, -1.5), (1.5, 0, 1.5), s, SKIN)
    # Face on +Z: eyes (white + iris), brows, nose, mouth.
    for side in (1, -1):
        x0, x1 = sorted((side * 0.75, side * 3.0))
        m.box((x0, 3, 4), (x1, 4.5, 4.08), T["white"])
        ix0, ix1 = sorted((side * 0.9, side * 2.0))
        m.box((ix0, 3, 4.02), (ix1, 4.5, 4.12), T["white"], EYE)
        m.box((x0, 5.0, 4), (x1, 5.6, 4.15), T["hair"], HAIR)
    m.box((-0.5, 2.25, 4), (0.5, 3.75, 4.8), s, SKIN)
    if female:
        # Lashes, softer brows and colored lips.
        for side in (1, -1):
            x0, x1 = sorted((side * 0.6, side * 3.2))
            m.box((x0, 4.4, 4.02), (x1, 4.75, 4.14), T["dark"])
        m.box((-1.2, 1.2, 4), (1.2, 1.8, 4.1), T["lips"])
    else:
        m.box((-1.5, 1.25, 4), (1.5, 1.75, 4.08), T["dark"])
        # Jaw line.
        m.box((-4.05, 0, -2), (4.05, 0.6, 4.05), s, SKIN)
    return m


def hair(style: str) -> Model:
    m = Model()
    h = T["hair"]
    cap = lambda: m.box((-4.3, 6.2, -4.3), (4.3, 8.6, 4.3), h, HAIR)
    back = lambda y0: m.box((-4.3, y0, -4.4), (4.3, 8, -3.6), h, HAIR)
    sides = lambda y0: (m.box((-4.4, y0, -4.3), (-3.6, 8, 2.5), h, HAIR),
                        m.box((3.6, y0, -4.3), (4.4, 8, 2.5), h, HAIR))
    fringe = lambda: m.box((-4.3, 6.2, 3.6), (4.3, 7.4, 4.4), h, HAIR)
    if style == "short":
        cap(); back(4); sides(5); fringe()
    elif style == "long":
        cap(); fringe(); sides(-3)
        m.box((-4.3, -5, -4.6), (4.3, 8, -3.6), h, HAIR)
    elif style == "ponytail":
        cap(); back(4); sides(5); fringe()
        m.box((-1, 2, -6.5), (1, 7, -4.3), h, HAIR, rot=("x", 22.5, (0, 7, -4.3)))
        m.box((-0.8, -3, -6.8), (0.8, 2.5, -5.2), h, HAIR)
    elif style == "braid":
        cap(); back(3); sides(4); fringe()
        for i in range(4):
            y = 2 - i * 2.2
            m.box((-0.9, y - 2, -5.4), (0.9, y, -3.6), h, HAIR)
    elif style == "bun":
        cap(); back(4); sides(5)
        m.box((-2, 7, -5.5), (2, 11, -2), h, HAIR)
    elif style == "mohawk":
        m.box((-1, 7.5, -4.3), (1, 11, 4.3), h, HAIR)
        back(5)
    elif style == "curly":
        m.box((-5, 5, -5), (5, 9.5, 5), h, HAIR)
        sides(1); back(0)
        m.box((-5, 5.5, 3.6), (5, 7, 5.2), h, HAIR)
    elif style == "spiky":
        cap(); back(4); fringe()
        for i, x in enumerate((-3, -1, 1, 3)):
            m.box((x - 1, 8, -2), (x + 1, 10.5, 1), h, HAIR, rot=("z", (-22.5, 22.5)[i % 2], (x, 8, 0)))
    elif style == "bob":
        cap(); fringe()
        m.box((-4.5, 1.5, -4.5), (4.5, 8, -3.5), h, HAIR)
        m.box((-4.6, 1.5, -4.5), (-3.6, 8, 3), h, HAIR)
        m.box((3.6, 1.5, -4.5), (4.6, 8, 3), h, HAIR)
    elif style == "shaggy":
        cap(); sides(2); back(0)
        m.box((-4.3, 5.4, 3.6), (4.3, 7.4, 4.5), h, HAIR)
        m.box((-1, 8.4, -3), (3, 9.6, 2), h, HAIR)
    else:
        raise ValueError(style)
    return m


def ears(kind: str) -> Model:
    m = Model()
    s, h = T["skin"], T["fur"]
    if kind == "human":
        for side in (1, -1):
            x0, x1 = sorted((side * 4, side * 4.7))
            m.box((x0, 3, -0.5), (x1, 5, 0.8), s, SKIN)
    elif kind in ("elf", "demon"):
        for side in (1, -1):
            x0, x1 = sorted((side * 4, side * 7))
            m.box((x0, 3.5, -0.5), (x1, 5, 0.5), s, SKIN, rot=("z", side * 22.5, (side * 4, 4, 0)))
        if kind == "demon":
            for side in (1, -1):
                x = side * 2.5
                m.box((x - 0.9, 8, -1), (x + 0.9, 11, 1), T["bone"], HORN, rot=("x", -22.5, (x, 8, 0)))
                m.box((x - 0.6, 10.5, -3.2), (x + 0.6, 13, -1.6), T["bone"], HORN, rot=("x", -45, (x, 10.5, -2)))
    elif kind in ("cat", "wolf"):
        tall = 3 if kind == "cat" else 3.6
        for side in (1, -1):
            x = side * 2.8
            m.box((x - 1.5, 8, -0.8), (x + 1.5, 9.2, 0.8), h, HAIR)
            m.box((x - 1, 9.2, -0.6), (x + 1, 8 + tall * 0.8, 0.6), h, HAIR)
            m.box((x - 0.5, 8 + tall * 0.8, -0.4), (x + 0.5, 8 + tall, 0.4), h, HAIR)
            m.box((x - 0.7, 8.6, 0.6), (x + 0.7, 8 + tall * 0.7, 0.75), s, SKIN)
    elif kind == "bear":
        for side in (1, -1):
            x = side * 3.2
            m.box((x - 1.4, 7.6, -0.7), (x + 1.4, 10, 0.7), h, HAIR)
            m.box((x - 0.8, 8.2, 0.7), (x + 0.8, 9.4, 0.8), s, SKIN)
    elif kind == "rabbit":
        for i, side in enumerate((1, -1)):
            x = side * 2
            r = ("z", side * -22.5 if i == 0 else side * -22.5, (x, 8, 0))
            m.box((x - 1, 8, -0.6), (x + 1, 16, 0.6), h, HAIR, rot=r)
            m.box((x - 0.5, 9, 0.6), (x + 0.5, 15, 0.7), s, SKIN, rot=r)
    else:
        raise ValueError(kind)
    return m


def beard(kind: str) -> Model:
    m = Model()
    h = T["hair"]
    if kind == "stubble":
        m.box((-4.05, 0, 3.0), (4.05, 2.4, 4.06), h, HAIR)
    elif kind == "short":
        m.box((-4.1, -0.5, 2.5), (4.1, 2.6, 4.4), h, HAIR)
        m.box((-2, 1.9, 4.2), (2, 2.4, 4.7), h, HAIR)
    elif kind == "full":
        m.box((-4.2, -2, 1), (4.2, 3, 4.5), h, HAIR)
        m.box((-2.2, 1.8, 4.3), (2.2, 2.5, 4.9), h, HAIR)
    elif kind == "long":
        m.box((-4.2, -2, 1), (4.2, 3, 4.5), h, HAIR)
        m.box((-3, -7, 2), (3, -2, 4.4), h, HAIR)
        m.box((-2.2, 1.8, 4.3), (2.2, 2.5, 4.9), h, HAIR)
    elif kind == "braided":
        m.box((-4.2, -1.5, 1), (4.2, 3, 4.5), h, HAIR)
        for x in (-1.6, 1.6):
            for i in range(3):
                y = -1.5 - i * 2
                m.box((x - 0.8, y - 2, 2.6), (x + 0.8, y, 4.2), h, HAIR)
        m.box((-2.2, 1.8, 4.3), (2.2, 2.5, 4.9), h, HAIR)
    elif kind == "goatee":
        m.box((-1.2, -1.5, 3.4), (1.2, 1.4, 4.5), h, HAIR)
        m.box((-2, 1.8, 4.1), (2, 2.3, 4.6), h, HAIR)
    elif kind == "mustache":
        m.box((-2.5, 1.7, 4.1), (2.5, 2.4, 4.7), h, HAIR)
        for side in (1, -1):
            x0, x1 = sorted((side * 2.5, side * 3.2))
            m.box((x0, 0.6, 4.1), (x1, 2.4, 4.6), h, HAIR)
    else:
        raise ValueError(kind)
    return m


def helmet(kind: str) -> Model:
    m = Model()
    met, lea, clo, tri = T["metal"], T["leather"], T["cloth"], T["metal"]

    def shell(tex, tint, y0=-0.5, top=8.8, open_face=True):
        m.box((-4.6, 6, -4.6), (4.6, top, 4.6), tex, tint)
        m.box((-4.6, y0, -4.6), (4.6, 6, -3.8), tex, tint)
        m.box((-4.6, y0, -3.8), (-3.8, 6, 4.6), tex, tint)
        m.box((3.8, y0, -3.8), (4.6, 6, 4.6), tex, tint)
        if not open_face:
            m.box((-4.6, y0, 3.8), (4.6, 2.7, 4.7), tex, tint)
            m.box((-4.6, 4.6, 3.8), (4.6, 6, 4.7), tex, tint)
            m.box((-0.6, 2.7, 3.8), (0.6, 4.6, 4.75), tex, tint)

    if kind == "leather":
        m.box((-4.5, 5, -4.5), (4.5, 8.7, 4.5), lea, ARM_MAIN)
        m.box((-4.6, 5, -4.6), (4.6, 5.8, 4.6), lea, ARM_TRIM)
    elif kind == "chain":
        shell(T["chain"], ARM_MAIN)
    elif kind == "scale":
        shell(met, ARM_MAIN)
        m.box((-4.7, 5.5, 4.5), (4.7, 6.5, 5.6), tri, ARM_TRIM)
    elif kind == "plate":
        shell(met, ARM_MAIN, open_face=False)
        m.box((-0.5, 8.6, -4), (0.5, 10.5, 4), clo, ARM_TRIM)
    elif kind == "robe":
        # Pointed wizard hat.
        m.box((-6, 7.5, -6), (6, 8.3, 6), clo, ARM_MAIN)
        m.box((-4.2, 8.3, -4.2), (4.2, 11, 4.2), clo, ARM_MAIN)
        m.box((-3, 11, -3.5), (3, 13.5, 2.5), clo, ARM_MAIN, rot=("x", -22.5, (0, 11, 0)))
        m.box((-1.5, 13.2, -5.5), (1.5, 15.5, -2.5), clo, ARM_MAIN, rot=("x", -45, (0, 13, -3)))
        m.box((-4.3, 8.3, -4.3), (4.3, 9.2, 4.3), tri, ARM_TRIM)
    elif kind == "ranger":
        shell(clo, ARM_MAIN, y0=1)
        m.box((-2.5, 6.5, -6.5), (2.5, 8.5, -4.4), clo, ARM_MAIN, rot=("x", 22.5, (0, 8, -4.5)))
    elif kind == "noble":
        m.box((-4.4, 7.5, -4.4), (4.4, 9, 4.4), met, ARM_TRIM)
        for x, z in ((0, 4.2), (-4.2, 0), (4.2, 0), (0, -4.2), (-3, 3), (3, 3)):
            m.box((x - 0.5, 9, z - 0.5), (x + 0.5, 10.2, z + 0.5), met, ARM_TRIM)
        m.box((-0.6, 8, 4.3), (0.6, 9, 4.6), T["white"], ARM_MAIN)
    elif kind == "bone":
        shell(T["bone"], ARM_MAIN, top=9)
        for side in (1, -1):
            x = side * 4.2
            m.box((x - 0.8, 7, -1), (x + 0.8, 11, 1), T["bone"], ARM_TRIM, rot=("z", side * -22.5, (x, 7, 0)))
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- torso


def torso_base(b: dict) -> Model:
    m = Model()
    tw, th, td = b["tw"], b["th"], b["td"]
    hw, hd = tw / 2, td / 2
    m.box((-hw, 0, -hd), (hw, th, hd), T["cloth"], CLOTH)
    # Neckline (skin) and belt.
    m.box((-1.5, th - 1.5, hd), (1.5, th, hd + 0.05), T["skin"], SKIN)
    m.box((-hw - 0.15, 1.2, -hd - 0.15), (hw + 0.15, 2.3, hd + 0.15), T["belt"])
    m.box((-0.7, 1.1, hd + 0.1), (0.7, 2.4, hd + 0.3), T["buckle"])
    # Collar and hem trim in the trousers color.
    m.box((-hw - 0.1, th - 0.6, -hd - 0.1), (hw + 0.1, th, hd + 0.1), T["cloth"], PANTS)
    m.box((-hw - 0.12, 0, -hd - 0.12), (hw + 0.12, 0.6, hd + 0.12), T["cloth"], PANTS)
    if b["bust"]:
        m.box((-hw + 0.6, th - 5.5, hd), (hw - 0.6, th - 2.5, hd + 1.1), T["cloth"], CLOTH)
    return m


def torso_armor(kind: str, b: dict) -> Model:
    m = Model()
    tw, th, td = b["tw"], b["th"], b["td"]
    hw, hd = tw / 2 + 0.4, td / 2 + 0.4
    bust = b["bust"]
    met, lea, clo = T["metal"], T["leather"], T["cloth"]

    def shell(tex, tint, y0=0.5, y1=th + 0.2):
        m.box((-hw, y0, -hd), (hw, y1, hd), tex, tint)
        if bust:
            m.box((-hw + 0.7, th - 5.6, hd), (hw - 0.7, th - 2.3, hd + 1.0), tex, tint)

    if kind == "leather":
        shell(lea, ARM_MAIN, 1)
        m.box((-hw - 0.1, 1.2, -hd - 0.1), (hw + 0.1, 2.4, hd + 0.1), lea, ARM_TRIM)
        m.box((-0.4, 2.4, hd), (0.4, th, hd + 0.15), lea, ARM_TRIM)
    elif kind == "chain":
        shell(T["chain"], ARM_MAIN, -2)
        m.box((-hw - 0.1, 1.2, -hd - 0.1), (hw + 0.1, 2.4, hd + 0.1), lea, ARM_TRIM)
    elif kind == "scale":
        shell(met, ARM_MAIN, -1.5)
        for i in range(4):
            y = th - 1 - i * 2.4
            m.box((-hw - 0.1, y - 0.6, hd), (hw + 0.1, y, hd + 0.2), met, ARM_TRIM)
    elif kind == "plate":
        shell(met, ARM_MAIN, 2)
        m.box((-hw + 0.5, 4, hd), (hw - 0.5, th - 1, hd + 0.8), met, ARM_MAIN)
        m.box((-0.3, 4, hd + 0.8), (0.3, th - 1, hd + 1.0), met, ARM_TRIM)
        m.box((-hw - 0.2, 0, -hd - 0.2), (hw + 0.2, 2.2, hd + 0.2), met, ARM_TRIM)
        m.box((-hw, -3, -hd), (hw, 0, hd), T["chain"], ARM_MAIN)
    elif kind == "robe":
        shell(clo, ARM_MAIN, -1)
        m.box((-hw - 0.3, -10, -hd - 0.3), (hw + 0.3, 0, hd + 0.3), clo, ARM_MAIN)
        m.box((-1, -10, hd + 0.3), (1, th, hd + 0.45), clo, ARM_TRIM)
        m.box((-hw - 0.4, 1, -hd - 0.4), (hw + 0.4, 2, hd + 0.4), clo, ARM_TRIM)
    elif kind == "ranger":
        shell(lea, PANTS, 0.5)
        m.box((-hw - 0.3, -6, -hd - 1.0), (hw + 0.3, th + 0.5, -hd), clo, ARM_MAIN)
        m.box((-hw - 0.3, th - 1, -hd - 0.4), (hw + 0.3, th + 0.6, hd + 0.4), clo, ARM_MAIN)
        m.box((-hw + 1, th - 4, hd - 0.2), (-hw + 1.8, th + 0.2, hd + 0.3), lea, ARM_TRIM)
    elif kind == "noble":
        shell(clo, ARM_MAIN, -2)
        m.box((-hw - 0.3, -8, -hd - 0.9), (hw + 0.3, th + 0.4, -hd), clo, ARM_TRIM)
        m.box((-hw - 0.4, th - 1.2, -hd - 0.4), (hw + 0.4, th + 0.6, hd + 0.4), T["white"])
        for y in (3, 5.5, 8):
            m.box((-0.4, y, hd), (0.4, y + 0.8, hd + 0.2), met, ARM_TRIM)
    elif kind == "bone":
        shell(lea, ARM_MAIN, 1)
        for i in range(4):
            y = th - 2.5 - i * 2.2
            m.box((-hw + 0.5, y, hd), (hw - 0.5, y + 0.8, hd + 0.4), T["bone"], ARM_TRIM)
    else:
        raise ValueError(kind)
    return m


def tail(kind: str, b: dict) -> Model:
    m = Model()
    z = -b["td"] / 2
    f = T["fur"]
    if kind == "cat":
        m.box((-0.6, 0.8, z - 5), (0.6, 2, z), f, HAIR, rot=("x", -22.5, (0, 1.4, z)))
        m.box((-0.6, 1.6, z - 9), (0.6, 2.8, z - 4.3), f, HAIR, rot=("x", 45, (0, 2, z - 4.6)))
    elif kind == "wolf":
        m.box((-1.4, -1, z - 6), (1.4, 2, z), f, HAIR, rot=("x", 22.5, (0, 1.5, z)))
        m.box((-1.1, -4, z - 7), (1.1, -1, z - 4), f, HAIR, rot=("x", 22.5, (0, -1, z - 5)))
    elif kind == "bear":
        m.box((-1.2, 0.5, z - 1.8), (1.2, 2.5, z), f, HAIR)
    elif kind == "rabbit":
        m.box((-1.5, 0.3, z - 2.6), (1.5, 3.2, z), T["white"], HAIR)
    elif kind == "demon":
        m.box((-0.4, 0.6, z - 6), (0.4, 1.4, z), T["skin"], SKIN, rot=("x", 22.5, (0, 1, z)))
        m.box((-0.4, -3.5, z - 9), (0.4, -2.7, z - 4.5), T["skin"], SKIN, rot=("x", -22.5, (0, -3, z - 5)))
        m.box((-1.2, -4.0, z - 10.5), (1.2, -2.2, z - 8.8), T["bone"], HORN, rot=("x", 45, (0, -3, z - 9.5)))
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- limbs


def arm_base(b: dict) -> Model:
    """Arm hanging down from the shoulder pivot (0, 0, 0): top at y +2."""
    m = Model()
    aw, al = b["aw"], b["al"]
    h = aw / 2
    m.box((-h, 2 - al, -h), (h, 2, h), T["skin"], SKIN)
    m.box((-h - 0.2, -3.5, -h - 0.2), (h + 0.2, 2.2, h + 0.2), T["cloth"], CLOTH)
    return m


def arm_armor(kind: str, b: dict) -> Model:
    m = Model()
    aw, al = b["aw"], b["al"]
    h = aw / 2 + 0.35
    low = 2 - al
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    if kind == "leather":
        m.box((-h, low + 1, -h), (h, low + 5, h), lea, ARM_MAIN)
        m.box((-h - 0.1, low + 4.5, -h - 0.1), (h + 0.1, low + 5.2, h + 0.1), lea, ARM_TRIM)
    elif kind == "chain":
        m.box((-h, -4, -h), (h, 2.3, h), T["chain"], ARM_MAIN)
        m.box((-h, low + 0.8, -h), (h, low + 4, h), lea, ARM_TRIM)
    elif kind == "scale":
        m.box((-h - 0.4, -1, -h - 0.4), (h + 0.4, 3, h + 0.4), met, ARM_MAIN)
        m.box((-h, low + 1, -h), (h, low + 5, h), met, ARM_TRIM)
    elif kind == "plate":
        m.box((-h - 0.8, -1.5, -h - 0.6), (h + 0.8, 3.2, h + 0.6), met, ARM_MAIN)
        m.box((-h - 0.9, 1.6, -h - 0.7), (h + 0.9, 2.2, h + 0.7), met, ARM_TRIM)
        m.box((-h, -5, -h), (h, -1.5, h), met, ARM_MAIN)
        m.box((-h - 0.1, low, -h - 0.1), (h + 0.1, low + 5, h + 0.1), met, ARM_MAIN)
    elif kind == "robe":
        m.box((-h - 0.3, low + 2, -h - 0.3), (h + 0.3, 2.4, h + 0.3), clo, ARM_MAIN)
        m.box((-h - 0.9, low + 1.2, -h - 0.9), (h + 0.9, low + 3.2, h + 0.9), clo, ARM_TRIM)
    elif kind == "ranger":
        m.box((-h, low + 1, -h), (h, low + 5.5, h), lea, ARM_TRIM)
        m.box((-h - 0.2, -2, -h - 0.2), (h + 0.2, 2.4, h + 0.2), clo, ARM_MAIN)
    elif kind == "noble":
        m.box((-h, low + 3.5, -h), (h, 2.4, h), clo, ARM_MAIN)
        m.box((-h - 0.3, low + 3, -h - 0.3), (h + 0.3, low + 4, h + 0.3), T["white"])
    elif kind == "bone":
        m.box((-h - 0.6, -1, -h - 0.5), (h + 0.6, 3, h + 0.5), T["bone"], ARM_TRIM)
        m.box((-h, low + 1, -h), (h, low + 5, h), lea, ARM_MAIN)
    else:
        raise ValueError(kind)
    return m


def leg_base(b: dict) -> Model:
    """Leg hanging from the hip pivot (0, 0, 0)."""
    m = Model()
    lw, ll = b["lw"], b["ll"]
    h = lw / 2
    m.box((-h, -ll, -h), (h, 0, h), T["cloth"], PANTS)
    m.box((-h - 0.2, -ll, -h - 0.2), (h + 0.2, -ll + 3.5, h + 0.4), T["boot"])
    m.box((-h - 0.25, -ll + 3.2, -h - 0.25), (h + 0.25, -ll + 3.9, h + 0.45), T["belt"])
    return m


def leg_armor(kind: str, b: dict) -> Model:
    m = Model()
    lw, ll = b["lw"], b["ll"]
    h = lw / 2 + 0.35
    met, lea, clo = T["metal"], T["leather"], T["cloth"]
    if kind == "leather":
        m.box((-h, -ll + 3, -h), (h, -0.5, h), lea, ARM_MAIN)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 3.8, h + 0.5), lea, ARM_TRIM)
    elif kind == "chain":
        m.box((-h, -ll + 3, -h), (h, 0, h), T["chain"], ARM_MAIN)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 3.8, h + 0.5), lea, ARM_TRIM)
    elif kind == "scale":
        m.box((-h, -ll * 0.5, -h), (h, 0, h), met, ARM_MAIN)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 4.5, h + 0.5), met, ARM_TRIM)
    elif kind == "plate":
        m.box((-h, -ll * 0.55, -h), (h, 0, h), met, ARM_MAIN)
        m.box((-h - 0.3, -ll * 0.55 - 1, -h - 0.1), (h + 0.3, -ll * 0.55 + 0.6, h + 0.6), met, ARM_TRIM)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll * 0.55 - 1, h + 0.6), met, ARM_MAIN)
    elif kind == "robe":
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 3.5, h + 0.5), lea, ARM_TRIM)
    elif kind == "ranger":
        m.box((-h, -ll, -h), (h, -ll + 5.5, h + 0.3), lea, ARM_TRIM)
        m.box((-h - 0.05, -4, -h - 0.05), (h + 0.05, 0, h + 0.05), clo, ARM_MAIN)
    elif kind == "noble":
        m.box((-h, -ll + 3.5, -h), (h, 0, h), clo, ARM_MAIN)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 4, h + 0.5), T["leather"], ARM_TRIM)
    elif kind == "bone":
        m.box((-h, -ll * 0.5, -h), (h, -ll * 0.5 + 2.5, h + 0.4), T["bone"], ARM_TRIM)
        m.box((-h - 0.1, -ll, -h - 0.1), (h + 0.1, -ll + 3.8, h + 0.5), lea, ARM_MAIN)
    else:
        raise ValueError(kind)
    return m


# ---------------------------------------------------------------- write


def fmt(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def main() -> None:
    textures()
    n = lambda m, rel: model_node(m.save(rel))

    head_layers = [select_node(0, {"f": n(head_base(True), "body/head_f"), "df": n(head_base(True), "body/head_f")},
                               n(head_base(), "body/head"))]
    head_layers.append(select_node(1, {k: n(helmet(k), f"body/helmet_{k}") for k in ARMORS}))
    head_layers.append(select_node(2, {k: n(hair(k), f"body/hair_{k}") for k in HAIRS}))
    head_layers.append(select_node(3, {k: n(ears(k), f"body/ears_{k}") for k in EARS}))
    head_layers.append(select_node(4, {k: n(beard(k), f"body/beard_{k}") for k in BEARDS}))
    write_item("body/head", composite(*head_layers))

    torso_cases, arm_cases, leg_cases = {}, {}, {}
    for bid, b in BUILDS.items():
        torso_cases[bid] = composite(
            n(torso_base(b), f"body/{bid}/torso"),
            select_node(1, {k: n(torso_armor(k, b), f"body/{bid}/torso_{k}") for k in ARMORS}),
            select_node(2, {k: n(tail(k, b), f"body/{bid}/tail_{k}") for k in TAILS}))
        arm_cases[bid] = composite(
            n(arm_base(b), f"body/{bid}/arm"),
            select_node(1, {k: n(arm_armor(k, b), f"body/{bid}/arm_{k}") for k in ARMORS}))
        leg_cases[bid] = composite(
            n(leg_base(b), f"body/{bid}/leg"),
            select_node(1, {k: n(leg_armor(k, b), f"body/{bid}/leg_{k}") for k in ARMORS}))
    write_item("body/torso", select_node(0, torso_cases, torso_cases["m"]))
    # Inventory icons of armor pieces: the man's piece, posed for a slot.
    for slot, fn in (("head", lambda k: helmet(k)), ("torso", lambda k: torso_armor(k, BUILDS["m"])),
                     ("arm", lambda k: arm_armor(k, BUILDS["m"])), ("leg", lambda k: leg_armor(k, BUILDS["m"]))):
        cases = {}
        for k in ARMORS:
            m = fn(k)
            m.display = fit_gui(m)
            cases[k] = model_node(m.save(f"icon/armor_{slot}_{k}"))
        write_item(f"armor/{slot}", select_node(0, cases, cases["leather"]))
    write_item("body/arm", select_node(0, arm_cases, arm_cases["m"]))
    write_item("body/leg", select_node(0, leg_cases, leg_cases["m"]))

    # tc/rig_data.tc: per build, the pivots (model pixels, scale 1, feet at 0).
    lines = [
        "// Generated by pack/src/character.py: do not edit.",
        "// Rig pivots per build in model pixels (1/16 block at scale 1), feet at y 0.",
        "",
        "/** Per build: [hipY, hipX, neckY, shoulderX, shoulderY, armLen, legLen, torsoDepth]. */",
        "declare global rigBuild: dict[list];",
        "",
        "function loadRigData {",
        "    global rigBuild = {};",
    ]
    for bid, b in BUILDS.items():
        hip_y = b["ll"]
        neck_y = b["ll"] + b["th"]
        sh_y = neck_y - 2
        vals = [hip_y, b["hip"], neck_y, b["sh"], sh_y, b["al"], b["ll"], b["td"]]
        lines.append(f"    global rigBuild[\"{bid}\"] = [{', '.join(fmt(v) for v in vals)}];")
    lines += ["}", "",
              "/** Option lists for the character designer. */",
              "function rigOptions(kind: str): list[str] {"]
    for kind, vals in (("armor", ARMORS), ("hair", HAIRS), ("ears", EARS), ("beard", BEARDS), ("tail", TAILS)):
        lines.append(f"    if (kind == \"{kind}\") {{ return [{', '.join(repr(v).replace(chr(39), chr(34)) for v in vals)}]; }}")
    lines += ["    return [];", "}", ""]
    (ROOT / "tc/rig_data.tc").write_text("\n".join(lines))
    print(f"character: {len(BUILDS)} builds, {len(ARMORS)} armors, {len(HAIRS)} hair, {len(EARS)} ears, "
          f"{len(BEARDS)} beards, {len(TAILS)} tails")


if __name__ == "__main__":
    main()
