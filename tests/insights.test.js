const test = require('node:test');
const assert = require('node:assert/strict');
const { insights } = require('./load');

const RI = insights();
const sample = () => JSON.parse(JSON.stringify(RI.SAMPLE.properties));
const run = (opts = {}) => RI.analyze({ properties: sample(), ...opts });
const of = (r, id) => r.findings.filter((f) => f.propertyId === id);
const rule = (r, id, name) => r.findings.find((f) => f.propertyId === id && f.rule === name);

test('uses the latest month on file and the month before it', () => {
  const r = run();
  assert.equal(r.period, '2026-10');
  assert.deepEqual(RI.allPeriods(sample()), ['2026-10', '2026-09', '2026-08']);
});

test('a healthy community produces no findings', () => {
  assert.equal(of(run(), 'briarwood').length, 0);
});

test('declining occupancy is flagged with the prior month, target and calculation', () => {
  const f = rule(run(), 'maple-ridge', 'occupancy');
  assert.equal(f.severity, 'High');
  assert.match(f.title, /down 2\.2 pts to 93\.5%/);
  assert.match(f.calculation, /93\.5% − 95\.7% = −2\.2 pts/);
  assert.equal(f.source.report, 'MRI Box Score');
  assert.equal(f.source.period, 'Sep 2026 → Oct 2026');
});

test('weak leasing pipeline lists every condition it found', () => {
  const f = rule(run(), 'lakeview', 'pipeline');
  assert.match(f.observation, /renewal conversion 30\.0% is below the 50\.0% target/);
  assert.match(f.observation, /move-outs \(9\) exceed move-ins \(3\)/);
  assert.match(f.calculation, /6 ÷ 20 × 100 = 30\.0%/);
  assert.equal(f.severity, 'High');
});

test('rising delinquency compares months and shows share of revenue', () => {
  const f = rule(run(), 'maple-ridge', 'delinquency');
  assert.match(f.calculation, /\$24,900 − \$18,200 = \+\$6,700 \(36\.8%\)/);
  assert.match(f.calculation, /\$24,900 ÷ \$236,270 × 100 = 10\.5%/);
  assert.match(f.source.report, /MRI Aged Delinquency/);
});

test('unresolved maintenance and negative feedback are flagged', () => {
  const r = run();
  assert.match(rule(r, 'cedar-glen', 'maintenance').calculation, /14 − 5 = \+9/);
  const fb = rule(r, 'cedar-glen', 'feedback');
  assert.match(fb.observation, /3\.7 is below the 4\.0 target/);
  assert.match(fb.observation, /4 negative reviews/);
});

test('unusual expenses are flagged per line with the variance math', () => {
  const f = rule(run(), 'harbor-point', 'expense:repairs-maintenance');
  assert.match(f.calculation, /\$21,400 − \$9,000 = \+\$12,400/);
  assert.match(f.title, /137\.8% over budget/);
  // lines within threshold are not flagged
  assert.equal(of(run(), 'harbor-point').filter((x) => x.category === 'Expenses').length, 1);
});

test('inconsistent numbers become data checks, not trends', () => {
  const f = rule(run(), 'harbor-point', 'check:occupancy');
  assert.equal(f.kind, 'data');
  assert.equal(f.severity, 'Data check');
  assert.match(f.calculation, /\(120 − 9\) ÷ 120 × 100 = 92\.5%/);
});

test('other cross-checks: renewals, delinquent units, budget variance, unit count', () => {
  const props = sample();
  const oct = props.find((p) => p.id === 'briarwood').months['2026-10'];
  oct.renewals.renewalsSigned = 6;            // more than the 4 expiring
  oct.delinquency.delinquentUnits = 70;       // more than 64 units
  oct.budget.budgetVariance = 4.0;            // actual vs budget says 1.1%
  oct.boxscore.units = 66; oct.boxscore.vacant = 4; // unit count changed; occupancy stays consistent-ish
  const r = RI.analyze({ properties: props });
  const rules = of(r, 'briarwood').map((f) => f.rule);
  for (const x of ['check:renewals', 'check:delinquent-units', 'check:budget', 'check:units']) assert.ok(rules.includes(x), x);
});

