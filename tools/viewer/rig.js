// The character rig and animation mixing, mirrored from tc/rig.tc and
// tc/anim.tc so the viewer shows what the game draws. Keep the two in step.
//
// Frames: +X is the character's left, +Y up, +Z forward (Minecraft at yaw 0).
// A part is drawn as world = t + s/16 * (a*x + b*y + c*z) for model pixels
// (x, y, z) around the part's pivot; the feet are at the origin.

export const PARTS = ["head", "torso", "armR", "armL", "legR", "legL", "main", "off"];
export const PART_ITEM = { head: "head", torso: "torso", armR: "arm", armL: "arm", legR: "leg", legL: "leg" };

const v = (x, y, z) => [x, y, z];
const add = (p, q) => [p[0] + q[0], p[1] + q[1], p[2] + q[2]];
const mul = (p, k) => [p[0] * k, p[1] * k, p[2] * k];
const sub = (p, q) => add(p, mul(q, -1));
const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
const cross = (p, q) => [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]];
const norm = p => { const l = Math.hypot(...p) || 1; return mul(p, 1 / l); };

/** Rotates p about unit axis k by deg degrees (right-handed, like Bukkit's
 * rotateAroundVec). */
export function rotAround(p, k, deg) {
  const r = deg * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const d = dot(k, p);
  const x = cross(k, p);
  return [0, 1, 2].map(i => p[i] * c + x[i] * s + k[i] * d * (1 - c));
}

/** basisRot of rig.tc: yaw about b, then pitch about a (positive swings -b
 * toward +c), then roll about c (positive moves -b toward +a). */
export function basisRot(a, b, c, p, y, r) {
  if (y) { c = rotAround(c, b, y); a = rotAround(a, b, y); }
  if (p) { b = rotAround(b, a, -p); c = rotAround(c, a, -p); }
  if (r) { b = rotAround(b, c, r); a = rotAround(a, c, r); }
  return [a, b, c];
}

/** Squash and stretch factors for sq (percent): [across, up]. */
export const squash = sq => { const up = Math.max(0.3, 1 + sq / 100); return [1 / Math.sqrt(up), up]; };

/** Poses the rig. build: rig_data build entry; pose: {channel: value}; ik:
 * left-hand offset along a two-handed weapon (px) or null; slim: slim arms. Returns
 * {parts: {name: {a, b, c, t, s}}, joints: [[x,y,z]...], grip}. */
export function rigPose(build, scale, pose, ik = null, slim = false) {
  if (slim) build = { ...build, sx: build.sxs };
  const s = scale * 0.9, px = s / 16;
  const P = k => pose[k] || 0;
  let L = v(1, 0, 0), U = v(0, 1, 0), F = v(0, 0, 1);
  // Bob and fwd are keyed for build m (hips 12 px up): scale them to the
  // build's legs.
  const k = build.hip / 12;
  const hip = add(mul(U, (P("bob") * k + build.hip) * px), mul(F, P("fwd") * k * px));
  // Whole body about the hips: turn, then pitch forward, then roll left.
  if (P("root_y")) { L = rotAround(L, U, P("root_y")); F = rotAround(F, U, P("root_y")); }
  if (P("root_p")) { U = rotAround(U, L, P("root_p")); F = rotAround(F, L, P("root_p")); }
  if (P("root_r")) { U = rotAround(U, F, -P("root_r")); L = rotAround(L, F, -P("root_r")); }
  const parts = {}, joints = [];
  const put = (name, B, t, len = 1) => { parts[name] = { a: B[0], b: mul(B[1], len), c: B[2], t, s }; };

  const tb = basisRot(L, U, F, -P("t_p"), P("t_y"), -P("t_r"));
  put("torso", tb, hip);
  const [ta, tu, tf] = tb;
  const neck = add(hip, mul(tu, (build.neck - build.hip) * px));
  put("head", basisRot(ta, tu, tf, -P("h_p"), P("h_y"), -P("h_r")), neck);

  // Arms: one piece each from the shoulder; "out" moves the hand away from
  // the body. The hand (grip) is `grip` px down the arm.
  const sh = add(hip, mul(tu, (build.sy - build.hip) * px));
  const arm = (side, key) => {
    const at = add(sh, mul(ta, side * build.sx * px));
    const B = basisRot(ta, tu, tf, P(`a_${key}_p`), P(`a_${key}_y`), side * P(`a_${key}_o`));
    return { at, B, len: 1, grip: sub(at, mul(B[1], build.grip * px)) };
  };
  const R = arm(-1, "r"), Lf = arm(1, "l");
  // Held items: +Y out of the fist along the arm's forward, +Z down the arm.
  const held = (B, key) => basisRot(B[0], B[2], mul(B[1], -1), P(`${key}_p`), P(`${key}_y`), P(`${key}_r`));
  const wb = held(R.B, "m");
  if (ik !== null) {
    // Two-handed: the left arm reaches for the handle ik px along the
    // weapon from the right fist, stretching (cartoon style) to get there.
    const target = add(R.grip, mul(wb[1], ik * px));
    const d = sub(target, Lf.at), dist = Math.hypot(...d), dir = norm(d);
    const b = mul(dir, -1);
    let a = sub(ta, mul(dir, dot(ta, dir)));
    if (Math.hypot(...a) < 1e-3) a = sub(tf, mul(dir, dot(tf, dir)));
    a = norm(a);
    Lf.B = [a, b, cross(a, b)];
    Lf.len = Math.max(0.75, Math.min(1.3, dist / (build.grip * px)));
    Lf.grip = add(Lf.at, mul(dir, build.grip * px * Lf.len));
  }
  put("armR", R.B, R.at);
  put("armL", Lf.B, Lf.at, Lf.len);
  put("main", wb, R.grip);
  put("off", held(Lf.B, "o"), Lf.grip);
  if (ik !== null) parts.off.s = 0;
  joints.push(R.at, R.grip, Lf.at, Lf.grip);

  // Legs from the hips (root frame, not the torso's).
  const leg = (side, key, name) => {
    const at = add(hip, mul(L, side * build.hx * px));
    const B = basisRot(L, U, F, P(`l_${key}_p`), 0, side * P(`l_${key}_o`));
    joints.push(at, sub(at, mul(B[1], build.ll * px)));
    put(name, B, at);
  };
  leg(-1, "r", "legR");
  leg(1, "l", "legL");
  joints.push(hip, neck);

  // Squash and stretch about the feet: scale every part's frame.
  const [h, u] = squash(P("sq"));
  const S = p => [p[0] * h, p[1] * u, p[2] * h];
  for (const p of Object.values(parts)) { p.a = S(p.a); p.b = S(p.b); p.c = S(p.c); p.t = S(p.t); }
  return { parts, joints: joints.map(S), grip: S(R.grip) };
}

