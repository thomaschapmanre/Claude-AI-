const test = require('node:test');
const assert = require('node:assert/strict');
const { market } = require('./load');

const M = market();
const S = () => JSON.parse(JSON.stringify(M.SAMPLE));
const analyze = (d, id, opts = {}) => M.analyzeProperty({ property: d.properties.find((p) => p.id === id), registry: d.registry, compSet: d.compSets[id] || null, surveys: d.surveys, today: opts.today || d.today, settings: opts.settings });
const all = (d, opts) => d.properties.map((p) => analyze(d, p.id, opts));
const group = (a, beds) => a.groups.find((g) => g.beds === beds);

test('each property has its own competitive set and survey', () => {
  const d = S();
  const mid = analyze(d, 'midtown'), oak = analyze(d, 'oak-hollow');
  assert.deepEqual(mid.compSet.approved, ['alpha-commons', 'beta-place', 'gamma-flats']);
  assert.deepEqual(oak.compSet.approved, ['delta-gardens', 'echo-ridge']);
  assert.ok(mid.latest.every((r) => r.compId === 'subject' || mid.compSet.approved.includes(r.compId)));
  // a survey saved for one property never shows up in another, even for a shared competitor
  d.surveys.push({ id: 'oak-hollow__2026-10-12', propertyId: 'oak-hollow', date: '2026-10-12', rows: [{ compId: 'alpha-commons', beds: 2, askingRent: 999, verifiedAt: '2026-10-12', confidence: 'verified' }] });
  assert.equal(analyze(d, 'midtown').latest.find((r) => r.compId === 'alpha-commons' && r.beds === 2).askingRent, 1825);
  // pine terrace and oak hollow share echo-ridge but keep separate surveys
  assert.notDeepEqual(analyze(d, 'pine-terrace').latest.map((r) => r.verifiedAt), analyze(d, 'oak-hollow').latest.map((r) => r.verifiedAt));
});

test('approved competitors are saved and reused; rejected ones are not suggested again', () => {
  const d = S(), p = d.properties.find((x) => x.id === 'willow-court');
  const reg = [...d.registry, { id: 'south-new', name: 'South New (sample)', submarket: 'Sample South' }];
  const saved = { approved: ['fox-run'], rejected: ['glen-park'], distances: {} };
  const set = M.effectiveCompSet(p, reg, saved);
  assert.deepEqual(set.approved, ['fox-run']);
  const c = M.candidates(p, reg, set).map((x) => x.comp.id);
  assert.ok(c.includes('south-new') && c.includes('hill-view'));
  assert.ok(!c.includes('fox-run') && !c.includes('glen-park'));
  assert.match(M.candidates(p, reg, set).find((x) => x.comp.id === 'south-new').why.join(' '), /same submarket/);
});

test('an earlier comp list seeds the set until one is saved', () => {
  const reg = [{ id: 'a', name: 'A', sets: ['midtown'] }, { id: 'b', name: 'B', sets: [] }];
  const set = M.effectiveCompSet({ id: 'midtown', name: 'Midtown' }, reg, null);
  assert.deepEqual(set.approved, ['a']);
  assert.equal(set.saved, false);
  assert.deepEqual(M.effectiveCompSet({ id: 'midtown', name: 'Midtown' }, reg, { approved: ['b'], rejected: [] }).approved, ['b']);
});

test('duplicate competitors are caught by name or address', () => {
  const reg = [{ id: 'alpha', name: 'Alpha Commons Apartments', address: '1 Main Street, Townville' }];
  assert.equal(M.findDuplicate(reg, { name: 'The Alpha Commons' }).id, 'alpha');
  assert.equal(M.findDuplicate(reg, { name: 'Different Name', address: '1 Main St' }).id, 'alpha');
  assert.equal(M.findDuplicate(reg, { name: 'Beta Place', address: '9 Other Rd' }), null);
  assert.equal(M.newCompId([{ id: 'beta-place' }], 'Beta Place'), 'beta-place-2');
});

test('survey history: changes since the previous survey', () => {
  const a = analyze(S(), 'midtown');
  assert.deepEqual(a.dates, ['2026-10-11', '2026-10-10', '2026-09-12']);
  const down = a.changes.filter((c) => c.type === 'rent_down').map((c) => [c.name, c.beds, c.from, c.to]);
  assert.deepEqual(down, [['Alpha Commons (sample)', 1, 1580, 1540], ['Alpha Commons (sample)', 2, 1890, 1825]]);
  const conc = a.changes.find((c) => c.type === 'concession_new');
  assert.equal(conc.compId, 'beta-place');
  assert.ok(a.findings.some((f) => f.kind === 'concession_new' && /None was recorded on 9\/12\/2026/.test(f.text)));
  assert.ok(a.findings.some((f) => f.kind === 'competitor_rent_down' && f.url === 'https://example.com/alpha' && f.date === '2026-10-10'));
});

