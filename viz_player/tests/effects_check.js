// Błyski aktywności i statystyki linków z engine.js kontra wzorzec policzony w Pythonie z eventów. Uruchamia test_effects.py:
//   node effects_check.js <katalog strony> <expected.json>
// expected.json: {flowFactor, flashes: [{t, life, types, ages, names}], stats: [{t, W, n, nf, len, tt, speed, flow}]}
// speed i flow: wartość na link albo null (brak ruchu).
const fs = require("fs");
const path = require("path");
const {Engine} = require("../engine.js");

const site = process.argv[2];
const expected = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

const get = async (name, kind) => {
  const raw = fs.readFileSync(path.join(site, name.split("?")[0]));
  if (kind === "json") return JSON.parse(raw.toString("utf8"));
  return raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
};
const arr = async (name, Ctor) => new Ctor(await get(name, "buf"));
const near = (a, b) => Math.abs(a - b) < 1e-6 * Math.max(1, Math.abs(b));

(async () => {
  const linkLL = await arr("link_ll.bin", Float64Array);
  const attr = await arr("link_attr.bin", Float32Array);
  const eng = await Engine.load("data/", get, null, linkLL);
  const on = new Uint8Array(eng.classKeys.length).fill(1);
  const out = {flashes: [], stats: [], meta: {hasActs: eng.hasActs, types: eng.actTypes, starts: eng.actStarts, back: eng.back}};
  for (const row of expected.flashes) {
    await eng.want(row.t);
    const typeOn = Uint8Array.from(eng.actTypes, (n) => (row.types.indexOf(n) >= 0 ? 1 : 0));
    const fl = eng.flashes(row.t, row.life, typeOn);
    const order = Array.from({length: fl.n}, (_, i) => i).sort((a, b) => fl.age[b] - fl.age[a] || fl.type[a] - fl.type[b]);
    const ages = order.map((i) => fl.age[i]), names = order.map((i) => eng.actTypes[fl.type[i]]);
    out.flashes.push({t: row.t, n_js: fl.n, n_py: row.ages.length, ok: JSON.stringify(ages) === JSON.stringify(row.ages) && JSON.stringify(names) === JSON.stringify(row.names)});
  }
  for (const row of expected.stats) {
    await eng.want(row.t);
    const ls = eng.linkStats(row.t, row.W, on);
    const r = {t: row.t, W: row.W, n: true, nf: true, len: true, tt: true, speed: true, flow: true};
    for (let l = 0; l < row.n.length; l++) {
      if (ls.n[l] !== row.n[l]) r.n = false;
      if (ls.nf[l] !== row.nf[l]) r.nf = false;
      if (!near(ls.len[l], row.len[l])) r.len = false;
      if (!near(ls.tt[l], row.tt[l])) r.tt = false;
    }
    const sp = eng.loadValues(ls, attr, "speed", row.W, expected.flowFactor, new Float32Array(row.n.length));
    const fw = eng.loadValues(ls, attr, "flow", row.W, expected.flowFactor, new Float32Array(row.n.length));
    for (let l = 0; l < row.n.length; l++) {
      const s = Number.isNaN(sp[l]) ? null : sp[l], f = Number.isNaN(fw[l]) ? null : fw[l];
      if ((s === null) !== (row.speed[l] === null) || (s !== null && Math.abs(s - row.speed[l]) > 1e-5)) r.speed = false;
      if ((f === null) !== (row.flow[l] === null) || (f !== null && Math.abs(f - row.flow[l]) > 1e-5)) r.flow = false;
    }
    out.stats.push(r);
  }
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
