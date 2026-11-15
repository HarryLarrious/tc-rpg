// The character rig and animation mixing, mirrored from tc/rig.tc and
// tc/anim.tc so the viewer shows what the game draws. Keep the two in step.
//
// Frames: +X is the character's left, +Y up, +Z forward (Minecraft at yaw 0).
// A part is drawn as world = t + s/16 * (a*x + b*y + c*z) for model pixels
// (x, y, z) around the part's pivot.

export const PARTS = ["head", "torso", "uarmR", "uarmL", "farmR", "farmL", "thighR", "thighL", "shinR", "shinL", "main", "off"];
export const PART_ITEM = { head: "head", torso: "torso", uarmR: "uarm", uarmL: "uarm", farmR: "farm", farmL: "farm",
  thighR: "thigh", thighL: "thigh", shinR: "shin", shinL: "shin" };

const v = (x, y, z) => [x, y, z];
const add = (p, q) => [p[0] + q[0], p[1] + q[1], p[2] + q[2]];
const mul = (p, k) => [p[0] * k, p[1] * k, p[2] * k];
const sub = (p, q) => add(p, mul(q, -1));

/** Rotates p about unit axis k by deg degrees (right-handed, like Bukkit's
 * rotateAroundVec). */
export function rotAround(p, k, deg) {
  const r = deg * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const d = k[0] * p[0] + k[1] * p[1] + k[2] * p[2];
  const x = [k[1] * p[2] - k[2] * p[1], k[2] * p[0] - k[0] * p[2], k[0] * p[1] - k[1] * p[0]];
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

const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
const cross = (p, q) => [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]];
const norm = p => { const l = Math.hypot(...p) || 1; return mul(p, 1 / l); };

/** Two-bone IK of an arm: shoulder at, target point, bone lengths ua and
 * fa (blocks), pole: where the elbow points. Returns [upper basis, elbow,
 * fore basis] with each bone hanging along -b and bending toward +c. */
export function armIk(at, target, ua, fa, pole, fwd) {
  let d = sub(target, at);
  const dist = Math.max(Math.abs(ua - fa) + 1e-3, Math.min(ua + fa - 1e-3, Math.hypot(...d)));
  const n = norm(d);
  const cosA = Math.max(-1, Math.min(1, (ua * ua + dist * dist - fa * fa) / (2 * ua * dist)));
  const sinA = Math.sqrt(1 - cosA * cosA);
  let pp = sub(pole, mul(n, dot(pole, n)));
  pp = norm(pp);
  const u = add(mul(n, cosA), mul(pp, sinA));
  const elbow = add(at, mul(u, ua));
  const w = norm(sub(add(at, mul(n, dist)), elbow));
  const frame = (dir, bendTo) => {
    const b = mul(dir, -1);
    let c = sub(bendTo, mul(dir, dot(bendTo, dir)));
    if (Math.hypot(...c) < 1e-3) c = sub(fwd, mul(dir, dot(fwd, dir)));
    c = norm(c);
    return [cross(b, c), b, c];
  };
  const upper = frame(u, w);
  // The forearm keeps the upper arm's side axis, bent about it.
  const fb = mul(w, -1), fc = norm(cross(upper[0], fb));
  return [upper, elbow, [upper[0], fb, fc]];
}

/** Poses the rig. build: rig_data build entry; pose: {channel: value}.
 * Returns {parts: {name: {a, b, c, t, s}}, joints: [[x,y,z]...], grip}. */