test('rent comparisons only use the same bedroom count', () => {
  const a = analyze(S(), 'midtown');
  assert.equal(group(a, 0).ours, null);                     // the studio is never compared with our rents
  assert.equal(group(a, 0).position, 'our rent not on file');
  assert.deepEqual(group(a, 2).used.map((r) => r.beds), [2, 2, 2]);
  assert.equal(group(a, 2).asking.min, 1760);
  // a competitor with two 2-bed plans counts once, at its lowest plan
  const d = S();
  d.surveys[1].rows.push({ compId: 'alpha-commons', beds: 2, baths: 2, sqft: 1250, plan: 'B3', askingRent: 2300, verifiedAt: '2026-10-10', confidence: 'verified' });
  const g = group(analyze(d, 'midtown'), 2);
  assert.equal(g.asking.n, 3);
  assert.equal(g.used.find((r) => r.compId === 'alpha-commons').askingRent, 1825);
});

test('sample size: one competitor is not a market; two give a range; three give a median', () => {
  assert.equal(group(analyze(S(), 'oak-hollow'), 2).position, 'one competitor');
  assert.equal(group(analyze(S(), 'oak-hollow'), 2).asking.median, null);
  assert.match(group(analyze(S(), 'oak-hollow'), 2).sample, /Only one competitor/);
  const w = group(analyze(S(), 'willow-court'), 2);
  assert.equal(w.asking.n, 2); assert.equal(w.asking.median, null); assert.equal(w.asking.average, null);
  const m = group(analyze(S(), 'midtown'), 2);
  assert.equal(m.asking.median, 1825); assert.equal(m.asking.average, 1865);
});

test('asking and effective rents are separate, with the calculation shown', () => {
  const r = analyze(S(), 'midtown').latest.find((x) => x.compId === 'beta-place' && x.beds === 2);
  assert.equal(r.askingRent, 2010);
  assert.equal(Math.round(r.effective.value), 1797);
  assert.match(r.effective.calc, /6 × 7 ÷ 30\.42 = 1\.38 months free; \$2,010 × \(13 − 1\.38\) ÷ 13 = \$1,797/);
  assert.equal(M.effectiveRent(1500, { type: 'free_months', value: 1, termMonths: null }).value, null);
  assert.match(M.effectiveRent(1500, { type: 'free_months', value: 1 }).note, /lease term is not recorded/);
  assert.equal(M.effectiveRent(1500, { type: 'percent_off_monthly', value: 10 }).value, 1350);
  assert.equal(M.effectiveRent(1500, { type: 'amount_off_once', value: 600, termMonths: 12 }).value, 1450);
  assert.equal(M.effectiveRent(1500, { type: 'other', text: 'Look and lease special' }).value, null);
});

test('stale figures are flagged and left out, never used as current', () => {
  const p = analyze(S(), 'pine-terrace');
  assert.equal(group(p, 2).asking, null);
  assert.match(group(p, 2).sample, /last verified 7\/30\/2026, 76 days ago/);
  assert.ok(p.findings.some((f) => f.kind === 'survey_stale'));
  assert.ok(p.findings.some((f) => f.kind === 'our_rent_stale'));
  assert.equal(p.needsRefresh, true);
  // the same data is current when the stale limit is raised
  assert.equal(group(analyze(S(), 'pine-terrace', { settings: { staleDays: 90 } }), 2).asking.n, 1);
});

test('unverified and unpublished rents are left out and explained', () => {
  assert.match(group(analyze(S(), 'willow-court'), 2).sample, /Hill View \(sample\) \(unverified\)/);
  assert.match(group(analyze(S(), 'oak-hollow'), 2).sample, /Echo Ridge \(sample\) \(no rent published\)/);
});

test('missing is not zero: blank rent is missing, $0 is rejected', () => {
  const blank = M.cleanRow({ compId: 'x', beds: '2', askingRent: '', verifiedAt: '2026-10-01', confidence: 'verified' }, '2026-10-14');
  assert.deepEqual(blank.errors, []); assert.equal(blank.row.askingRent, null);
  assert.match(M.cleanRow({ compId: 'x', beds: '2', askingRent: '0', verifiedAt: '2026-10-01' }, '2026-10-14').errors.join(), /Asking rent "0" is not valid/);
  const studio = M.cleanRow({ compId: 'x', beds: '0', askingRent: '1100', verifiedAt: '2026-10-01' }, '2026-10-14');
  assert.equal(studio.row.beds, 0);
  assert.match(M.cleanRow({ compId: 'x', beds: '1', askingRent: '1', verifiedAt: '2026-12-01' }, '2026-10-14').errors.join(), /in the future/);
  assert.match(M.cleanRow({ compId: 'x', beds: '1', askingRent: '1', verifiedAt: '' }, '2026-10-14').errors.join(), /Last verified date is required/);
  assert.equal(M.cleanRow({ compId: 'x', beds: '1', verifiedAt: '2026-10-01', confidence: 'certain' }, '2026-10-14').row.confidence, 'unverified');
});

