// Model and animation viewer for the RPG pack. Serve the repo root
// (python3 -m http.server 8137) and open /tools/viewer/. It reads the item
// model definitions, block models and textures straight from pack/assets,
// and the clips from anim_data.json, so it shows what the generators wrote.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PARTS, PART_ITEM, rigPose, clipPose, toDict, locoMix, addClip, blendAction, actionWeight, phaseRate } from "./rig.js";

const ASSETS = "../../pack/assets/";
const WEAPONS = ["sword", "longsword", "greatsword", "dagger", "axe", "greataxe", "mace", "warhammer", "spear", "halberd",
  "scythe", "staff", "wand", "bow", "crossbow", "gauntlets", "shield"];
const $ = id => document.getElementById(id);
const errBox = $("err");
const showErr = e => { errBox.textContent += String(e) + "\n"; console.error(e); };

// ------------------------------------------------------------- loading

let bust = Date.now();
const jsonCache = new Map(), texCache = new Map();
async function getJson(path) {
  if (!jsonCache.has(path)) {
    jsonCache.set(path, fetch(path + "?v=" + bust).then(r => {
      if (!r.ok) throw new Error(`${r.status} ${path}`);
      return r.json();
    }));
  }
  return jsonCache.get(path);
}
const idPath = (id, dir, ext) => {
  const [ns, p] = id.includes(":") ? id.split(":") : ["minecraft", id];
  return `${ASSETS}${ns}/${dir}/${p}${ext}`;
};
function getTex(id) {
  if (!texCache.has(id)) {
    const t = new THREE.TextureLoader().load(idPath(id, "textures", ".png") + "?v=" + bust);
    t.magFilter = THREE.NearestFilter;
    t.minFilter = THREE.NearestFilter;
    t.colorSpace = THREE.SRGBColorSpace;
    texCache.set(id, t);
  }
  return texCache.get(id);
}

/** Resolves an item model definition node to [[modelId, tints]...] for the
 * given custom model data strings and colors. */
function resolve(node, strings, colors, out = []) {
  const type = (node.type || "").replace("minecraft:", "");
  if (type === "model") {
    const tints = (node.tints || []).map(t => (t.type || "").endsWith("custom_model_data")
      ? (colors[t.index] ?? t.default) : (t.default ?? 0xffffff));
    out.push([node.model, tints]);
  } else if (type === "composite") {
    node.models.forEach(m => resolve(m, strings, colors, out));
  } else if (type === "select") {
    let val = null;
    if ((node.property || "").endsWith("custom_model_data")) val = strings[node.index || 0];
    const hit = val == null ? null : node.cases.find(c => [].concat(c.when).includes(val));
    resolve(hit ? hit.model : (node.fallback || { type: "empty" }), strings, colors, out);
  }
  return out;
}

const matCache = new Map();
function material(texId, tint, alpha = 1) {
  const key = `${texId}|${tint}|${alpha}`;
  if (!matCache.has(key)) {
    matCache.set(key, new THREE.MeshLambertMaterial({ map: getTex(texId), color: new THREE.Color(tint),
      transparent: alpha < 1, opacity: alpha, alphaTest: 0.1 }));
  }
  return matCache.get(key);
}
const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });
// BoxGeometry face order.
const FACE_ORDER = ["east", "west", "up", "down", "south", "north"];

/** Builds a mesh group from a block model; geometry is in model pixels
 * around the pivot (element coordinates minus 8). */
