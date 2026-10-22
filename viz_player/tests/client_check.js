// Porównanie silnika klienta (viz_player/engine.js) z wzorcem z Pythona. Uruchamia test_client.py:
//   node client_check.js <katalog strony> <expected.json>
// expected.json: {times: [{t, track, lon, lat, speed, heading, link}], trails: [{track, t, path}], lookups: [...]}
const fs = require("fs");
const path = require("path");
const {Engine} = require("../engine.js");

const site = process.argv[2];
const expected = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const M = 111194.93;

const get = async (name, kind) => {
  const raw = fs.readFileSync(path.join(site, name));
  if (kind === "json") return JSON.parse(raw.toString("utf8"));
  return raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
};
const arr = async (name, Ctor) => new Ctor(await get(name, "buf"));

(async () => {
  const boot = await get("boot.json", "json");
  const linkLL = await arr("link_ll.bin", Float64Array);
  const curves = boot.nCurve
    ? {off: await arr("curve_off.bin", Int32Array), lon: await arr("curve_lon.bin", Float64Array), lat: await arr("curve_lat.bin", Float64Array)}
    : null;
  const eng = await Engine.load("data/", get, curves, linkLL);
  const on = new Uint8Array(eng.classKeys.length).fill(1);
  const out = {frames: [], trails: [], lookups: []};
  for (const row of expected.times) {
    await eng.want(row.t);
    const fr = eng.frame(row.t, on);
    const at = new Map();
    for (let i = 0; i < fr.n; i++) at.set(fr.track[i], i);
    const r = {t: row.t, n_js: fr.n, n_py: row.track.length, missing: 0, pos_m: 0, speed_rel: 0, heading: 0, link: 0};
    row.track.forEach((tr, k) => {
      const i = at.get(tr);
      if (i === undefined) { r.missing++; return; }
      const cl = Math.cos(row.lat[k] * Math.PI / 180);
      r.pos_m = Math.max(r.pos_m, Math.hypot((fr.lon[i] - row.lon[k]) * cl, fr.lat[i] - row.lat[k]) * M);
      r.speed_rel = Math.max(r.speed_rel, Math.abs(fr.speed[i] - row.speed[k]) / Math.max(row.speed[k], 1));
      let dh = Math.abs(fr.heading[i] - row.heading[k]);
      dh = Math.min(dh, 2 * Math.PI - dh);
      r.heading = Math.max(r.heading, dh);
      if (fr.link[i] !== row.link[k]) r.link++;
    });
    out.frames.push(r);
  }
  for (const row of expected.trails) {
    await eng.want(row.t, eng.tr.t0[row.track]);
    const got = eng.trail(row.track, row.t);
    const r = {track: row.track, n_js: got.length, n_py: row.path.length, pos_m: 0};
    for (let i = 0; i < Math.min(got.length, row.path.length); i++) {
      const cl = Math.cos(row.path[i][0] * Math.PI / 180);
      r.pos_m = Math.max(r.pos_m, Math.hypot((got[i][1] - row.path[i][1]) * cl, got[i][0] - row.path[i][0]) * M);
    }
    out.trails.push(r);
  }
  for (const row of expected.lookups) out.lookups.push({q: row.q, ok: JSON.stringify(eng.lookup(row.q)) === JSON.stringify(row.want), got: eng.lookup(row.q)});
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