test('pricing gaps are flagged only when outside the range and material', () => {
  const f = analyze(S(), 'willow-court').findings.find((x) => x.kind === 'our_rent_above');
  assert.match(f.text, /\$1,350 is above the comparable range of \$1,240–\$1,270 \(2 competitors\) by \+\$80 \(\+6\.3%\)/);
  assert.match(f.text, /not a pricing recommendation/);
  assert.equal(analyze(S(), 'willow-court', { settings: { materialityPct: 7 } }).findings.find((x) => x.kind === 'our_rent_above'), undefined);
  assert.equal(group(analyze(S(), 'midtown'), 2).position, 'within range');
});

test('amenity gaps come only from recorded amenity lists', () => {
  const a = analyze(S(), 'midtown');
  assert.equal(a.amenities.comps, 3);
  assert.deepEqual(a.amenities.disadvantages.map((x) => x.amenity), ['Garage']);
  assert.ok(a.amenities.advantages.some((x) => x.amenity === 'Pet friendly'));
  assert.equal(analyze(S(), 'oak-hollow').amenities, null);
});

test('CSV import: validation, new competitors and duplicate detection', () => {
  const d = S();
  const csv = 'competitor,address,beds,baths,asking_rent,verified_date,confidence,distance_miles\nOur property,,2,1,1460,2026-10-12,verified,\nDelta Gardens (sample) Apartments,,2,1,1400,2026-10-12,verified,0.6\nNew Place (sample),5 New Rd,1,1,1100,2026-10-12,partially verified,2\nDelta Gardens (sample),,2,1,1400,2026-10-12,verified,\nBroken,,x,1,1,2026-10-12,verified,\n';
  const parsed = M.parseCsv(csv);
  assert.deepEqual(parsed.errors, []);
  const res = M.importRecords(parsed.records, { registry: d.registry, subject: d.properties.find((p) => p.id === 'oak-hollow'), today: d.today });
  assert.deepEqual(res.rows.map((r) => r.compId), ['subject', 'delta-gardens', 'new-place-sample']);
  assert.deepEqual(res.newCompetitors.map((c) => c.name), ['New Place (sample)']);
  assert.equal(res.errors.length, 2);
  assert.match(res.errors[0], /Line 5: duplicate/);
  assert.match(res.errors[1], /Line 6: Bedrooms "x"/);
  assert.equal(M.parseCsv(csv).key, parsed.key);                       // same file → same key → blocked on re-import
  assert.notEqual(M.parseCsv(csv.replace('1460', '1465')).key, parsed.key);
  assert.match(M.parseCsv('name,rent\nA,1').errors[0], /Missing column/);
});

test('older starting-rent history becomes partially verified rows, by bedroom count only', () => {
  const rows = M.legacyRows({ sourceUrl: 'https://example.com/list', history: { '2026-10-11': { b1: 1500, b2: null, b3: 2100 } } }, 'x');
  assert.deepEqual(rows.map((r) => [r.beds, r.askingRent, r.confidence, r.baths]), [[1, 1500, 'partially verified', null], [3, 2100, 'partially verified', null]]);
});

test('office and regional summaries follow office changes and keep Midtown separate', () => {
  const d = S();
  let s = M.summarize(all(d));
  assert.deepEqual(s.offices.map((o) => o.office), ['Midtown', 'Sample Office A', 'Sample Office B']);
  assert.deepEqual(s.offices[2].properties[0].above, ['2 bed']);
  assert.equal(s.region.above, 1); assert.equal(s.region.newConcessions, 1); assert.equal(s.region.needsRefresh, 1);
  d.properties.find((p) => p.id === 'willow-court').office = 'Sample Office A';
  d.properties.find((p) => p.id === 'midtown').office = 'Sample Office A';      // Midtown stays separate regardless
  s = M.summarize(all(d));
  assert.deepEqual(s.offices.map((o) => [o.office, o.properties.length]), [['Midtown', 1], ['Sample Office A', 3]]);
  assert.equal(s.offices[1].above, 1);
  delete d.properties.find((p) => p.id === 'oak-hollow').office;
  assert.ok(M.summarize(all(d)).offices.some((o) => o.office === 'Unassigned'));
});

test('Word agenda groups: office → property → actionable points, with exclusions', () => {
  const an = all(S());
  const g = M.agendaGroups(an, {});
  assert.deepEqual(g.map((o) => o.office), ['Midtown', 'Sample Office A', 'Sample Office B']);
  const mid = g[0].properties[0];
  assert.ok(mid.points.every((p) => p.source && p.date));
  assert.ok(mid.points.some((p) => p.url === 'https://example.com/alpha'));
  const drop = an[0].findings.find((f) => f.kind === 'amenity_gap');
  const g2 = M.agendaGroups(an, { [M.findingId(drop)]: true });
  assert.equal(g2[0].properties[0].points.length, mid.points.length - 1);
  // a property with no survey at all is listed once under its office instead of as a point
  const d = S(); d.properties.push({ id: 'new-one', name: 'New One (sample)', office: 'Sample Office B', rents: {} });
  const g3 = M.agendaGroups(all(d), {});
  assert.deepEqual(g3.find((o) => o.office === 'Sample Office B').missing, ['New One (sample)']);
});