function buildModel(model, tints, alpha) {
  const g = new THREE.Group();
  const texOf = key => {
    let k = key.replace("#", "");
    for (let i = 0; i < 4 && model.textures[k]?.startsWith("#"); i++) k = model.textures[k].slice(1);
    return model.textures[k];
  };
  for (const el of model.elements || []) {
    const size = [0, 1, 2].map(i => Math.max(0.001, el.to[i] - el.from[i]));
    const geo = new THREE.BoxGeometry(...size);
    const uv = geo.attributes.uv;
    const mats = FACE_ORDER.map((f, fi) => {
      const face = el.faces[f];
      if (!face) return HIDDEN;
      const [u0, v0, u1, v1] = face.uv || [0, 0, 16, 16];
      for (let k = 0; k < 4; k++) {
        const idx = fi * 4 + k;
        const U = uv.getX(idx), V = uv.getY(idx);
        uv.setXY(idx, (u0 + U * (u1 - u0)) / 16, 1 - (v0 + (1 - V) * (v1 - v0)) / 16);
      }
      const tint = face.tintindex != null ? (tints[face.tintindex] ?? 0xffffff) : 0xffffff;
      return material(texOf(face.texture), tint, alpha);
    });
    const m = new THREE.Matrix4();
    const c = [0, 1, 2].map(i => (el.from[i] + el.to[i]) / 2 - 8);
    if (el.rotation) {
      const r = el.rotation, o = r.origin.map(x => x - 8), D = Math.PI / 180;
      const rot = new THREE.Matrix4();
      if (r.axis) {
        const ax = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }[r.axis];
        rot.makeRotationAxis(new THREE.Vector3(...ax), r.angle * D);
      } else {
        // Euler x, y, z applied X first (JOML rotationZYX).
        rot.makeRotationFromEuler(new THREE.Euler((r.x || 0) * D, (r.y || 0) * D, (r.z || 0) * D, "ZYX"));
      }
      m.makeTranslation(o[0], o[1], o[2]).multiply(rot).multiply(new THREE.Matrix4().makeTranslation(c[0] - o[0], c[1] - o[1], c[2] - o[2]));
    } else {
      m.makeTranslation(c[0], c[1], c[2]);
    }
    geo.applyMatrix4(m);
    g.add(new THREE.Mesh(geo, mats));
  }
  return g;
}

async function buildItem(itemId, strings, colors, alpha = 1) {
  const def = await getJson(idPath(itemId, "items", ".json"));
  const g = new THREE.Group();
  for (const [modelId, tints] of resolve(def.model, strings, colors)) {
    g.add(buildModel(await getJson(idPath(modelId, "models", ".json")), tints, alpha));
  }
  return g;
}

// ------------------------------------------------------------- scene

const view = $("view");
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(devicePixelRatio);
view.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x2b3340);
const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 100);
camera.position.set(2.2, 1.6, 4.2);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.95, 0);
controls.update();
scene.add(new THREE.HemisphereLight(0xffffff, 0x58606a, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(3, 6, 4);
scene.add(sun);
const grid = new THREE.GridHelper(8, 8, 0x6a7280, 0x46505c);
scene.add(grid);
const fine = new THREE.GridHelper(8, 128, 0x3a424e, 0x3a424e);
fine.position.y = -0.001;
scene.add(fine);

const rigRoot = new THREE.Group();
scene.add(rigRoot);
const partGroups = Object.fromEntries(PARTS.map(p => {
  const g = new THREE.Group();
  g.matrixAutoUpdate = false;
  rigRoot.add(g);
  return [p, g];
}));
const jointDots = new THREE.Group();
scene.add(jointDots);
const trail = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffd060 }));
scene.add(trail);
const single = new THREE.Group();
scene.add(single);
// Filmstrip: copies of the rig posed at evenly spaced times of the clip,
// side on, in a row.
const strip = new THREE.Group();
scene.add(strip);
const STRIP_N = 7;
function stripBuild() {
  strip.clear();
  rigRoot.visible = !$("strip").checked;
  if (!$("strip").checked) return;
  for (let i = 0; i < STRIP_N; i++) {
    const root = new THREE.Group();
    root.position.set((i - (STRIP_N - 1) / 2) * 1.35, 0, 0);
    root.rotation.y = { side: Math.PI / 2, front: 0, q: Math.PI / 5 }[$("stripView").value] ?? Math.PI / 2;
    root.userData.parts = {};
    for (const p of PARTS) {
      const g = partGroups[p].clone();
      g.matrixAutoUpdate = false;
      root.add(g);
      root.userData.parts[p] = g;
    }
    strip.add(root);
  }
}

