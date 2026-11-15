# tc-rpg design plan

A third-person fantasy-medieval RPG for DiamondFire, written in Terracotta.
Plot 35000113 (Mega, 1001 x 1001 build area, 300 x 300 code space).
Target client: Minecraft 26.3, resource pack format 97.1.

This file is the source of truth for design decisions. Update it when a
design fact changes.

## Pillars

1. **Looks good**: every visible thing that matters (characters, weapons,
   armor, spell effects, slashes) is a custom model from the pack. The world
   is built from vanilla blocks by the plot code itself.
2. **Easy to pick up**: left click attacks, right click is the weapon's heavy
   move, Shift dodges, number keys cast. Everything else is a menu.
3. **Procedural**: the world, the towns, the loot and the spells are all
   generated from rules and a seed, not hand placed.

## Camera and the player's body (third person)

DiamondFire cannot force the F5 camera, so the game builds its own:

- The **body** is an invisible armor stand. The game sets its velocity
  every tick from the player's keys, so vanilla physics does the gravity,
  block collision and step-up. Enemies and spells hit the body.
- The **camera** is the real player, riding an interaction entity (the
  "boom") that the game moves every tick to a point behind and above the
  body, along the player's look direction. A raycast pulls the boom in
  when a wall is in the way. The rider's look is free, so the mouse
  controls the camera like any third-person game.
- The **model** is the custom character rig (below), drawn at the body.
- Input while riding: `steerForwardMovement` / `steerSidewaysMovement`
  (W/S, A/D), `movementKeyChange` (Space, Shift, Ctrl), clicks, hotbar
  changes, F (swap hands) and Q (drop).
- The real player is invisible and hidden from other players.

| Key | Action |
| --- | --- |
| W A S D | Move, relative to the camera |
| Space | Jump |
| Ctrl | Sprint (uses stamina) |
| Shift | Dodge roll (invulnerable for a moment, uses stamina) |
| Left click | Light attack; chained clicks make a combo |
| Right click | Heavy attack / weapon skill (bow: aimed shot, shield: block) |
| 1-8 | Cast the spell or ability in that slot |
| F | Interact: talk, open doors, loot, read signs |
| Q | Lock on to the nearest enemy (Q again to release) |
| 9 / Journal item | Character, inventory, spells, quests, map |

## Character rig

Every character (players and NPCs) is 6 body-part item displays plus 2
held-item displays: head, torso, two arms and two legs. The style is
blocky with classic proportions (an 8 px head, 12 px torso, arms and legs
for the tall builds): one-piece limbs, a plain face (no nose) and flat,
paper-thin ears. Arms are classic (4 px) or slim (3 px), a choice in the
character designer (`app["arms"]`; the arm item's build string gets an `s`
for slim). Each part item uses one item model
(`rpg:body/<part>`: head, torso, arm, leg) that is a **composite** of layers
picked by the item's custom model data strings and colored by its custom
model data colors:

| String index | Layer |
| --- | --- |
| 0 | build: `m`, `f`, `dm`, `df` (dwarf builds are short and stocky) |
| 1 | armor piece on this part (`leather`, `chain`, `plate`, ...) |
| 2 | hair style (head) or tail (torso) |
| 3 | ears / horns (head) |
| 4 | beard (head) |

| Color index | Use |
| --- | --- |
| 0 | skin / fur |
| 1 | hair |
| 2 | eyes |
| 3 | clothes |
| 4 | armor main |
| 5 | armor trim |
| 6 | horns / claws |
| 7 | trousers |

`pack/src/character.py` generates the models and writes `tc/rig_data.tc`
(joint positions and limb lengths per build).

Animation is keyframed in `pack/src/anim_clips.py` in a cartoony, bouncy
style: 28 channels (root turn/pitch/roll, bob, squash and stretch, torso,
head, arms, legs, held items), Catmull-Rom between keys, sampled into
`tc/anim_data.tc`. Moves wind up with a squash, snap through stretched,
overshoot and spring back; walks and runs hop between steps. Clips can be
planted: the generator lifts or lowers the body each sample so its lowest
point touches the ground. In game (`tc/anim.tc`) locomotion mixes idle,
walk and run by speed (a flailing loop in the air, a squash on landing), a
weapon stance is added on top, and an action clip (attacks, roll, cast,
death...) blends over it. `tc/rig.tc` turns the pose into display matrices
every tick (players) or every few ticks (NPCs), squashing the whole rig
about the feet; for two-handed weapons the left arm reaches for the handle
and stretches to get there.

