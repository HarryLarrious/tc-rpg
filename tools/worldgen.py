#!/usr/bin/env python3
"""Mirror of the plot's world generator (tc/world*.tc), for previews.

Runs the same planning algorithm as the plot code from the same seed and
draws map/preview.png: terrain, river, roads, wall, buildings by type,
farms and points of interest. Keep it in step with tc/world_plan.tc.

    python3 tools/worldgen.py [--seed 7341] [--size 1001]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

M = 1000003


def hsh(x: int, z: int, s: int) -> int:
    """Integer hash, 0..M-1 (same integer steps as worldHash in TC)."""
    h = (x * 374761 + z * 668265 + s * 1013 + 7) % M
    h = (h * h + 12345) % M
    h = (h * h + 6789) % M
    return h


def r01(x, z, s):
    return (hsh(x, z, s) % 1000) / 1000


def smooth(t):
    return t * t * (3 - 2 * t)


def vnoise(x, z, cell, salt, seed):
    ix, iz = math.floor(x / cell), math.floor(z / cell)
    fx, fz = smooth(x / cell - ix), smooth(z / cell - iz)
    a = r01(ix, iz, seed + salt)
    b = r01(ix + 1, iz, seed + salt)
    c = r01(ix, iz + 1, seed + salt)
    d = r01(ix + 1, iz + 1, seed + salt)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fz


class Plan:
    def __init__(self, seed: int, size: int):
        self.seed, self.S = seed, size
        S = size
        self.k = S / 1001
        self.cx = S // 2 + (hsh(1, 2, seed) % 41) - 20
        self.cz = S // 2 + (hsh(3, 4, seed) % 41) - 20
        self.R = round(118 * min(1.0, self.k * 1.5) if S < 1001 else 118)
        self.rot = hsh(5, 6, seed) % 90
        self.roads: list[tuple] = []        # (x1, z1, x2, z2, width, kind)
        self.wall: list[tuple] = []          # polygon points
        self.gates: list[tuple] = []         # (x, z, angle)
        self.blds: list[dict] = []           # buildings
        self.farms: list[tuple] = []         # (x0, z0, x1, z1)
        self.pois: dict[str, tuple] = {}
        self.village = None

    # ------------------------------------------------------------ terrain

    def river_x(self, z):
        return self.cx - (self.R + 38) + 22 * math.sin((z - self.cz) / 83) + 9 * math.sin((z + self.seed) / 31)

    def height(self, x, z):
        s = self.seed
        hills = 0.6 * vnoise(x, z, 96, 11, s) + 0.3 * vnoise(x, z, 37, 23, s) + 0.1 * vnoise(x, z, 13, 37, s)
        de = min(x, z, self.S - 1 - x, self.S - 1 - z)
        mount = max(0.0, (70 - de) / 70) ** 2 * 38
        k = 1.0
        for (sx, sz, sr) in self.flats():
            dc = math.hypot(x - sx, z - sz)
            k = min(k, smooth(min(1.0, max(0.0, (dc - sr - 20) / 60))))
        h = 51 + (hills * 20 + mount) * k + (1 - k) * 1
        dr = abs(x - self.river_x(z))
        if dr < 24:
            bank = 48 + (dr - 5) * 0.75
            h = min(h, bank) if dr >= 5 else 45 + dr * 0.3
        lx, lz, lr = self.pois.get("lake", (0, 0, 0))
        if lr:
            dl = math.hypot(x - lx, z - lz) / lr + 0.25 * (vnoise(x, z, 17, 41, s) - 0.5)
            if dl < 1.25:
                h = min(h, 44 + dl * 4.5)
        return round(h)

    def flats(self):
        out = [(self.cx, self.cz, self.R)]
        if self.village:
            out.append((self.village[0], self.village[1], self.village[2]))
        return out

    def plan_village(self):
        """The village sits at the end of the country road that points away
        from every point of interest."""
        best, bk = -1, 0
        for k in range(4):
            ang = self.rot + k * 90 + (hsh(k, 77, self.seed) % 25) - 12
            dmin = 999
            for name, (x, z, r) in self.pois.items():
                a2 = math.degrees(math.atan2(z - self.cz, x - self.cx))
                d = abs((ang - a2 + 180) % 360 - 180)
                dmin = min(dmin, d)
            # Not across the river (west of town).
            if math.cos(math.radians(ang)) < -0.5:
                dmin = -1
            if dmin > best:
                best, bk = dmin, k
        ang = math.radians(self.rot + bk * 90 + (hsh(bk, 77, self.seed) % 25) - 12)
        reach = min(self.cx, self.cz, self.S - self.cx, self.S - self.cz) - 60
        d = self.wall_r(ang) + min(reach * 0.62, 240)
        self.village = (self.cx + math.cos(ang) * d, self.cz + math.sin(ang) * d, 40, bk)

    # ------------------------------------------------------------ roads

    def wall_r(self, ang):
        return self.R + 7 * (vnoise((ang + 10) * 3, 0, 40, 51, self.seed) - 0.5) * 2

    def curve(self, x1, z1, x2, z2, n, amp, salt, width, kind):
        """Adds a road from (x1, z1) to (x2, z2) as n segments bent sideways
        by two sine waves of amplitude amp."""
        dx, dz = x2 - x1, z2 - z1
        L = math.hypot(dx, dz)
        nx, nz = -dz / L, dx / L
        ph = (hsh(salt, 9, self.seed) % 628) / 100
        pts = []
        for i in range(n + 1):
            t = i / n
            off = amp * math.sin(t * math.pi) * math.sin(t * 2.3 + ph)
            pts.append((x1 + dx * t + nx * off, z1 + dz * t + nz * off))
        for a, b in zip(pts, pts[1:]):
            self.roads.append((a[0], a[1], b[0], b[1], width, kind))
        return pts

    def plan_roads(self):
        cx, cz, R = self.cx, self.cz, self.R
        P = 15  # plaza half side
        # Plaza edges count as roads (buildings face the square).
        for (a, b) in (((-P, -P), (P, -P)), ((P, -P), (P, P)), ((P, P), (-P, P)), ((-P, P), (-P, -P))):
            self.roads.append((cx + a[0], cz + a[1], cx + b[0], cz + b[1], 3, "plaza"))
        # Main streets to four gates and on into the country.
        for i in range(4):
            ang = math.radians(self.rot + i * 90 + (hsh(i, 77, self.seed) % 25) - 12)
            ux, uz = math.cos(ang), math.sin(ang)
            sx, sz = cx + ux * P * 1.4, cz + uz * P * 1.4
            gr = self.wall_r(ang)
            gx, gz = cx + ux * gr, cz + uz * gr
            self.curve(sx, sz, gx, gz, 6, 7, 100 + i, 5, "main")
            self.gates.append((gx, gz, ang))
            # Country road from the gate toward the plot edge.
            reach = min(cx, cz, self.S - cx, self.S - cz) - 60
            ex, ez = cx + ux * (gr + reach * 0.85), cz + uz * (gr + reach * 0.85)
            ex = min(max(ex, 40), self.S - 40)
            ez = min(max(ez, 40), self.S - 40)
            if self.village and self.village[3] == i:
                ex, ez = self.village[0], self.village[1]
            self.curve(gx + ux * 2, gz + uz * 2, ex, ez, 10, 26, 200 + i, 4, "country")
        # Ring street.
        n = 28
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            r = R * 0.6 + 6 * (vnoise(i * 7, 3, 9, 61, self.seed) - 0.5)
            ring.append((cx + math.cos(a) * r, cz + math.sin(a) * r))
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            self.roads.append((a[0], a[1], b[0], b[1], 4, "ring"))
        # Wall street: just inside the wall, between the gates.
        n2 = 36
        inner = []
        for i in range(n2):
            a = 2 * math.pi * i / n2
            r = self.wall_r(a) - 9
            inner.append((cx + math.cos(a) * r, cz + math.sin(a) * r))
        for i in range(n2):
            a, b = inner[i], inner[(i + 1) % n2]
            self.roads.append((a[0], a[1], b[0], b[1], 3, "wallst"))
        # Lanes: between the main streets, from near the plaza to the ring,
        # and from the ring out toward the wall.
        for i in range(4):
            for j, frac in enumerate((0.33, 0.67)):
                ang = math.radians(self.rot + i * 90 + 90 * frac + (hsh(i, j, self.seed + 5) % 15) - 7)
                ux, uz = math.cos(ang), math.sin(ang)
                if j == 0:
                    self.curve(cx + ux * 27, cz + uz * 27, cx + ux * R * 0.6, cz + uz * R * 0.6, 3, 3, 300 + i * 2 + j, 3, "lane")
                ang2 = ang + math.radians(((hsh(i, j, self.seed + 9) % 20) - 10))
                ux2, uz2 = math.cos(ang2), math.sin(ang2)
                self.curve(cx + ux2 * R * 0.6, cz + uz2 * R * 0.6, cx + ux2 * (self.wall_r(ang2) - 9),
                           cz + uz2 * (self.wall_r(ang2) - 9), 3, 3, 400 + i * 2 + j, 3, "lane")
                if j == 1:
                    ang3 = ang + math.radians(22)
                    ux3, uz3 = math.cos(ang3), math.sin(ang3)
                    self.curve(cx + ux3 * 30, cz + uz3 * 30, cx + ux3 * R * 0.6, cz + uz3 * R * 0.6, 3, 4, 500 + i, 3, "lane")

    def plan_village_roads(self):
        vx, vz, VR, _ = self.village
        P = 7
        for (a, b) in (((-P, -P), (P, -P)), ((P, -P), (P, P)), ((P, P), (-P, P)), ((-P, P), (-P, -P))):
            self.roads.append((vx + a[0], vz + a[1], vx + b[0], vz + b[1], 3, "vplaza"))
        for i in range(4):
            ang = math.radians(self.rot + 45 + i * 90 + (hsh(i, 31, self.seed) % 20) - 10)
            ux, uz = math.cos(ang), math.sin(ang)
            self.curve(vx + ux * 10, vz + uz * 10, vx + ux * VR * 0.95, vz + uz * VR * 0.95, 4, 4, 600 + i, 4, "vmain")
        n = 16
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            r = VR * 0.62 + 4 * (vnoise(i * 5, 7, 9, 63, self.seed) - 0.5)
            ring.append((vx + math.cos(a) * r, vz + math.sin(a) * r))
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            self.roads.append((a[0], a[1], b[0], b[1], 3, "vring"))

    def plan_wall(self):
        n = 18
        for i in range(n):
            a = 2 * math.pi * i / n
            r = self.wall_r(a)
            self.wall.append((self.cx + math.cos(a) * r, self.cz + math.sin(a) * r))

    # ------------------------------------------------------------ lots

    @staticmethod
    def seg_dist(px, pz, x1, z1, x2, z2):
        dx, dz = x2 - x1, z2 - z1
        L2 = dx * dx + dz * dz
        t = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (pz - z1) * dz) / L2))
        return math.hypot(px - (x1 + dx * t), pz - (z1 + dz * t))

    def rect_ok(self, x0, z0, x1, z1, inside=True, sid=1):
        cx, cz = self.cx, self.cz
        if sid == 2:
            vx, vz, VR, _ = self.village
            mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
            if inside and max(math.hypot(px - vx, pz - vz) for px, pz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1))) > VR:
                return False
            if abs(mx - vx) < 9 + (x1 - x0) / 2 and abs(mz - vz) < 9 + (z1 - z0) / 2:
                return False
            return self.rect_free(x0, z0, x1, z1)
        pts = [(x0, z0), (x1, z0), (x0, z1), (x1, z1), ((x0 + x1) / 2, (z0 + z1) / 2),
               ((x0 + x1) / 2, z0), ((x0 + x1) / 2, z1), (x0, (z0 + z1) / 2), (x1, (z0 + z1) / 2)]
        if inside:
            for px, pz in pts[:4]:
                ang = math.atan2(pz - cz, px - cx)
                if math.hypot(px - cx, pz - cz) > self.wall_r(ang) - 5:
                    return False
        if abs((x0 + x1) / 2 - cx) < 17 + (x1 - x0) / 2 and abs((z0 + z1) / 2 - cz) < 17 + (z1 - z0) / 2:
            return False
        return self.rect_free(x0, z0, x1, z1)

    def rect_free(self, x0, z0, x1, z1):
        pts = [(x0, z0), (x1, z0), (x0, z1), (x1, z1), ((x0 + x1) / 2, (z0 + z1) / 2),
               ((x0 + x1) / 2, z0), ((x0 + x1) / 2, z1), (x0, (z0 + z1) / 2), (x1, (z0 + z1) / 2)]
        for (a, b, c, d, w, kind) in self.roads:
            lim = w / 2 + 0.6
            for px, pz in pts:
                if self.seg_dist(px, pz, a, b, c, d) < lim:
                    return False
            # Road crossing the rectangle between the sample points.
            mx, mz = (a + c) / 2, (b + d) / 2
            if x0 - 1 <= mx <= x1 + 1 and z0 - 1 <= mz <= z1 + 1:
                return False
        for o in self.blds:
            if x0 < o["x1"] + 1 and x1 > o["x0"] - 1 and z0 < o["z1"] + 1 and z1 > o["z0"] - 1:
                return False
        return True

    def lot_rect(self, a, b, c, dd, rw, t, side, w, d):
        """Rectangle for a w (frontage) x d lot beside the road a-b..c-dd at
        t, on `side`: its center sits along the road's normal far enough
        that the near corners clear the road. Returns (x0, z0, x1, z1,
        facing)."""
        px, pz = a + (c - a) * t, b + (dd - b) * t
        L = math.hypot(c - a, dd - b)
        nx, nz = -(dd - b) / L * side, (c - a) / L * side
        horiz = abs(c - a) >= abs(dd - b)
        bw, bd = (w, d) if horiz else (d, w)
        ext = abs(nx) * bw / 2 + abs(nz) * bd / 2
        gap = rw / 2 + 1 + ext
        mx, mz = px + nx * gap, pz + nz * gap
        x0, z0 = math.floor(mx - bw / 2 + 0.5), math.floor(mz - bd / 2 + 0.5)
        if abs(nx) > abs(nz):
            facing = "west" if nx > 0 else "east"
        else:
            facing = "north" if nz > 0 else "south"
        return x0, z0, x0 + bw - 1, z0 + bd - 1, facing

    def try_lot(self, a, b, c, dd, rw, t, side, w, d, btype, h, inside=True, sid=1):
        x0, z0, x1, z1, facing = self.lot_rect(a, b, c, dd, rw, t, side, w, d)
        if not self.rect_ok(x0, z0, x1, z1, inside, sid):
            return None
        bld = {"type": btype, "x0": x0, "z0": z0, "x1": x1, "z1": z1, "facing": facing,
               "floors": 1 + (h // 37) % 3, "sid": sid}
        self.blds.append(bld)
        return bld

    def place_along(self, kinds, btype, w, d, salt, t_from=0.0, t_to=1.0, tries=60, inside=True, sid=1):
        """Finds a lot for a w x d building fronting a road of one of the
        kinds; returns the building or None."""
        segs = [r for r in self.roads if r[5] in kinds]
        if not segs:
            return None
        for k in range(tries):
            h = hsh(salt, k, self.seed)
            a, b, c, dd, rw, kind = segs[h % len(segs)]
            t = t_from + (t_to - t_from) * ((h // 7) % 100) / 100
            side = 1 if (h // 701) % 2 else -1
            bld = self.try_lot(a, b, c, dd, rw, t, side, w, d, btype, h, inside, sid)
            if bld:
                return bld
        return None

    def plan_lots(self):
        special = [
            ("keep", 21, 17, ("ring", "main")), ("guild", 15, 11, ("plaza",)), ("inn", 13, 11, ("plaza",)),
            ("library", 13, 11, ("plaza", "main")), ("armory", 11, 9, ("plaza", "main")),
            ("blacksmith", 11, 9, ("main",)), ("chapel", 15, 9, ("main", "ring")), ("tavern", 11, 9, ("main",)),
            ("alchemist", 9, 7, ("main", "ring")), ("store", 9, 9, ("plaza", "main")), ("bakery", 9, 7, ("ring",)),
            ("magetower", 9, 9, ("ring",)), ("barracks", 15, 9, ("main",)), ("stables", 13, 9, ("main",)),
        ]
        for i, (bt, w, d, kinds) in enumerate(special):
            t_from, t_to = (0.0, 1.0)
            if bt in ("barracks", "stables"):
                t_from = 0.6
            b = self.place_along(kinds, bt, w, d, 1000 + i, t_from, t_to, 200)
            if b is None:
                b = self.place_along(("main", "ring", "lane"), bt, w, d, 2000 + i, 0, 1, 300)
            if b is not None and bt in ("keep", "chapel", "magetower", "guild", "inn"):
                b["floors"] = {"keep": 3, "chapel": 1, "magetower": 5, "guild": 2, "inn": 3}[bt]
        # Houses: march along both sides of every street, packing lots.
        n = 0
        for si, seg in enumerate(list(self.roads)):
            a, b, c, dd, rw, kind = seg
            if kind not in ("main", "ring", "lane", "plaza", "wallst"):
                continue
            L = math.hypot(c - a, dd - b)
            for side in (1, -1):
                pos = 1.0
                while pos < L - 3:
                    h = hsh(si * 2 + (side > 0), int(pos), self.seed + 3)
                    w = 7 + (h % 3) * 2
                    d = 7 + ((h // 3) % 3) * 2
                    t = (pos + w / 2) / L
                    if t > 1:
                        break
                    if self.try_lot(a, b, c, dd, rw, t, side, w, d, "house", h):
                        n += 1
                        pos += w + 1
                    else:
                        pos += 2
        # The village: its own six required buildings and houses.
        vspecial = [("keep", 13, 11), ("guild", 11, 9), ("inn", 11, 9), ("library", 9, 9), ("armory", 9, 7), ("blacksmith", 9, 7)]
        for i, (bt, w, d) in enumerate(vspecial):
            b = self.place_along(("vplaza", "vmain"), bt, w, d, 3000 + i, 0, 1, 200, sid=2)
            if b is None:
                b = self.place_along(("vring", "vmain"), bt, w, d, 3100 + i, 0, 1, 300, sid=2)
            if b is not None:
                b["floors"] = 2
        for si, seg in enumerate(list(self.roads)):
            a, b, c, dd, rw, kind = seg
            if kind not in ("vmain", "vring", "vplaza"):
                continue
            L = math.hypot(c - a, dd - b)
            for side in (1, -1):
                pos = 1.0
                while pos < L - 3:
                    h = hsh(si * 2 + (side > 0), int(pos), self.seed + 4)
                    w = 7 + (h % 2) * 2
                    d = 7 + ((h // 3) % 2) * 2
                    t = (pos + w / 2) / L
                    if t > 1:
                        break
                    if self.try_lot(a, b, c, dd, rw, t, side, w, d, "house", h, True, 2):
                        pos += w + 2
                    else:
                        pos += 2
        # Farms outside: along the country roads near the gates.
        nf = 0
        for k in range(60):
            if nf >= 16:
                break
            h = hsh(k, 66, self.seed)
            w, d = 13 + h % 9, 17 + (h // 9) % 9
            b = self.place_along(("country",), "farm", w, d, 7000 + k, 0.02, 0.4, 2, inside=False)
            if b:
                nf += 1
            if b:
                dc = math.hypot((b["x0"] + b["x1"]) / 2 - self.cx, (b["z0"] + b["z1"]) / 2 - self.cz)
                dv = math.hypot((b["x0"] + b["x1"]) / 2 - self.village[0], (b["z0"] + b["z1"]) / 2 - self.village[1])
                if dc < self.R + 10 or dv < self.village[2] + 14 or abs((b["x0"] + b["x1"]) / 2 - self.river_x((b["z0"] + b["z1"]) / 2)) < 16:
                    self.blds.remove(b)
                    nf -= 1
        return n

    def plan_pois(self):
        s, S = self.seed, self.S
        # Lake: east of town.
        ang = math.radians(self.rot + 45 + hsh(7, 7, s) % 30)
        d = self.R + 140
        self.pois["lake"] = (self.cx + math.cos(ang) * d, self.cz + math.sin(ang) * d, 34)
        for i, name in enumerate(("camp", "ruins", "cave", "grove")):
            a = math.radians(self.rot + 135 + i * 90 + hsh(i, 88, s) % 30)
            dd = self.R + 180 + hsh(i, 99, s) % 80
            x = min(max(self.cx + math.cos(a) * dd, 70), S - 70)
            z = min(max(self.cz + math.sin(a) * dd, 70), S - 70)
            self.pois[name] = (x, z, 18)

    def run(self):
        self.plan_pois()
        self.plan_village()
        self.plan_wall()
        self.plan_roads()
        self.plan_village_roads()
        houses = self.plan_lots()
        return houses


COLORS = {
    "keep": (150, 40, 40), "guild": (200, 120, 30), "inn": (230, 180, 60), "library": (60, 90, 200),
    "armory": (120, 120, 140), "blacksmith": (60, 60, 60), "chapel": (240, 240, 240), "tavern": (180, 90, 40),
    "alchemist": (150, 60, 200), "store": (60, 160, 60), "bakery": (220, 160, 120), "magetower": (90, 40, 160),
    "barracks": (110, 30, 30), "stables": (140, 100, 60), "house": (185, 150, 110), "farm": (200, 200, 70),
}


def draw(plan: Plan, out: Path):
    S = plan.S
    img = Image.new("RGB", (S, S))
    px = img.load()
    for z in range(0, S):
        for x in range(0, S):
            h = plan.height(x, z)
            if h < 49:
                px[x, z] = (40, 90, 170)
            else:
                g = min(255, 60 + (h - 49) * 6)
                px[x, z] = (60 + (h - 49) * 3, g, 50) if h < 75 else (150, 150, 150)
    d = ImageDraw.Draw(img)
    for (a, b, c, e, w, kind) in plan.roads:
        col = (150, 130, 100) if kind != "country" else (170, 150, 110)
        d.line((a, b, c, e), fill=col, width=max(1, int(w)))
    d.line(plan.wall + [plan.wall[0]], fill=(90, 90, 90), width=3)
    for b in plan.blds:
        d.rectangle((b["x0"], b["z0"], b["x1"], b["z1"]), fill=COLORS[b["type"]], outline=(30, 20, 10))
    for name, (x, z, r) in plan.pois.items():
        d.ellipse((x - 6, z - 6, x + 6, z + 6), outline=(255, 0, 0), width=2)
        d.text((x + 8, z - 6), name, fill=(255, 255, 255))
    vx, vz, VR, _ = plan.village
    d.text((vx + VR, vz), "village", fill=(255, 255, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    # A close-up of the town.
    R = plan.R + 20
    img.crop((plan.cx - R, plan.cz - R, plan.cx + R, plan.cz + R)).resize((R * 6, R * 6), Image.NEAREST).save(
        out.with_name("town.png"))
    vx, vz, VR, _ = plan.village
    V = VR + 25
    img.crop((int(vx - V), int(vz - V), int(vx + V), int(vz + V))).resize((V * 8, V * 8), Image.NEAREST).save(
        out.with_name("village.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7341)
    ap.add_argument("--size", type=int, default=1001)
    a = ap.parse_args()
    p = Plan(a.seed, a.size)
    houses = p.run()
    counts = {}
    for b in p.blds:
        counts[b["type"]] = counts.get(b["type"], 0) + 1
    print(f"seed {a.seed}: center ({p.cx}, {p.cz}) R {p.R}, {len(p.roads)} road segments, buildings {counts}")
    draw(p, ROOT / "map/preview.png")


if __name__ == "__main__":
    main()