test('missing reports are listed and their checks are skipped', () => {
  const r = run();
  const f = rule(r, 'lakeview', 'missing');
  assert.match(f.observation, /MRI Aged Delinquency/);
  assert.equal(rule(r, 'lakeview', 'delinquency'), undefined);
});

test('targets are configurable and thresholds are inclusive', () => {
  // Briarwood is 96.9%: raising the target to 97 flags it, with the target in the evidence
  const f = rule(run({ targets: { occupancyTarget: 97 } }), 'briarwood', 'occupancy');
  assert.match(f.title, /below the 97\.0% target/);
  // Maple Ridge fell exactly 2.2 pts: a 2.2 threshold still flags, 2.3 does not (target lowered so only the drop counts)
  assert.ok(rule(run({ targets: { occupancyDropPts: 2.2, occupancyTarget: 90 } }), 'maple-ridge', 'occupancy'));
  assert.equal(rule(run({ targets: { occupancyDropPts: 2.3, occupancyTarget: 90 } }), 'maple-ridge', 'occupancy'), undefined);
});

test('an earlier month can be reviewed, and a first month says there is no prior', () => {
  const r = run({ period: '2026-08', targets: { occupancyTarget: 97 } });
  const f = rule(r, 'maple-ridge', 'occupancy');
  assert.match(f.calculation, /No prior month on file/);
  assert.equal(f.source.period, 'Aug 2026');
  // communities with no data on or before that month are left out
  assert.deepEqual(r.byProperty.map((g) => g.id), ['maple-ridge']);
});

test('every finding carries evidence, calculation, source, period, a question and a next step', () => {
  for (const f of run().findings) {
    for (const k of ['title', 'observation', 'why', 'calculation', 'question', 'nextStep', 'point']) assert.ok(f[k] && f[k].length > 10, `${f.id} ${k}`);
    assert.ok(f.evidence.length > 0, f.id);
    assert.ok(f.source.report && f.source.period, f.id);
  }
});

test('findings state figures, not guesses about causes', () => {
  const guessy = /\b(because|due to|caused by|likely|probably|clearly|definitely)\b/i;
  for (const f of run().findings) {
    assert.doesNotMatch(f.observation, guessy, f.id);
    assert.doesNotMatch(f.point, guessy, f.id);
  }
});

test('talking points include only approved findings, grouped by property, with edits', () => {
  const r = run();
  const occ = rule(r, 'maple-ridge', 'occupancy'), fb = rule(r, 'cedar-glen', 'feedback'), mt = rule(r, 'cedar-glen', 'maintenance');
  const groups = RI.talkingPoints(r, {
    [occ.id]: { status: 'approved', text: 'Occupancy slipped to 93.5%; ask for the vacant list.' },
    [fb.id]: { status: 'approved' },
    [mt.id]: { status: 'dismissed' }
  });
  assert.deepEqual(groups.map((g) => g.property), ['Cedar Glen Senior Living (sample)', 'Maple Ridge Apartments (sample)']);
  assert.equal(groups[1].points[0].text, 'Occupancy slipped to 93.5%; ask for the vacant list.');
  assert.equal(groups[0].points.length, 1);
  assert.match(groups[0].points[0].source, /Opiniion Resident Feedback, Sep 2026 → Oct 2026/);
  assert.deepEqual(RI.talkingPoints(r, {}), []);
});

test('works on saved report data that has only some reports', () => {
  const r = RI.analyze({ properties: [{ id: 'x', name: 'Test Court', months: {
    '2026-09': { boxscore: { occupancy: 97, units: 100, vacant: 3 } },
    '2026-10': { boxscore: { occupancy: 94, units: 100, vacant: 6 } } } }] });
  assert.deepEqual(r.findings.map((f) => f.rule).sort(), ['missing', 'occupancy']);
  assert.match(r.findings.find((f) => f.rule === 'missing').title, /6 reports not on file/);
});

test('empty input returns nothing instead of failing', () => {
  assert.deepEqual(RI.analyze({ properties: [] }).findings, []);
  assert.equal(RI.analyze({ properties: [] }).period, null);
});