function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);

// ------------------------------------------------------------- state

let rigData, anim;
const hex = id => parseInt($(id).value.slice(1), 16);
function fill(id, values, blank) {
  const sel = $(id), cur = sel.value;
  sel.innerHTML = (blank ? `<option value="">${blank}</option>` : "") + values.map(v => `<option>${v}</option>`).join("");
  if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
}

async function loadData() {
  bust = Date.now();
  jsonCache.clear();
  texCache.clear();
  matCache.clear();
  rigData = await getJson("rig_data.json");
  anim = await getJson("anim_data.json");
  anim.upperMask = anim.channels.map(c => anim.upper.includes(c));
  fill("build", Object.keys(rigData.builds));
  fill("hairStyle", rigData.hairs, "none");
  fill("ears", rigData.ears);
  fill("beard", rigData.beards, "none");
  fill("tail", rigData.tails, "none");
  for (const s of ["a_head", "a_torso", "a_arm", "a_leg"]) fill(s, rigData.armors, "none");
  fill("main", WEAPONS, "none");
  fill("off", WEAPONS, "none");
  fill("clip", Object.keys(anim.clips));
  fill("stance", Object.keys(anim.clips).filter(n => n.startsWith("hold_")), "none");
  readHash();
  await rebuild();
}

const HIDES_HAIR = ["chain", "scale", "plate", "bone", "ranger"];
function partStrings(item) {
  const b = $("build").value;
  const slot = item;
  const armor = $("a_" + slot).value;
  const s = [item === "arm" && $("arms").value === "slim" ? b + "s" : b, armor];
  if (item === "head") {
    let hs = $("hairStyle").value, ears = $("ears").value;
    if (HIDES_HAIR.includes(armor)) { hs = ""; if (ears === "human" || ears === "elf") ears = ""; }
    s.push(hs, ears, $("beard").value);
  } else if (item === "torso") {
    s.push($("tail").value);
  }
  return s;
}

let buildSeq = 0;
async function rebuild() {
  const seq = ++buildSeq;
  errBox.textContent = "";
  try {
    const colors = [hex("skin"), hex("hair"), hex("eye"), hex("cloth"), hex("am"), hex("at"), hex("horn"), hex("pants")];
    const built = {};
    for (const p of PARTS) {
      if (PART_ITEM[p]) {
        built[p] = await buildItem("rpg:body/" + PART_ITEM[p], partStrings(PART_ITEM[p]), colors);
      } else {
        const w = $(p).value;
        built[p] = w ? await buildItem("rpg:weapon/" + w, [$("variant").value], [0xb8bcc4, 0x7a5434, 0xd8b048]) : new THREE.Group();
      }
    }
    single.clear();
    const id = $("single").value.trim();
    if (id) {
      const m = buildModel(await getJson(idPath(id, "models", ".json")), [0xe0ac85, 0x5a3a22, 0x3c6e9e, 0x8a6a45, 0x9aa0a8, 0xc8a050, 0x2b2420, 0x4e4234]);
      m.scale.setScalar(1 / 16);
      m.position.set(1.4, 0.6, 0);
      single.add(m);
    }
    if (seq !== buildSeq) return;
    for (const p of PARTS) {
      partGroups[p].clear();
      partGroups[p].add(built[p]);
    }
    stripBuild();
  } catch (e) {
    showErr(e);
  }
}

// ------------------------------------------------------------- hash state

const KEYS = ["stripView", "mode", "clip", "stance", "speed", "rate", "time", "ticks", "build", "arms", "hairStyle", "ears", "beard", "tail", "scale",
  "skin", "hair", "eye", "cloth", "pants", "horn", "a_head", "a_torso", "a_arm", "a_leg", "am", "at", "main", "off", "variant", "single"];
function readHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  for (const k of KEYS) if (q.has(k)) $(k).value = q.get(k);
  for (const k of ["joints", "ghost", "strip", "air"]) if (q.has(k)) $(k).checked = q.get(k) === "1";
  if (q.get("paused") === "1") setPlaying(false);
  if (q.has("cam")) setCam(q.get("cam"));
}
function writeHash() {
  const q = new URLSearchParams();
  for (const k of KEYS) if ($(k).value !== "") q.set(k, $(k).value);
  for (const k of ["joints", "ghost", "strip", "air"]) if ($(k).checked) q.set(k, "1");
  if (!playing) q.set("paused", "1");
  history.replaceState(null, "", "#" + q.toString());
}

// ------------------------------------------------------------- playback

let playing = true, clipT = 0, phase = 0, ticks = 0;
function setPlaying(p) {
  playing = p;
  $("play").textContent = p ? "Pause" : "Play";
}
$("play").onclick = () => { setPlaying(!playing); writeHash(); };
$("step").onclick = () => { setPlaying(false); advance(1); writeHash(); };
$("time").oninput = () => { clipT = +$("time").value; };
function setCam(kind) {
  const d = 4.6;
  // The strip: far enough back for the whole row to fit the view's width.
  const half = Math.tan(camera.fov * Math.PI / 360) * camera.aspect;
  const far = (STRIP_N * 1.35 / 2 + 0.3) / half;
  const pos = { front: [0, 1.1, d], side: [d, 1.1, 0], q: [2.4, 1.7, 3.9], strip: [0, 1.2, far] }[kind] || [2.4, 1.7, 3.9];
  camera.position.set(...pos);
  controls.target.set(0, 0.95, 0);
  controls.update();
}
$("shot").onclick = () => setCam("front");
$("side3").onclick = () => setCam("side");
$("top3").onclick = () => setCam("q");
$("reload").onclick = loadData;
for (const k of KEYS) {
  const el = $(k);
  const rebuildKeys = ["build", "arms", "hairStyle", "ears", "beard", "tail", "skin", "hair", "eye", "cloth", "pants", "horn",
    "a_head", "a_torso", "a_arm", "a_leg", "am", "at", "main", "off", "variant", "single"];
  el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
    if (rebuildKeys.includes(k)) rebuild();
    if (k === "clip") clipT = 0;
    writeHash();
  });
}
for (const k of ["joints", "ghost", "strip", "air"]) $(k).addEventListener("change", writeHash);
$("strip").addEventListener("change", () => { stripBuild(); setCam($("strip").checked ? "strip" : "q"); });
$("stripView").addEventListener("change", stripBuild);

/** Advances the animation by n game ticks. */
function advance(n) {
  const speed = +$("speed").value;
  for (let i = 0; i < n; i++) {
    ticks += 1;
    phase = (phase + speed * phaseRate(speed)) % 360;
    const len = Math.max(1, +$("ticks").value || 14);
    clipT += 1 / len;
    const c = anim.clips[$("clip").value];
    if (c && c.loop) clipT %= 1;
    else if (clipT > 1.25) clipT = 0;
  }
  $("time").value = Math.min(1, clipT);
}

function currentPose(t = clipT) {
  const mode = $("mode").value;
  if (mode === "rest") return anim.rest.slice();
  let pose = locoMix(anim, mode === "loco" ? +$("speed").value : 0, mode !== "loco" || !$("air").checked, phase, ticks);
  pose = addClip(anim, pose, $("stance").value);
  if (mode === "clip") {
    const name = $("clip").value, c = anim.clips[name];
    const tt = Math.min(1, t);
    // Landings add over locomotion in the game (tc/core.tc).
    pose = name === "land" ? addClip(anim, pose, name, tt) : blendAction(anim, pose, name, tt, actionWeight(tt, c.loop, name === "death"));
  }
  return pose;
}