export function rigPose(build, scale, pose, ikOff = null) {
  const s = scale * 0.9, px = s / 16;
  const P = k => pose[k] || 0;
  let L = v(1, 0, 0), U = v(0, 1, 0), F = v(0, 0, 1);
  // Bob and fwd are keyed for build m (hips 12 px up): scale them to the
  // build's legs.
  const k = build.hip / 12;
  const base = add(mul(U, P("bob") * px * k), mul(F, P("fwd") * px * k));
  const hip = add(base, mul(U, build.hip * px));
  // Whole body about the hips: pitch tips forward, roll tips to its left.
  if (P("root_p")) { U = rotAround(U, L, P("root_p")); F = rotAround(F, L, P("root_p")); }
  if (P("root_r")) { U = rotAround(U, F, -P("root_r")); L = rotAround(L, F, -P("root_r")); }
  const parts = {}, joints = [];
  const put = (name, B, t) => { parts[name] = { a: B[0], b: B[1], c: B[2], t, s }; };

  const tb = basisRot(L, U, F, -P("t_p"), P("t_y"), -P("t_r"));
  put("torso", tb, hip);
  const up = tb[1], left = tb[0];
  const neck = add(hip, mul(up, (build.neck - build.hip) * px));
  put("head", basisRot(tb[0], tb[1], tb[2], -P("h_p"), P("h_y"), 0), neck);

  const sh = add(hip, mul(up, (build.sy - build.hip) * px));
  const arm = (side, k) => {
    const at = add(sh, mul(left, side * build.sx * px));
    const ua = basisRot(tb[0], tb[1], tb[2], P(`ua_${k}_p`), P(`ua_${k}_y`), side * P(`ua_${k}_o`));
    const elbow = sub(at, mul(ua[1], build.ua * px));
    const fa = basisRot(ua[0], ua[1], ua[2], P(`el_${k}`), 0, 0);
    const grip = sub(elbow, mul(fa[1], build.fa * px));
    joints.push(at, elbow, grip);
    return [at, ua, elbow, fa, grip];
  };
  const R = arm(-1, "r"), Lh = arm(1, "l");
  if (ikOff !== null) {
    // Two-handed: the left hand takes the handle ikOff px along the weapon
    // from the right fist.
    const wb = basisRot(R[3][0], R[3][2], mul(R[3][1], -1), P("m_p"), P("m_y"), P("m_r"));
    const target = add(R[4], mul(wb[1], ikOff * px));
    const pole = add(add(mul(up, -1), mul(left, 0.7)), mul(tb[2], -0.4));
    const ik = armIk(Lh[0], target, build.ua * px, build.fa * px, pole, tb[2]);
    joints.splice(joints.length - 3, 3, Lh[0], ik[1], target);
    Lh[1] = ik[0]; Lh[2] = ik[1]; Lh[3] = ik[2]; Lh[4] = target;
  }
  put("uarmR", R[1], R[0]); put("farmR", R[3], R[2]);
  put("uarmL", Lh[1], Lh[0]); put("farmL", Lh[3], Lh[2]);
  // Held items: +Y out of the fist along the forearm's forward, +Z down the
  // forearm.
  const held = (fa, k) => basisRot(fa[0], fa[2], mul(fa[1], -1), P(`${k}_p`), P(`${k}_y`), P(`${k}_r`));
  put("main", held(R[3], "m"), R[4]);
  put("off", held(Lh[3], "o"), Lh[4]);

  const leg = (side, k, nameT, nameS) => {
    const at = add(hip, mul(L, side * build.hx * px));
    const th = basisRot(L, U, F, P(`th_${k}_p`), 0, side * P(`th_${k}_o`));
    const knee = sub(at, mul(th[1], build.th * px));
    const shn = basisRot(th[0], th[1], th[2], -P(`kn_${k}`), 0, 0);
    joints.push(at, knee, sub(knee, mul(shn[1], build.sh * px)));
    put(nameT, th, at); put(nameS, shn, knee);
  };
  leg(-1, "r", "thighR", "shinR");
  leg(1, "l", "thighL", "shinL");
  joints.push(hip, neck);
  return { parts, joints, grip: R[4] };
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
 * by speed (blocks per tick), the air pose when off the ground. */
export function locoMix(anim, speed, grounded, phase, t) {
  if (!grounded) return clipPose(anim, "air", 0);
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

/** Adds an upper-body stance (relative to the rest pose) over a pose. */
export function addStance(anim, pose, name) {
  if (!name) return pose;
  const st = clipPose(anim, name, 0);
  return pose.map((v0, i) => v0 + st[i] - anim.rest[i]);
}

/** Blends action clip `name` at time t over pose with weight w (upper-only
 * clips leave the legs and root alone). */
export function blendAction(anim, pose, name, t, w) {
  const c = anim.clips[name];
  const act = clipPose(anim, name, t);
  return pose.map((v0, i) => {
    if (c.mask === "upper" && !anim.upper[i]) return v0;
    // Root turns the shorter way round, so a roll's 360 blends out as 0.
    const d = i < 2 ? (act[i] - v0 + 900) % 360 - 180 : act[i] - v0;
    return v0 + d * w;
  });
}

/** Weight of an action at time t: a quick blend in and out. */
export function actionWeight(t, loop, hold = false) {
  if (loop) return 1;
  if (hold) return Math.min(1, t / 0.08);
  return Math.max(0, Math.min(1, t / 0.08, (1 - t) / 0.15));
}
