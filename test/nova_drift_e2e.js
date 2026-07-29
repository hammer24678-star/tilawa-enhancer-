#!/usr/bin/env node
/**
 * S254: end-to-end reachability check, in a real browser, on the real game.
 *
 * test/nova_drift_reachability.js is the CI gate: it evaluates the MOVEMENTS
 * library out of the HTML and simulates it directly, which needs nothing but
 * node and so runs anywhere. This is the deeper pass the repo has always kept
 * separate (see the header of nova_drift_check.py) — it boots the actual page
 * in headless Chromium, starts an actual run, spawns through the actual edge
 * spawner at the waves that froze, and watches the actual update loop.
 *
 * Two measures, because they fail differently:
 *
 *   worstSteps  — offT, the continuously-off-screen timer enforceReachable()
 *                 maintains. Exact, but it only exists because the net does.
 *   worstAgeMs  — how long the oldest currently-off-screen unit has been
 *                 ALIVE, from spawnT alone. A unit that has existed for
 *                 thirty seconds and is still outside the arena is stranded
 *                 whether or not anything is keeping score, and this is what
 *                 tells a stranded roster apart from a wave still spawning.
 *
 * Verified in both directions: it passes on the fixed build (worst strand
 * 1.9s) and fails on a build with the hover_advance seed bug reintroduced and
 * the net removed (units alive 30.4s, still unreachable).
 *
 * Not wired into CI — it needs Playwright and a browser. Run it by hand:
 *
 *   npm i -g playwright && npx playwright install chromium
 *   node test/nova_drift_e2e.js [path/to/nova_drift.html]
 */
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const path = require('path');
const GAME = path.resolve(process.argv[2] ||
  path.join(__dirname, '..', 'assets', 'game', 'nova_drift.html'));

const SUSPECTS = ['sentry_drone','flak_walker','railgunner','shield_bearer',
                  'swarm_launcher','iron_sentinel','command_node','solar_lance',
                  'pressure_wave','crystal_vine','spore','entropy_seed','cluster',
                  'cloaked_stalker','wailer','deepcaller'];
const LIMIT_STEPS = 4 * 60;   // the same 4s ceiling the offline simulator uses
const LIMIT_AGE_MS = 15000;   // a unit alive 15s and still outside is stranded

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    viewport: { width: 412, height: 892 }, deviceScaleFactor: 1,
    isMobile: true, hasTouch: true, offline: true,
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  // NOVA_FORCE_2D as well: headless software rendering runs the GL path at
  // ~12fps, which correctly trips the game's own "this WebView landed on a
  // software rasteriser" guard and reloads into Canvas2D mid-test, destroying
  // the execution context. Pin the renderer so the harness measures gameplay
  // rather than the fallback.
  await page.addInitScript(() => { window.NOVA_QA = true; window.NOVA_FORCE_2D = true; });
  await page.goto('file://' + GAME, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(1500);

  if (!await page.evaluate(() => !!(window.NOVA_TEST && window.NOVA_TEST.spawnEdge))) {
    console.log('FAIL: QA hooks missing'); await browser.close(); process.exit(1);
  }

  const startRun = async () => {
    await page.evaluate(() => {
      window.NOVA_TEST.buyAll();              // survivability: this must not end early
      document.getElementById('startBtn').click();
    });
    await page.waitForFunction(() => window.NOVA_STATS().running, null, { timeout: 15000 });
  };
  await startRun();
  console.log('  run started:', JSON.stringify(await page.evaluate(() => {
    const s = window.NOVA_STATS(); return { running: s.running, renderer: s.renderer };
  })));

  let failed = false, worstEver = 0, worstId = null;
  for (const wave of [12, 16]) {
    if (!await page.evaluate(() => window.NOVA_STATS().running)) await startRun();
    const spawned = await page.evaluate(({ w, ids }) => {
      window.NOVA_TEST.setWave(w);
      window.NOVA_TEST.killAll();
      let n = 0;
      for (const id of ids) n += window.NOVA_TEST.spawnEdge(id, 2);
      return n;
    }, { w: wave, ids: SUSPECTS });

    // The wave spawner keeps running, so there are almost always some freshly
    // spawned units still outside — "nothing is off-screen right now" is not
    // the assertion. The assertion is that no unit stays out there: both the
    // off-screen timer and the AGE of the oldest off-screen unit stay bounded.
    let peak = 0, peakId = null, peakAge = 0, peakAgeId = null, died = false;
    for (let t = 1; t <= 30; t++) {
      await page.waitForTimeout(1000);
      // Every third wave opens the relic picker and pauses the run until the
      // player chooses. Nothing moves while it is up, so an off-screen unit
      // freezes there and its age keeps climbing — a harness artifact, not a
      // strand. Pick a relic and skip the sample.
      const s = await page.evaluate(() => {
        const relic = document.getElementById('relicOverlay');
        if (relic && getComputedStyle(relic).display !== 'none') {
          const pick = relic.querySelector('.relicCard, button');
          if (pick) pick.click();
          return { skip: true };
        }
        const st = window.NOVA_STATS();
        if (st.paused) return { skip: true };
        return { off: window.NOVA_TEST.offscreen(), running: st.running };
      });
      if (s.skip) continue;
      if (s.off.worstSteps > peak) { peak = s.off.worstSteps; peakId = s.off.worstId; }
      if (s.off.worstAgeMs > peakAge) { peakAge = s.off.worstAgeMs; peakAgeId = s.off.worstAgeId; }
      if (!s.running) { died = true; break; }
    }
    const ok = peak <= LIMIT_STEPS && peakAge <= LIMIT_AGE_MS;
    if (!ok) failed = true;
    if (peak > worstEver) { worstEver = peak; worstId = peakId; }
    console.log(`  wave ${wave}: ${spawned} spawned from the arena edges | ` +
                `worst off-screen timer ${(peak / 60).toFixed(1)}s${peakId ? ' [' + peakId + ']' : ''} | ` +
                `oldest unit still outside ${(peakAge / 1000).toFixed(1)}s${peakAgeId ? ' [' + peakAgeId + ']' : ''}` +
                (died ? ' | run ended early' : '') + ` -> ${ok ? 'OK' : 'FAIL'}`);
  }

  console.log('  console errors:', errs.length ? errs.slice(0, 5) : 'none');
  await browser.close();
  if (failed || errs.length) {
    console.log(`\nFAILED — worst ${(worstEver / 60).toFixed(1)}s off-screen (${worstId})`);
    process.exit(1);
  }
  console.log(`\nPASS — every unit reached the arena; worst strand ${(worstEver / 60).toFixed(1)}s`);
  process.exit(0);
})();
