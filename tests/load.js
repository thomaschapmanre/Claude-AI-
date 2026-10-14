// Loads scripts straight out of tools/Command Deck.html so the tests exercise the shipped code.
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'tools', 'Command Deck.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?: id="([^"]*)")?>([\s\S]*?)<\/script>/g)].map((m) => ({ id: m[1], code: m[2] }));

function load(match) {
  const s = scripts.find((x) => x.id === match || x.code.includes(match));
  if (!s) throw new Error('script not found: ' + match);
  const module = { exports: {} };
  new Function('module', 'require', s.code)(module, require);
  return module.exports;
}

module.exports = {
  html,
  insights: () => load('region-insights-engine'),
  market: () => load('market-survey-engine'),
  agenda: () => load('Call Agenda engine'),
  templateBytes: () => Buffer.from(/const TEMPLATE_B64 = "([^"]+)"/.exec(html)[1], 'base64')
};
