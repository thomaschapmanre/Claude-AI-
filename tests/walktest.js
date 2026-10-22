const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
const NM = path.dirname(require.resolve('three/package.json')); // npm i three@0.160.0 playwright
const WEB = process.argv[2], OUT = process.argv[3];
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] }).catch(() => chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] }));
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await p.route('**/*', r => {
    const u = r.request().url();
    if (u.startsWith('https://cdn.jsdelivr.net/npm/three@0.160.0/')) return r.fulfill({ path: path.join(NM, u.split('three@0.160.0/')[1]), contentType: 'text/javascript' });
    if (u.startsWith('https://fonts.')) return r.abort();
    if (u.startsWith('http://t/')) { const f = path.join(WEB, u.slice(9) || 'index.html'); return r.fulfill({ path: f, contentType: f.endsWith('.html') ? 'text/html; charset=utf-8' : f.endsWith('.jpg') ? 'image/jpeg' : 'text/javascript' }); }
    r.continue();
  });
  await p.goto('http://t/index.html');
  await p.waitForFunction('window.__ready', null, { timeout: 120000 });
  await p.waitForTimeout(500);
  const res = {};
  res.spawnRoom = await p.evaluate('window.__room');
  await p.screenshot({ path: OUT + '/walk_entry.png' });
  const ft = 0.3048;
  // waypoints in plan feet; [x, z, expected room or null]
  const R = [[1.7,27],[2.5,19.2],[9.3,18.6],[9.3,4,"Living / Kitchen"],[8.7,0.5],[8.7,-2.7,"Balcony"],[9.7,-2.7],[11.6,-1.3,"Mech closet"],
    [9.7,-2.7],[8.7,0.5],[9.3,2],[13.6,1.5,"Nook"],[16.0,1.5],[18.4,1.5],[18.4,-3,"Primary bedroom"],[18.4,1.8],[16.2,1.8],[16.2,4.5],[14.5,8,"Primary walk-in"],
    [16.2,4.5],[16.2,1.8],[21.7,1.8],[21.7,5],[23,7,"Primary bath"],[21.7,5],[21.7,1.8],[16.0,1.5],[13.6,1.5],[9.3,2],[9.3,18.6],
    [14.8,18.4],[14.8,15.4,"Laundry"],[14.8,18.4],[18,18.4,"Hall"],[20.5,19.4],[23,19.4],[23,13,"Second bath"],[23,19.4],[20.5,19.4],[16.6,18.6],[16.6,22.6],[18.5,23.5,"Second bedroom"],
    [18.5,28.5],[16.8,28.5],[16.8,33],[19,35,"Second walk-in"],[16.8,33],[16.8,28.5],[18.5,28.5],[18.5,23.5],[16.6,22.6],[16.6,18.6],[9.3,18.6],[2.5,19.2],[2.5,27],[9,27,"Living / Kitchen"],
    [2.5,27],[1.7,30],[1.7,33.4,"Entry"],[4.5,32.9,"Water heater closet"]];
  res.fails = [];
  for (const [x, z, room] of R) {
    const r = await p.evaluate(([tx, tz]) => {
      let pos;
      for (let i = 0; i < 2000; i++) {
        pos = window.__walk(0, 0);
        const dx = tx - pos[0], dz = tz - pos[1], d = Math.hypot(dx, dz);
        if (d < 0.03) break;
        const st = Math.min(0.04, d);
        const before = pos; pos = window.__walk(dx / d * st, dz / d * st);
        if (pos[0] === before[0] && pos[1] === before[1]) break;
      }
      return pos;
    }, [x * ft, z * ft]);
    const off = Math.hypot(r[0] - x * ft, r[1] - z * ft);
    await p.waitForTimeout(40);
    const got = await p.evaluate('window.__roomNow()');
    if (off > 0.1 || (room && got !== room)) res.fails.push({ target: [x, z], stuckAt: [+(r[0]/ft).toFixed(1), +(r[1]/ft).toFixed(1)], room: got, want: room });
    if (room === "Balcony" || room === "Primary bedroom" || room === "Second bedroom") await p.screenshot({ path: OUT + '/walk_' + room.replace(/ /g, '_').toLowerCase() + '.png' });
  }
  res.legs = R.length;
  console.log(JSON.stringify(res), 'errors:', JSON.stringify(errs));
  await b.close();
})();