`tools/viewer/` shows the pack's models and the clips in a browser with
the same rig math (`rig.js` mirrors `rig.tc` and `anim.tc`): serve the repo
root (`python3 -m http.server 8137`) and open `/tools/viewer/`. It has a
filmstrip mode, joint markers and the weapon arc, and keeps its settings in
the URL.

## Races

| Race | Height | Bonus |
| --- | --- | --- |
| Human | 1.00 | +10% XP, +1 to every stat |
| Elf | 1.06 | +15% ranged damage, +3 DEX, pointed ears |
| Dwarf | 0.80 | +3 STR, +10% armor, smithing costs -20%, beards |
| Demon | 1.05 | +3 INT, +15% spell power, fire resistance, horns, tail |
| Felkin (cat) | 0.95 | +15% move speed, +5% crit, cat ears and tail |
| Lupin (wolf) | 1.02 | +10% melee damage, heal 2% of melee damage, wolf ears, tail |
| Ursan (bear) | 1.10 | +25% max HP, +2 VIT, round ears |
| Leporin (rabbit) | 0.92 | +40% jump, +3 AGI, long ears, small tail |

## Stats and progression

- Stats: **STR** (heavy and blunt weapons), **DEX** (light, piercing and
  ranged weapons, crit), **INT** (spell power, magic efficiency, mana),
  **VIT** (health, regen), **AGI** (stamina, speed, dodge).
- Level 1-50. XP from kills and quests. Each level: +3 stat points, +HP.
- Derived: max HP, mana, stamina, regen, crit, move speed, magic
  efficiency `eff = INT / (INT + 40)`; spell mana cost is multiplied by
  `1 - 0.6 * eff` and spell power by `1 + INT / 50`.
- Gear adds stats: a staff adds INT by its quality, a greatsword STR, a
  dagger DEX, and so on.

## Items

Generated from type x material x rarity (+ random affixes), stored as real
Minecraft items with tags (`type`, `mat`, `rar`, `dmg`, `stats`, `slots`,
`dur`, ...) and a custom model.

- Weapon types: sword, longsword, greatsword (heavy), dagger, spear,
  halberd, axe, greataxe, mace, warhammer, scythe, gauntlets, staff, wand,
  bow, crossbow, shield.
- Materials (tier): wood, bronze, iron, steel, silver, mithril, adamant,
  dragonbone, runic. Each has colors used as model tints.
- Rarity: Common, Uncommon, Rare, Epic, Legendary, Mythic (1-6).
  - Wand: magic slots = rarity (1-6).
  - Staff: magic slots = ceil(rarity / 2), plus INT.
  - Dagger: ability slots = ceil(rarity / 2), plus DEX.
  - Other weapons: 1 ability slot from Rare up, 2 at Legendary.
  - Total hotbar slots used for spells and abilities: at most 8.
- Armor: helmet, chest, gloves (arms), legs, boots; sets: cloth, leather,
  chain, scale, plate, mage robe, ranger; tinted per material.
- Durability: repaired at the blacksmith. The blacksmith also crafts from
  ore and monster parts.

## Magic: words are physical

A spell is a phrase of learned Latin words. The phrase is parsed into
parameters, not looked up in a spell table, so every combination does
something. Word classes:

- **Elements** (damage type, color, status): ignis (fire, burn), glacies
  (ice, slow/freeze), fulmen (lightning, chains), aqua (water, push,
  douse), terra (earth, stun, heavy), ventus (wind, knockback), lux (light,
  bonus vs undead), umbra (shadow, lifesteal), venenum (poison), vita
  (life, heals).
- **Forms** (how it travels): sagitta (bolt), globus (orb that bursts),
  radius (beam), anulus (ring around you), murus (wall), pluvia (rain from
  above), nubes (lingering cloud), lancea (piercing lance), scutum (ward on
  self).
- **Verbs** (what it does): ferio (harm, default), sano (heal), traho
  (pull), pello (push), ligo (bind), volo (fly: dash or lift), voco
  (summon a familiar orb that casts the rest of the phrase).
