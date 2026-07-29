#!/usr/bin/env node
/**
 * S254: reachability gate for assets/game/nova_drift.html.
 *
 * A wave in Nova Drift ends when the last enemy dies. So an enemy the player
 * cannot reach does not just look wrong — it hangs the run permanently, and
 * the stranded unit goes on shooting from somewhere the player cannot see or
 * answer. Three separate movement entries shipped that bug at once:
 *
 *   * hover_advance derived its hover line from e.seed, the monotonically
 *     increasing spawn counter, instead of a 0..1 random — so by wave 12 the
 *     line was tens of thousands of pixels below the arena and every Iron
 *     Legion unit sank out of the world;
 *   * vine_grow anchored to its spawn point, which spawnEdgePos() puts 40px
 *     OUTSIDE the arena, and has speed 0 — three edges in four were fatal;
 *   * orbit_cluster derived its position from its anchor before wrapping that
 *     anchor, leaving position and anchor on opposite sides of the arena in a
 *     two-frame limit cycle.
 *
 * Those are three different mistakes with one shared shape, which is the
 * signal that reading the movement library is not a reliable way to catch
 * them. This runs it instead: every archetype, from every spawn edge, for two
 * simulated minutes, asserting that no unit is ever unreachable for longer
 * than a couple of seconds.
 *
 * It evaluates the real MOVEMENTS library out of the real HTML file rather
 * than a copy, so it cannot drift from what ships. No browser, no npm.
 *
 * Usage: node test/nova_drift_reachability.js [path/to/nova_drift.html]
 */
'use strict';
const fs = require('fs');
const path = require('path');

const GAME = process.argv[2] ||
  path.join(__dirname, '..', 'assets', 'game', 'nova_drift.html');
const src = fs.readFileSync(GAME, 'utf8');

// ---- pull the real library and roster out of the page ---------------------
function balanced(marker, open, close) {
  const i = src.indexOf(marker);
  if (i < 0) throw new Error('not found: ' + marker);
  let depth = 0, j = src.indexOf(open, i), k = j;
  while (k < src.length) {
    if (src[k] === open) depth++;
    else if (src[k] === close && --depth === 0) return src.slice(j, k + 1);
    k++;
  }
  throw new Error('unterminated: ' + marker);
}
function fn(name) {
  const m = new RegExp('function ' + name + '\\([^)]*\\)\\{').exec(src);
  if (!m) throw new Error('not found: function ' + name);
  let depth = 0, i = m.end = m.index + m[0].length - 1;
  while (i < src.length) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}' && --depth === 0) return src.slice(m.index, i + 1);
    i++;
  }
  throw new Error('unterminated: function ' + name);
}

// ---- the host the movement library runs against ---------------------------
// A portrait phone viewport: the tightest arena the game ships on, and so the
// one where an off-by-a-margin is most likely to strand something.
const W = 412, H = 892;
const TAU = Math.PI * 2;
const player = { x: W / 2, y: H * 0.7, r: 12, vx: 0, vy: 0 };
const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const rand = (a, b) => a + Math.random() * (b - a);
const factionOf = () => ({ ink: '#ffffff' });
function angDiff(a, b) {
  let d = a - b;
  while (d > Math.PI) d -= TAU;
  while (d < -Math.PI) d += TAU;
  return d;
}
// Movement may call into these; none of them influence position.
const nearEnemies = () => [];
const pushTrail = () => {};
const spawnHazard = () => {};
const spawnParticles = () => {};
const sfxAttack = () => {};
const perfLevel = () => 'high';

// The real onScreen / wrapEnemy / enforceReachable, verbatim from the page.
// Bound to consts rather than eval'd as declarations: under 'use strict' an
// eval'd function declaration is scoped to the eval and would be invisible to
// the movement library below.
const REACH_GRACE = Number(/const REACH_GRACE = (\d+)/.exec(src)[1]);
const REACH_SNAP2 = eval(/const REACH_SNAP2 = ([^;]+);/.exec(src)[1]);
const hyp = eval('(' + fn('hyp') + ')');
const onScreen = eval('(' + fn('onScreen') + ')');
const wrapEnemy = eval('(' + fn('wrapEnemy') + ')');
const enforceReachable = eval('(' + fn('enforceReachable') + ')');

const ENEMIES = eval(balanced('const ENEMIES =', '[', ']'));
const MOVEMENTS = eval('(' + balanced('const MOVEMENTS = {', '{', '}') + ')');

// ---- the real spawn paths -------------------------------------------------
function spawnEdgePos(edge) {
  if (edge === 0) return { x: rand(0, W), y: -40 };
  if (edge === 1) return { x: W + 40, y: rand(0, H) };
  if (edge === 2) return { x: rand(0, W), y: H + 40 };
  return { x: -40, y: rand(0, H) };
}

// Mirrors spawnEnemy()'s field initialisation for everything movement reads.
let enemySeq = 1;
function makeEnemy(def, pos, wave) {
  const e = {};
  e.active = true; e.def = def; e.faction = def.faction;
  e.x = pos.x; e.y = pos.y;
  e.r = def.radius; e.scale = 1;
  e.maxHp = e.hp = Math.max(1, Math.round(def.hp * (1 + (wave - 1) * 0.035)));
  const sp = def.speed * (1 + (wave - 1) * 0.012);
  const ang = Math.atan2(H / 2 - e.y + rand(-80, 80), W / 2 - e.x + rand(-80, 80));
  e.vx = Math.cos(ang) * sp; e.vy = Math.sin(ang) * sp;
  e.rot = rand(0, TAU); e.vr = rand(-0.04, 0.04);
  e.t = 0; e.fireTimer = rand(50, 140); e.phase = 0;
  e.seed = enemySeq++; e.rnd = Math.random(); e.offT = 0;
  e.state = 0; e.stateTimer = rand(20, 60);
  e.shieldHp = e.maxShieldHp = def.shield || 0;
  e.telegraph = 0; e.flash = 0; e.squash = 0.55; e.alpha = 1;
  e.anchorX = e.x; e.anchorY = e.y; e.linkTo = null; e.ownerId = 0;
  e.trailN = 0; e.growth = 0;
  return e;
}