/** Left-hand IK offset along the weapon for two-handed weapons (px), or
 * null (mirrors rigIkOffset in tc/rig.tc). */
function ikOffset() {
  const w = $("main").value;
  if (["greatsword", "greataxe", "warhammer", "scythe"].includes(w)) return -3.6;
  if (["spear", "halberd"].includes(w)) return 7;
  return null;
}

function applyPose(poseArr, groups = partGroups) {
  const build = rigData.builds[$("build").value];
  const res = rigPose(build, +$("scale").value, toDict(anim, poseArr), ikOffset(), $("arms").value === "slim");
  for (const p of PARTS) {
    const { a, b, c, t, s } = res.parts[p];
    const k = s / 16;
    groups[p].matrix.set(a[0] * k, b[0] * k, c[0] * k, t[0], a[1] * k, b[1] * k, c[1] * k, t[1], a[2] * k, b[2] * k, c[2] * k, t[2], 0, 0, 0, 1);
    groups[p].matrixWorldNeedsUpdate = true;
  }
  return res;
}

function drawJoints(res) {
  jointDots.clear();
  if (!$("joints").checked) return;
  const geo = new THREE.SphereGeometry(0.022, 8, 6);
  const mat = new THREE.MeshBasicMaterial({ color: 0xff4060, depthTest: false });
  for (const j of res.joints) {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(...j);
    m.renderOrder = 10;
    jointDots.add(m);
  }
}

function drawTrail() {
  if (!$("ghost").checked || $("mode").value !== "clip") { trail.visible = false; return; }
  const build = rigData.builds[$("build").value];
  const pts = [];
  for (let i = 0; i <= 60; i++) {
    const r = rigPose(build, +$("scale").value, toDict(anim, currentPose(i / 60)), null, $("arms").value === "slim");
    const m = r.parts.main;
    // The tip of a 14 px blade (weapons are half-size pixels).
    const L = 14 * m.s / 16;
    pts.push(new THREE.Vector3(m.t[0] + m.b[0] * L, m.t[1] + m.b[1] * L, m.t[2] + m.b[2] * L));
  }
  trail.geometry.setFromPoints(pts);
  trail.visible = true;
}

function hud(pose) {
  const name = $("clip").value, c = anim.clips[name];
  const ch = anim.channels.map((n, i) => `${n.padEnd(7)}${pose[i].toFixed(1).padStart(7)}`).join("\n");
  $("chans").textContent = ch;
  const mode = $("mode").value;
  $("hud").textContent = mode === "clip"
    ? `${name}  t=${Math.min(1, clipT).toFixed(3)}  ${c.loop ? "loop" : "once"}  hit=${c.hit}  mask=${c.mask}`
    : mode === "loco" ? `locomotion  speed=${(+$("speed").value).toFixed(3)} b/t  phase=${phase.toFixed(0)}` : "rest pose";
}

let last = performance.now(), acc = 0;
function frame(now) {
  requestAnimationFrame(frame);
  if (!anim) return;
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (playing) {
    acc += dt * 20 * +$("rate").value;
    const n = Math.floor(acc);
    acc -= n;
    if (n) advance(n);
  }
  const pose = currentPose();
  const res = applyPose(pose);
  strip.children.forEach((root, i) => applyPose(currentPose(i / (STRIP_N - 1)), root.userData.parts));
  drawJoints(res);
  hud(pose);
  renderer.render(scene, camera);
}

resize();
loadData().then(() => { drawTrail(); requestAnimationFrame(frame); }).catch(showErr);
setInterval(() => anim && drawTrail(), 500);
// For scripted checks (screenshots from the browser pane).
window.viewer = { setPose: t => { setPlaying(false); clipT = t; }, setCam, rebuild, loadData };
