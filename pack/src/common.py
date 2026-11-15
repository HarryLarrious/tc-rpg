"""Shared helpers for the pack generators: model elements, textures, item
model definitions and file writing.

Model space convention (all generators): units are model pixels, the part's
pivot is the origin, +Y up, +Z the character's forward, +X the character's
left. `Model.json()` shifts everything by +8 so the pivot lands on the
item model center, which the item renderer puts at the display's origin.
tc/rig.tc multiplies by diag(-1, 1, -1) to undo the display's built-in
180 degree turn, so these axes come out as written.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "pack/assets/rpg"
NS = "rpg"

# Every generated "minecraft:model" node gets this tint list: tint index i
# reads custom model data color i (white when the item has none).
TINT_COUNT = 8


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n")


def rnd(x: float) -> float:
    r = round(x, 4)
    return 0.0 if r == 0 else r


# ---------------------------------------------------------------- textures

TEX_SIZE = 32


def _noise(rng: random.Random, w: int, h: int, amp: float) -> list[list[float]]:
    return [[rng.uniform(-amp, amp) for _ in range(w)] for _ in range(h)]


def make_texture(name: str, kind: str, seed: int = 0, rgb: tuple | None = None) -> str:
    """Writes a grayscale (tinted later) or colored 32 x 32 texture and
    returns its resource id."""
    rng = random.Random(f"{name}{seed}")
    n = TEX_SIZE
    img = Image.new("RGBA", (n, n))
    px = img.load()
    for y in range(n):
        for x in range(n):
            if kind == "skin":
                v = 235 + rng.uniform(-6, 6)
            elif kind == "cloth":
                weave = 8 if (x + y) % 2 == 0 else -8
                v = 210 + weave + rng.uniform(-10, 10) - (14 if y % 8 == 0 else 0)
            elif kind == "leather":
                v = 200 + rng.uniform(-22, 22) - (30 if (x % 11 == 0 or y % 13 == 0) else 0)
            elif kind == "metal":
                band = 20 * math.sin((x + y * 0.3) * 0.5)
                v = 205 + band + rng.uniform(-8, 8) + (30 if (x + y) % 15 == 0 else 0)
            elif kind == "chain":
                v = 230 if (x % 3 != 0 and y % 2 == (x // 3) % 2) else 120
                v += rng.uniform(-10, 10)
            elif kind == "hair":
                strand = 25 * math.sin(x * 1.7 + rng.uniform(0, 0.6))
                v = 205 + strand + rng.uniform(-12, 12)
            elif kind == "fur":
                v = 210 + rng.uniform(-30, 25)
            elif kind == "wood":
                grain = 22 * math.sin(y * 0.9 + 3 * math.sin(x * 0.4))
                v = 190 + grain + rng.uniform(-10, 10)
            elif kind == "gem":
                cx, cy = x - n / 2, y - n / 2
                v = 255 - 3 * math.hypot(cx, cy) + rng.uniform(-5, 5)
            elif kind == "glow":
                v = 255
            elif kind == "white":
                v = 250
            elif kind == "dark":
                v = 40 + rng.uniform(-6, 6)
            elif kind == "bone":
                v = 225 + rng.uniform(-15, 10) - (25 if y % 9 == 0 else 0)
            else:
                raise ValueError(kind)
            g = max(0, min(255, int(v)))
            if rgb:
                px[x, y] = tuple(int(g * c / 255) for c in rgb) + (255,)
            else:
                px[x, y] = (g, g, g, 255)
    path = ASSETS / "textures/item" / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return f"{NS}:item/{name}"


def make_slash_texture(name: str) -> str:
    """A soft white streak, bright at one edge, fading out (for slash arcs)."""
    n = TEX_SIZE
    img = Image.new("RGBA", (n, n))
    px = img.load()
    for y in range(n):
        for x in range(n):
            t = y / (n - 1)
            a = int(255 * max(0.0, 1 - t) ** 1.6)
            fade = min(1.0, x / 6, (n - 1 - x) / 6)
            px[x, y] = (255, 255, 255, int(a * max(0.0, fade)))
    path = ASSETS / "textures/item" / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return f"{NS}:item/{name}"


# ---------------------------------------------------------------- models

FACES = ("north", "south", "east", "west", "up", "down")


class Model:
    """A block model built from boxes, in model pixels around the pivot."""

    def __init__(self, k: float = 1.0) -> None:
        """k scales every coordinate (0.5: half-size pixels for long items)."""
        self.elements: list[dict] = []
        self.textures: dict[str, str] = {}
        self.k = k
        self.display: dict = {}

    def tex(self, tex_id: str) -> str:
        for k, v in self.textures.items():
            if v == tex_id:
                return k
        key = f"t{len(self.textures)}"
        self.textures[key] = tex_id
        return key

    def box(self, a, b, tex: str, tint: int | None = None, rot=None, light: int = 0,
            faces=FACES, uv_seed: int = 0) -> None:
        """Adds the box from corner a to corner b. rot = (axis, angle,
        origin) with angle a multiple of 22.5 in -45..45."""
        a = [x * self.k for x in a]
        b = [x * self.k for x in b]
        lo = [min(a[i], b[i]) for i in range(3)]
        hi = [max(a[i], b[i]) for i in range(3)]
        key = self.tex(tex)
        size = [hi[i] - lo[i] for i in range(3)]
        rng = random.Random(len(self.elements) * 7919 + uv_seed)
        fd = {}
        for f in faces:
            if f in ("north", "south"):
                w, h = size[0], size[1]
            elif f in ("east", "west"):
                w, h = size[2], size[1]
            else:
                w, h = size[0], size[2]
            # One texture pixel per model pixel on a 32 px texture (uv units
            # are 1/16 of the texture).
            uw, uh = min(16.0, max(0.25, w / 2)), min(16.0, max(0.25, h / 2))
            u0 = rng.uniform(0, 16 - uw)
            v0 = rng.uniform(0, 16 - uh)
            face = {"uv": [rnd(u0), rnd(v0), rnd(u0 + uw), rnd(v0 + uh)], "texture": "#" + key}
            if tint is not None:
                face["tintindex"] = tint
            fd[f] = face
        el = {"from": [rnd(x + 8) for x in lo], "to": [rnd(x + 8) for x in hi], "faces": fd}
        if rot is not None:
            axis, angle, origin = rot
            el["rotation"] = {"angle": angle, "axis": axis, "origin": [rnd(o * self.k + 8) for o in origin]}
        if light:
            el["light_emission"] = light
        self.elements.append(el)

    def json(self) -> dict:
        for el in self.elements:
            for c in el["from"] + el["to"]:
                if not -16 <= c <= 32:
                    raise ValueError(f"element out of bounds: {el['from']} {el['to']}")
        out = {"textures": dict(self.textures, particle=next(iter(self.textures.values()))),
               "elements": self.elements}
        if self.display:
            out["display"] = self.display
        return out

    def save(self, rel: str) -> str:
        """Writes models/<rel>.json and returns its model id."""
        write_json(ASSETS / "models" / f"{rel}.json", self.json())
        return f"{NS}:{rel}"


# ---------------------------------------------------------------- item model definitions


def model_node(model_id: str) -> dict:
    return {"type": "minecraft:model", "model": model_id,
            "tints": [{"type": "minecraft:custom_model_data", "index": i, "default": 16777215}
                      for i in range(TINT_COUNT)]}


EMPTY = {"type": "minecraft:empty"}


def select_node(index: int, cases: dict[str, dict], fallback: dict | None = None) -> dict:
    node = {"type": "minecraft:select", "property": "minecraft:custom_model_data", "index": index,
            "cases": [{"when": k, "model": v} for k, v in cases.items()]}
    node["fallback"] = fallback if fallback is not None else EMPTY
    return node


def composite(*models: dict) -> dict:
    return {"type": "minecraft:composite", "models": list(models)}


def write_item(rel: str, node: dict) -> str:
    """Writes items/<rel>.json and returns the item model id."""
    write_json(ASSETS / "items" / f"{rel}.json", {"model": node})
    return f"{NS}:{rel}"


def fit_gui(m: "Model", rotation=(30, 225, 0), fill: float = 15.0) -> dict:
    """GUI display transform that scales and centers the model's bounding
    box in a slot (rotation as in block icons)."""
    xs = [c for el in m.elements for c in (el["from"][0], el["to"][0])]
    ys = [c for el in m.elements for c in (el["from"][1], el["to"][1])]
    zs = [c for el in m.elements for c in (el["from"][2], el["to"][2])]
    ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1)
    s = min(1.8, fill / ext)
    c = [(max(v) + min(v)) / 2 - 8 for v in (xs, ys, zs)]
    rx, ry, _ = (math.radians(a) for a in rotation)
    # Rotate the center offset (Y then X, as the display applies them).
    x, y, z = c
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    t = [round(max(-80, min(80, -x * s)), 2), round(max(-80, min(80, -y * s)), 2), 0]
    return {"gui": {"rotation": list(rotation), "translation": t, "scale": [round(s, 3)] * 3}}
