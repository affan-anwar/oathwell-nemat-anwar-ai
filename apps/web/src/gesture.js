// Motion-based swipe detection. It sees movement in the camera picture, not a specific hand,
// and it runs entirely in this browser. Frames are never stored or sent anywhere.
export const W = 32, H = 24;
export const SAFE_ACTIONS = ["navigate"]; // gestures may only change pages. Never publish, spend, delete or change permissions.

export function motionCentroid(prev, cur, thresh = 28) {
  let n = 0, sx = 0;
  for (let i = 0; i < cur.length; i++) {
    if (Math.abs(cur[i] - prev[i]) > thresh) { n++; sx += i % W; }
  }
  return { mass: n / cur.length, x: n ? sx / n / W : null };
}

// samples: [{t: ms, x: 0..1 or null, mass: 0..1}]. Returns "left" or "right" from the PERSON's point of view.
export function detectSwipe(samples, { minMass = 0.02, minTravel = 0.3, minMs = 120, maxMs = 1000 } = {}) {
  const act = samples.filter((s) => s.x !== null && s.mass >= minMass);
  if (act.length < 4) return null;
  const dt = act[act.length - 1].t - act[0].t;
  if (dt < minMs || dt > maxMs) return null;
  const travel = act[act.length - 1].x - act[0].x;
  if (Math.abs(travel) < minTravel) return null;
  let same = 0;
  for (let i = 1; i < act.length; i++) if (Math.sign(act[i].x - act[i - 1].x) === Math.sign(travel)) same++;
  if (same / (act.length - 1) < 0.7) return null; // the movement must be consistently one way
  // The camera picture is not mirrored: movement toward larger x is the person's LEFT.
  return travel > 0 ? "left" : "right";
}
