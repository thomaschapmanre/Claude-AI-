const test = require('node:test');
const assert = require('node:assert/strict');
const JSZip = require('jszip');
const { agenda, templateBytes } = require('./load');

const E = agenda();
const settings = { property: 'Midtown', code: 'YFLPH', entity: 'Test LLC', cm: 'A. Manager', maint: '', leasing: '', callLabel: 'Tuesday 10/20/2026, 11:00 a.m.', week: 'Mon 10/12/2026 - Sun 10/18/2026' };
const base = { settings, reports: {}, checks: [], slots: {}, builtAt: '10/19/2026 9:00 AM' };
const docXml = async (input) => (await JSZip.loadAsync(await E.buildDocx(templateBytes(), input))).file('word/document.xml').async('string');
const points = [{ property: 'Maple Ridge Apartments (sample)', points: [{ text: 'Occupancy 93.5% (−2.2 pts vs Sep); target 95.0%.', question: 'What is driving the change?', source: 'MRI Box Score, Sep 2026 → Oct 2026', calculation: 'Change = 93.5% − 95.7% = −2.2 pts.' }] }];

test('without approved insights the agenda is unchanged', async () => {
  const a = await docXml(base);
  const b = await docXml({ ...base, talkingPoints: [] });
  assert.equal(a, b);
  assert.doesNotMatch(a, /Regional manager talking points/);
});

test('approved insights are added as one closing section, leaving the rest as it was', async () => {
  const plain = await docXml(base);
  const withPts = await docXml({ ...base, talkingPoints: points, talkingPointsNote: 'FICTIONAL SAMPLE DATA: delete this section before sending.' });
  const added = E.talkingPointsXml(points, 'FICTIONAL SAMPLE DATA: delete this section before sending.');
  const at = plain.lastIndexOf('<w:sectPr');
  assert.equal(withPts, plain.slice(0, at) + added + plain.slice(at));
  for (const t of ['Regional manager talking points', 'Maple Ridge Apartments (sample)', 'Occupancy 93.5%', 'Ask: ', 'What is driving the change?', 'Source: MRI Box Score, Sep 2026 → Oct 2026', 'FICTIONAL SAMPLE DATA']) assert.ok(withPts.includes(t), t);
  assert.ok(withPts.trimEnd().endsWith('</w:sectPr></w:body></w:document>'));
});

test('talking point text is escaped for Word', () => {
  const x = E.talkingPointsXml([{ property: 'A & B <Court>', points: [{ text: 'R&M "over" <budget>', source: 's' }] }]);
  assert.match(x, /A &amp; B &lt;Court&gt;/);
  assert.match(x, /R&amp;M &quot;over&quot; &lt;budget&gt;/);
});