// ------------------------------------------------------------- animation

/** The pose of clip `name` at normalized time t (0..1), lerped between
 * samples like clipPose in tc/anim.tc. Returns an array of channels. */
export function clipPose(anim, name, t) {
  const c = anim.clips[name];
  const n = c.samples.length;
  let x;
  if (c.loop) {
    x = ((t % 1) + 1) % 1 * n;
  } else {
    x = Math.max(0, Math.min(1, t)) * (n - 1);
  }
  const i = Math.floor(x), f = x - i;
  const a = c.samples[i % n], b = c.samples[c.loop ? (i + 1) % n : Math.min(i + 1, n - 1)];
  return a.map((va, j) => va + (b[j] - va) * f);
}

export const toDict = (anim, arr) => Object.fromEntries(anim.channels.map((ch, i) => [ch, arr[i]]));

/** Locomotion as the game mixes it (tc/anim.tc locoMix): idle, walk and run
 * by speed (blocks per tick), the flailing air loop off the ground. */
export function locoMix(anim, speed, grounded, phase, t) {
  if (!grounded) return clipPose(anim, "air", t / 14);
  const idle = clipPose(anim, "idle", t / 60);
  if (speed < 0.01) return idle;
  const walk = clipPose(anim, "walk", phase / 360);
  const run = clipPose(anim, "run", phase / 360);
  const wWalk = Math.min(1, speed / 0.06);
  const wRun = runWeight(speed);
  return idle.map((v0, i) => {
    const m = v0 + (walk[i] - v0) * wWalk;
    return m + (run[i] - m) * wRun;
  });
}

/** How much of the run cycle mixes in at speed (blocks per tick). */
export const runWeight = speed => Math.max(0, Math.min(1, (speed - 0.17) / 0.08));

/** Walk phase degrees per block moved: one walk cycle covers about a block,
 * a run cycle nearly two. */
export const phaseRate = speed => 340 - 150 * runWeight(speed);

/** Adds clip `name` at time t (its offsets from the rest pose) over a pose
 * with weight w: stances, landings. */
export function addClip(anim, pose, name, t = 0, w = 1) {
  if (!name) return pose;
  const st = clipPose(anim, name, t);
  return pose.map((v0, i) => v0 + (st[i] - anim.rest[i]) * w);
}

/** Blends action clip `name` at time t over pose with weight w (upper-only
 * clips leave the legs, root and squash alone). */
export function blendAction(anim, pose, name, t, w) {
  const c = anim.clips[name];
  const act = clipPose(anim, name, t);
  return pose.map((v0, i) => {
    if (c.mask === "upper" && !anim.upperMask[i]) return v0;
    // Root turns the shorter way round, so a roll's 360 blends out as 0.
    const d = i < 3 ? ((act[i] - v0 + 900) % 360) - 180 : act[i] - v0;
    return v0 + d * w;
  });
}

/** Weight of an action at time t: a quick blend in and out. */
export function actionWeight(t, loop, hold = false) {
  if (loop) return 1;
  if (hold) return Math.min(1, t / 0.08);
  return Math.max(0, Math.min(1, t / 0.08, (1 - t) / 0.15));
}