// The spawn counter by the time a wave-N fight starts. Its exact value is not
// the point — the point is that it is large, which is what broke hover_advance
// while every early-wave playtest looked fine.
function seqAtWave(w) {
  let n = 1;
  for (let i = 1; i < w; i++) n += Math.round((16 + i * 3.2) / 3);
  return n;
}

// ---- the run --------------------------------------------------------------
const STEPS = 7200;        // two minutes at 60Hz
const TRIALS_PER_EDGE = 25;
const WAVE = 12;           // the wave the stranding was first reported on
const EDGE = ['top', 'right', 'bottom', 'left'];

// A unit legitimately leaves the arena — a dive, an edge wrap — for around a
// second. Past this it is not travelling, it is stranded.
const MAX_OFFSCREEN = 4 * 60;

/**
 * Two passes, because "no wave can hang" and "the movement library is correct"
 * are different claims and only the first one is enforced by the safety net.
 *
 *   withNet=true  — what actually ships. Hard limit: nothing may sit outside
 *                   the arena longer than MAX_OFFSCREEN. This is the promise
 *                   to the player.
 *   withNet=false — the movement library alone. The limit here is only that a
 *                   unit must reach the arena at all, ever, from every spawn
 *                   edge. It is deliberately loose: the ±70px wrap band lets a
 *                   slow drifter travel the long way round for tens of
 *                   seconds, which is by design and is exactly what the net is
 *                   there to shorten. What it does catch is a unit that is
 *                   never reachable — the shape all three shipped bugs had —
 *                   so the net can never quietly paper over a total failure.
 */
function sweep(withNet) {
  const rows = [];
  for (const def of ENEMIES) {
    const mv = MOVEMENTS[def.movement];
    if (!mv) continue;                    // covered by nova_drift_check.py
    let worstGap = 0, worstEdge = 0, neverSeen = 0, neverEdge = -1;
    for (let edge = 0; edge < 4; edge++) {
      for (let trial = 0; trial < TRIALS_PER_EDGE; trial++) {
        enemySeq = seqAtWave(WAVE);
        const e = makeEnemy(def, spawnEdgePos(edge), WAVE);
        let gap = 0, seen = false;
        for (let s = 0; s < STEPS; s++) {
          mv(e, 1);
          if (withNet) enforceReachable(e, 1);
          if (onScreen(e.x, e.y, 0)) { gap = 0; seen = true; }
          else if (++gap > worstGap) { worstGap = gap; worstEdge = edge; }
        }
        if (!seen) { neverSeen++; if (neverEdge < 0) neverEdge = edge; }
      }
    }
    rows.push({ id: def.id, mv: def.movement, gap: worstGap, edge: worstEdge,
                neverSeen, neverEdge });
  }
  rows.sort((a, b) => b.neverSeen - a.neverSeen || b.gap - a.gap);
  return rows;
}

const failures = [];

// ---- pass 1: as shipped ---------------------------------------------------
const shipped = sweep(true);
console.log('PASS 1 — as shipped (movement + reachability net)');
console.log('wave %d, %d spawns per archetype, %ds simulated each\n',
  WAVE, 4 * TRIALS_PER_EDGE, STEPS / 60);
for (const r of shipped.slice(0, 6)) {
  console.log('  %s %s %ss  (worst edge: %s)',
    r.id.padEnd(20), r.mv.padEnd(16), (r.gap / 60).toFixed(1), EDGE[r.edge]);
}
console.log('\n  %d archetypes, roster-wide worst %ss off-screen (limit %ss)',
  shipped.length, (shipped[0].gap / 60).toFixed(1), (MAX_OFFSCREEN / 60).toFixed(1));
for (const r of shipped) {
  if (r.neverSeen) {
    failures.push(r.id + ' (' + r.mv + '): NEVER reachable from the ' +
      EDGE[r.neverEdge] + ' edge, ' + r.neverSeen + '/' + (4 * TRIALS_PER_EDGE) + ' spawns');
  } else if (r.gap > MAX_OFFSCREEN) {
    failures.push(r.id + ' (' + r.mv + '): ' + (r.gap / 60).toFixed(1) +
      's off-screen from the ' + EDGE[r.edge] + ' edge');
  }
}

// ---- pass 2: the movement library on its own ------------------------------
const bare = sweep(false);
const stranded = bare.filter(r => r.neverSeen);
console.log('\nPASS 2 — movement library alone (net disabled)');
console.log('  roster-wide worst %ss off-screen; %d archetypes never reach the arena',
  (bare[0].gap / 60).toFixed(1), stranded.length);
for (const r of stranded) {
  failures.push(r.id + ' (' + r.mv + '): cannot reach the arena unaided from the ' +
    EDGE[r.neverEdge] + ' edge — the net should be a backstop, not the only thing ' +
    'keeping it killable');
}

if (failures.length) {
  console.log('\nFAILED (%d) — a wave does not end until the last enemy dies, so', failures.length);
  console.log('an enemy the player cannot reach hangs the run:');
  for (const f of failures) console.log('  - ' + f);
  process.exit(1);
}
console.log('\nnova_drift.html: every archetype stays reachable from every spawn edge');