- **Modifiers**: magnus (bigger), parvus (smaller, cheaper), celer
  (faster), tardus (slower, lasts longer), multus (more), geminus (one
  more), longus (further), fortis (stronger), sequens (homing), rumpens
  (bursts on hit), perforans (pierces), recurrens (bounces), mora
  (charges up for double power).

Every word adds mana cost; modifiers multiply it. Repeating a word stacks
with diminishing returns. A wand's slots each hold one inscribed phrase,
set in the Spell Loom (a dialog: type the phrase, see cost and effect,
inscribe it). Libraries sell words; rare words drop as scrolls. Speaking a
phrase in chat casts it from the held wand at +50% cost.

## World

`tc/world*.tc` generates the whole map in the plot from **seed 7341**,
sized from `game.plotSize`, so the plot can move or grow. The generator
works a little each tick and slows down when the plot CPU is high.

- Terrain: value-noise height lattice, rivers, a lake, forests, hills,
  rocky highlands at the edges.
- Settlements: the seed always places the walled city of **Valenmoor**
  near the middle, and (on plots of 601+ blocks) a village at the end of
  the country road that points away from the points of interest. The
  village has its own armory, library, blacksmith, guild hall, inn and
  reeve's manor.
- Town layout (after the "medieval fantasy city" generators): a market
  square, main streets from the square to the gates with gentle curves,
  side streets, lots cut along the streets, a wall with gates and towers,
  the lord's keep on the highest ground, farms outside the wall.
- Required buildings: armory, library, blacksmith, adventurers guild, inn,
  lord's house. Others: houses, chapel, bakery, alchemist, stables, tavern,
  general store, mage tower, barracks, market stalls, well, windmill,
  graveyard.
- Buildings are parametric (footprint, floors, roof, palette by type) with
  interiors fitting their use.
- Outside: monster zones by danger, a bandit camp, ruins over a crypt.

`tools/worldgen.py` mirrors the layout algorithm and draws `map/preview.png`
to check it.

## NPCs

Each NPC has a role, a home, a workplace and needs (energy, hunger,
social). A utility-based decision tree picks an activity each few seconds
(work, eat, go to the tavern, sleep, wander, flee from monsters, greet the
player). They walk the town's street graph. Shopkeepers trade through
menus. Guards fight monsters that come into town. Dialogue is generated
from the NPC's role, mood and the player's reputation.

## Quests

The adventurers guild has a board of generated contracts (hunt N of a
monster, clear a camp, fetch an item, escort), ranked F to S. Ranks unlock
harder contracts and better rewards.

## CPU rules

- One global loop: players every tick, NPCs and enemies in batches.
- NPC rigs update every 4 ticks with interpolation, only within 48 blocks
  of a player.
- World generation and other bulk work back off when `game.cpuUsage` is
  high.

## Status (built and tested on the plot)

- Camera boom, body, rig, races, appearance, gear on the model: working.
- World generation from the seed: terrain, river, lake, city (about 170
  buildings), village, farms, roads, bridges, lamps, forests, points of
  interest. About 20 minutes on a Mega plot; resumes after restarts.
- Combat: combos, heavy attacks, dodge, lock-on, slash trails, damage
  numbers, monsters with telegraphed attacks, ranged and caster enemies,
  bosses with a ground slam every third attack.
- Magic: phrase compiler, all forms and verbs, zones, wards, familiars,
  chat incantations, Spell Loom.
- Town: NPC needs and utility decisions, street-graph walking, chatter,
  dialogue, shops, library, smith repair and upgrades, inn, chapel, guild
  contracts and ranks, arts trainer, the lord's story.

## Lessons from the plot

- Spawning into an unloaded chunk silently fails (no UUID). Wait for the
  chunk (teleport the player first) and validate UUIDs before using them.
- A ridden entity does not teleport reliably across chunks: rebuild the
  body at the destination instead.
- The dismount event fires for code-driven dismounts too; allow it while
  the game moves the player.
- Styled text `%var()` inserts plain text: keep MiniMessage tags in the
  literal and pass `txt` values around for colored messages.
- Dialogs of type "Multi Action with Exit Button" turn the first button
  into the exit button; use "Multi Action".
- Startup cleanup (removing stale entities) must run once, synchronously,
  before anything spawns.

## Ideas for later

- Mounts (the stables), fishing at the lake dock, housing.
- More monster types with custom models (the rig can draw monsters too).
- Party play and shared contracts.
