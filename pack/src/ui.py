#!/usr/bin/env python3
"""UI assets: hides the vanilla hearts, food, armor, air and XP bars (the
game draws its own health, mana and stamina), and adds the spell icon.

Overridden sprites are fully transparent images of the vanilla sizes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image

from common import ROOT, Model, fit_gui, make_texture, model_node, write_item

JAR = Path.home() / ".var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/libraries/com/mojang/minecraft/26.3/minecraft-26.3-client.jar"
HIDE = ("hud/heart/", "hud/food_", "hud/armor_", "hud/air", "hud/experience_bar_")


def hide_vanilla_hud() -> int:
    out = ROOT / "pack/assets/minecraft/textures/gui/sprites"
    n = 0
    with zipfile.ZipFile(JAR) as z:
        for name in z.namelist():
            pre = "assets/minecraft/textures/gui/sprites/"
            if name.startswith(pre) and name.endswith(".png") and any(name[len(pre):].startswith(h) for h in HIDE):
                with z.open(name) as f:
                    w, h = Image.open(f).size
                path = out / name[len(pre):]
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGBA", (w, h), (0, 0, 0, 0)).save(path)
                n += 1
    return n


def spell_icon() -> None:
    m = Model(1.0)
    glow = make_texture("icon_glow", "glow")
    white = make_texture("icon_white", "white")
    m.box((-5, -5, -5), (5, 5, 5), glow, 0, light=15, rot=("y", 45, (0, 0, 0)))
    m.box((-3, -3, -3), (3, 3, 3), white, light=15, rot=("x", 45, (0, 0, 0)))
    m.display = fit_gui(m, (20, 30, 20), 14)
    write_item("icon/spell", model_node(m.save("icon/spell")))


if __name__ == "__main__":
    print(f"ui: hid {hide_vanilla_hud()} vanilla HUD sprites")
    spell_icon()
