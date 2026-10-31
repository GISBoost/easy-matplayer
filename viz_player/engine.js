// Silnik klatki po stronie klienta (D26, krok 4). Bez DOM i bez mapy: dane z viz_export.py
// (manifest.json, persons.json, tracks.bin, chunk_NNN.bin) i funkcje czasu. Python nie liczy klatek.
// Działa w przeglądarce (window.Engine) i w node (require), dzięki temu ma test bez okna.
(function (root) {
"use strict";

const SPEED_CAP = 30;       // m/s, jak w pipeline/viz_engine.py
const DT_FLOOR = 1e-3;
const M_PER_DEG = 111194.93; // sfera R = 6371008,8 m; tylko do prędkości zapasowej i długości śladu
const KEEP = 6;
const MAX_FLASH = 5000;     // najnowsze błyski aktywności w jednej klatce; reszta jest pomijana (Engine.flashes zwraca truncated)             // ile porcji zostaje w pamięci po obu stronach bieżącej
const TYPES = {"<i4": Int32Array, "<f4": Float32Array, "<f8": Float64Array, "<u2": Uint16Array, "u1": Uint8Array};

function readColumns(buf, columns, counts, align) {
  const out = {};
  let pos = 0;
  columns.forEach((col, i) => {
    const Ctor = TYPES[col[1]];
    out[col[0]] = new Ctor(buf, pos, counts[i]);
    const size = counts[i] * Ctor.BYTES_PER_ELEMENT;
    pos += size + ((align - (size % align)) % align);
  });
  if (pos !== buf.byteLength) throw new Error("zły rozmiar pliku: " + buf.byteLength + " B, oczekiwane " + pos + " B");
  return out;
}

function counts(spec, chunk) {
  const v = {"n": chunk.n_tracks, "n+1": chunk.n_tracks + 1, "k": chunk.n_knots, "a": chunk.n_acts || 0};
  return spec.map((s) => v[s]);
}

class Engine {
  // curves: {off: Int32Array, lon: Float64Array, lat: Float64Array} albo null; linkLL: Float64Array 4 na link.
  constructor(manifest, persons, tracks, curves, linkLL, get) {
    this.m = manifest;
    this.persons = persons;
    this.tr = tracks;
    this.curves = curves && curves.off && curves.off.length ? curves : null;
    this.linkLL = linkLL || null;
    this.get = get;
    this.lon0 = manifest.origin_lonlat[0];
    this.lat0 = manifest.origin_lonlat[1];
    this.cosLat = Math.cos(this.lat0 * Math.PI / 180);
    this.classKeys = manifest.classes.map((c) => c.key);
    this.classHeavy = Uint8Array.from(manifest.classes.map((c) => (c.heavy ? 1 : 0)));
    this.actTypes = manifest.act_types || [];
    this.actStarts = manifest.act_start_counts || [];     // ile startów ma każdy typ (lista typów w oknie pokazuje te, które błyskają)
    this.hasActs = manifest.chunk_columns.some((c) => c[0] === "act_t");
    this.back = 1;          // ile porcji przed bieżącą trzymać w pamięci (błyski i statystyki linków patrzą wstecz, okno i życie błysku < porcja)
    this.fl = null;
    this.chunks = new Map();
    this.pending = new Map();
    this.first = manifest.chunks[0].t0;
    let maxN = 1;
    manifest.chunks.forEach((c) => { if (c.n_tracks > maxN) maxN = c.n_tracks; });
    this.out = {
      lon: new Float64Array(maxN), lat: new Float64Array(maxN), speed: new Float32Array(maxN),
      heading: new Float32Array(maxN), cls: new Uint8Array(maxN), track: new Int32Array(maxN),
      link: new Int32Array(maxN), n: 0,
    };
    this.cum = this.curves ? this.curveLengths() : null;
    this._byId = null;
    this._byPerson = null;
  }

  static async load(base, get, curves, linkLL, manifestName) {
    const manifest = await get(base + (manifestName || "manifest.json"), "json");
    if (manifest.format !== 1 && manifest.format !== 2) throw new Error("nieznany format eksportu " + manifest.format);
    // ?v=klucz: serwer pywebview nie ustawia Cache-Control, a pliki danych zmieniają się bez zmiany adresu
    const q = "?v=" + manifest.source_key.slice(0, 12);
    const persons = await get(base + manifest.persons + q, "json");
    const buf = await get(base + manifest.tracks.file + q, "buf");
    const tracks = readColumns(buf, manifest.tracks.columns, manifest.tracks.columns.map(() => manifest.n_tracks), manifest.align);
    return new Engine(manifest, persons, tracks, curves, linkLL, (name, kind) => get(base + name + q, kind));
  }

  // ---- porcje ----
  chunkIndex(t) {
    const i = Math.floor((t - this.first) / this.m.chunk_sec);
    return Math.min(Math.max(i, 0), this.m.chunks.length - 1);
  }

  need(i) {
    if (i < 0 || i >= this.m.chunks.length) return Promise.resolve(null);
    if (this.chunks.has(i)) return Promise.resolve(this.chunks.get(i));
    if (!this.pending.has(i)) {
      const ch = this.m.chunks[i];
      const p = this.get(ch.file, "buf").then((buf) => {
        const cols = readColumns(buf, this.m.chunk_columns, counts(this.m.chunk_counts, ch), this.m.align);
        this.chunks.set(i, cols);
        this.pending.delete(i);
        return cols;
      });
      this.pending.set(i, p);
    }
    return this.pending.get(i);
  }

  // Zamawia porcje wokół t (i opcjonalnie od porcji `since`, do śladu) i zwalnia dalekie.
  want(t, since) {
    const ci = this.chunkIndex(t);
    const lo = Math.max(0, since == null ? ci - this.back : Math.min(ci - this.back, this.chunkIndex(since)));
    const jobs = [];
    for (let i = lo; i <= ci + 1; i++) jobs.push(this.need(i));
    for (const i of [...this.chunks.keys()]) if (i < lo - KEEP || i > ci + KEEP) this.chunks.delete(i);
    return Promise.all(jobs);
  }

  ready(t) { return this.chunks.has(this.chunkIndex(t)); }

  // ---- klatka ----
  // on: Uint8Array(len klas) z 1 dla włączonych klas. Zwraca this.out (bufory do następnej klatki) albo null.
  frame(t, on) {
    const ch = this.chunks.get(this.chunkIndex(t));
    if (!ch) return null;
    const o = this.out, tr = this.tr;
    const tf = Math.fround(t), cosLat = this.cosLat;
    const kt = ch.knot_t, kx = ch.knot_dlon, ky = ch.knot_dlat, kl = ch.knot_len, ki = ch.knot_link, off = ch.knot_off;
    let n = 0;
    for (let k = 0; k < ch.track.length; k++) {
      const id = ch.track[k];
      if (t < tr.t0[id] || t > tr.t1[id] || !on[tr.cls[id]]) continue;
      const a = off[k], b = off[k + 1];
      let dlon, dlat, link, heading = 0, speed = 0;
      if (b - a === 1) {
        dlon = kx[a]; dlat = ky[a]; link = ki[a];
      } else {
        let lo = a, hi = b;
        while (lo < hi) { const mid = (lo + hi) >> 1; if (kt[mid] <= tf) lo = mid + 1; else hi = mid; }
        const j = Math.min(Math.max(lo - 1, a), b - 2);
        const t0 = kt[j], t1 = kt[j + 1], dt = t1 - t0;
        if (dt <= 0) {
          dlon = kx[j + 1]; dlat = ky[j + 1]; link = ki[j + 1];
        } else {
          const u = (t - t0) / dt;
          dlon = kx[j] + u * (kx[j + 1] - kx[j]);
          dlat = ky[j] + u * (ky[j + 1] - ky[j]);
          link = t >= t1 ? ki[j + 1] : ki[j];
        }
        for (let q = j; q >= a; q--) {
          const dx = (kx[q + 1] - kx[q]) * cosLat, dy = ky[q + 1] - ky[q];
          if (dx !== 0 || dy !== 0) { heading = Math.atan2(dy, dx); break; }
        }
        const len = kl[j + 1];
        const dist = len > 0 ? len : Math.hypot((kx[j + 1] - kx[j]) * cosLat, ky[j + 1] - ky[j]) * M_PER_DEG;
        speed = Math.min(dist / Math.max(dt, DT_FLOOR), SPEED_CAP);
      }
      let lon = this.lon0 + dlon, lat = this.lat0 + dlat;
      if (this.curves && link >= 0) {
        const ca = this.curves.off[link], cb = this.curves.off[link + 1];
        if (cb - ca >= 3) {
          const p = this.pointAt(ca, cb, this.chordU(link, lon, lat));
          lon = p[0]; lat = p[1]; heading = p[2];
        }
      }
      o.lon[n] = lon; o.lat[n] = lat; o.speed[n] = speed; o.heading[n] = heading;
      o.cls[n] = tr.cls[id]; o.track[n] = id; o.link[n] = link;
      n++;
    }
    o.n = n;
    return o;
  }

  // ---- błyski aktywności ----
  // Starty aktywności z (t - life, t] z załadowanych porcji, najnowsze najpierw (do MAX_FLASH).
  // typeOn: Uint8Array(len act_types) z 1 dla widocznych typów. Zwraca bufory do następnej klatki:
  // {n, truncated, lon, lat, age (s symulacji od startu), type}.
  flashes(t, life, typeOn) {
    if (!this.fl) {
      this.fl = {n: 0, truncated: false, lon: new Float64Array(MAX_FLASH), lat: new Float64Array(MAX_FLASH),
                 age: new Float32Array(MAX_FLASH), type: new Uint16Array(MAX_FLASH)};
    }
    const o = this.fl;
    o.n = 0;
    o.truncated = false;
    if (!this.hasActs) return o;
    const hiT = Math.fround(t), loT = Math.fround(t - life);
    const ci = this.chunkIndex(t);
    for (let c = ci; c >= Math.max(0, ci - 1) && !o.truncated; c--) {
      const ch = this.chunks.get(c);
      if (!ch || !ch.act_t.length) continue;
      const at = ch.act_t;
      let a = 0, b = at.length;                       // pierwszy indeks z act_t > t
      while (a < b) { const mid = (a + b) >> 1; if (at[mid] <= hiT) a = mid + 1; else b = mid; }
      for (let i = a - 1; i >= 0 && at[i] > loT; i--) {
        if (!ch.act_kind[i] || !typeOn[ch.act_type[i]]) continue;
        if (o.n >= MAX_FLASH) { o.truncated = true; break; }
        o.lon[o.n] = this.lon0 + ch.act_dlon[i];
        o.lat[o.n] = this.lat0 + ch.act_dlat[i];
        o.age[o.n] = t - at[i];
        o.type[o.n] = ch.act_type[i];
        o.n++;
      }
    }
    return o;
  }

  // ---- obciążenie linków ----
  // Statystyki z węzłów tras w oknie (t - W, t]: wyjazd z linku to węzeł z knot_len > 0 po węźle wjazdu (knot_len = 0) tego samego linku; liczy się czasem wyjazdu
  // i tylko w porcji, w której ten czas leży w [t0, t1) (porcje powtarzają węzły graniczne). out.n: wszystkie wyjazdy (natężenie).
  // Pełny przejazd (poprzedni węzeł leży w początku linku, więc nie jest to wjazd w środek linku) daje out.nf, out.len, out.tt (prędkość).
  linkStats(t, W, on) {
    const nL = this.linkLL ? this.linkLL.length / 4 : 0;
    if (!this.ls || this.ls.n.length !== nL) {
      this.ls = {n: new Uint32Array(nL), nf: new Uint32Array(nL), len: new Float64Array(nL), tt: new Float64Array(nL)};
    }
    const o = this.ls, tr = this.tr, ll = this.linkLL;
    o.n.fill(0); o.nf.fill(0); o.len.fill(0); o.tt.fill(0);
    const hi = Math.fround(t), lo = Math.fround(t - W), ci = this.chunkIndex(t);
    const tol = 1.5 / M_PER_DEG, tolX = tol / this.cosLat;
    for (let c = ci; c >= Math.max(0, ci - 1); c--) {
      const ch = this.chunks.get(c);
      if (!ch) continue;
      const c0 = this.m.chunks[c].t0, c1 = this.m.chunks[c].t1;
      const kt = ch.knot_t, kx = ch.knot_dlon, ky = ch.knot_dlat, kl = ch.knot_len, ki = ch.knot_link, off = ch.knot_off;
      for (let j = 0; j < ch.track.length; j++) {
        const id = ch.track[j];
        if (!on[tr.cls[id]] || tr.t1[id] < lo || tr.t0[id] > hi) continue;
        for (let q = off[j] + 1; q < off[j + 1]; q++) {
          const te = kt[q];
          if (te <= lo || te > hi || te < c0 || te >= c1 || kl[q] <= 0 || kl[q - 1] !== 0) continue;   // wyjazd po wjeździe (nie po innym wyjeździe)
          const l = ki[q];
          if (l < 0 || l !== ki[q - 1]) continue;
          o.n[l]++;
          if (Math.abs(this.lon0 + kx[q - 1] - ll[4 * l]) < tolX && Math.abs(this.lat0 + ky[q - 1] - ll[4 * l + 1]) < tol) {
            o.nf[l]++;
            o.len[l] += kl[q];
            o.tt[l] += Math.max(te - kt[q - 1], 0.1);
          }
        }
      }
    }
    return o;
  }

  // Wskaźnik na link do koloru. attr: Float32Array po 4 na link [długość, swobodna m/s, przepustowość poj/h, pasy].
  // "speed": średnia przestrzenna prędkość / swobodna; "flow": natężenie / (przepustowość × flowFactor). NaN: brak ruchu w oknie
  // (albo brak przepustowości), nie „swobodnie”. Zwraca out (Float32Array na link).
  loadValues(ls, attr, mode, W, flowFactor, out) {
    for (let l = 0; l < out.length; l++) {
      let v = NaN;
      if (mode === "speed") {
        if (ls.nf[l] > 0 && attr[4 * l + 1] > 0) v = ls.len[l] / ls.tt[l] / attr[4 * l + 1];
      } else {
        const cap = attr[4 * l + 2] * flowFactor;
        if (ls.n[l] > 0 && cap > 0) v = (ls.n[l] * 3600 / W) / cap;
      }
      out[l] = v;
    }
    return out;
  }

  // ---- łamane OSM (tylko rysunek): pozycja z cięciwy przenoszona na łamaną tym samym ułamkiem ----
  curveLengths() {
    const c = this.curves, cum = new Float64Array(c.lon.length);
    for (let l = 0; l + 1 < c.off.length; l++) {
      for (let i = c.off[l] + 1; i < c.off[l + 1]; i++) {
        cum[i] = cum[i - 1] + Math.hypot((c.lon[i] - c.lon[i - 1]) * this.cosLat, c.lat[i] - c.lat[i - 1]);
      }
    }
    return cum;
  }

  chordU(link, lon, lat) {
    const ll = this.linkLL, k = 4 * link, cl = this.cosLat;
    const bx = (ll[k + 2] - ll[k]) * cl, by = ll[k + 3] - ll[k + 1];
    const den = bx * bx + by * by;
    if (den < 1e-24) return 0;
    const u = (((lon - ll[k]) * cl) * bx + (lat - ll[k + 1]) * by) / den;
    return Math.min(1, Math.max(0, u));
  }

  // [lon, lat, kierunek] na ułamku u długości łamanej o punktach ca..cb-1
  pointAt(ca, cb, u) {
    const c = this.curves, cum = this.cum, cl = this.cosLat;
    const total = cum[cb - 1];
    if (total <= 1e-15) return [c.lon[ca], c.lat[ca], 0];
    const target = Math.min(1, Math.max(0, u)) * total;
    const last = cb - 2;
    let lo = ca, hi = last;   // pierwszy odcinek i z cum[i+1] >= target
    while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid + 1] >= target - 1e-15) hi = mid; else lo = mid + 1; }
    const i = lo, seg = cum[i + 1] - cum[i];
    const f = seg <= 1e-18 ? 0 : Math.min(1, Math.max(0, (target - cum[i]) / seg));
    const lon = c.lon[i] + f * (c.lon[i + 1] - c.lon[i]);
    const lat = c.lat[i] + f * (c.lat[i + 1] - c.lat[i]);
    const j = f >= 1 - 1e-9 && i < last ? i + 1 : i;
    return [lon, lat, Math.atan2(c.lat[j + 1] - c.lat[j], (c.lon[j + 1] - c.lon[j]) * cl)];
  }

  // punkty łamanej między ułamkami u0 i u1 (kolejność zgodna z kierunkiem jazdy)
  span(ca, cb, u0, u1) {
    const c = this.curves, cum = this.cum;
    const rev = u1 < u0, a = rev ? u1 : u0, b = rev ? u0 : u1;
    const first = this.pointAt(ca, cb, a);
    const pts = [[first[0], first[1]]];
    const total = cum[cb - 1];
    if (total > 1e-15 && b > a) {
      const eps = 1e-4 / (total * M_PER_DEG);
      for (let i = ca + 1; i < cb - 1; i++) {
        const f = cum[i] / total;
        if (a + eps < f && f < b - eps) pts.push([c.lon[i], c.lat[i]]);
      }
      const e = this.pointAt(ca, cb, b), p = pts[pts.length - 1];
      if (Math.hypot((e[0] - p[0]) * this.cosLat, e[1] - p[1]) * M_PER_DEG > 1e-3) pts.push([e[0], e[1]]);
    }
    if (rev) pts.reverse();
    return pts;
  }

  // ---- osoby i ślad ----
  personIndex(id) {
    if (!this._byId) this._byId = new Map(this.persons.map((p, i) => [p, i]));
    const i = this._byId.get(String(id));
    return i === undefined ? -1 : i;
  }

  personTracks(pi) {
    if (!this._byPerson) {
      const pers = this.tr.person_i, n = this.persons.length, off = new Int32Array(n + 1);
      for (let i = 0; i < pers.length; i++) off[pers[i] + 1]++;
      for (let i = 0; i < n; i++) off[i + 1] += off[i];
      const fill = off.slice(0, n), order = new Int32Array(pers.length);
      for (let i = 0; i < pers.length; i++) order[fill[pers[i]]++] = i;
      this._byPerson = {off, order};
    }
    return Array.from(this._byPerson.order.subarray(this._byPerson.off[pi], this._byPerson.off[pi + 1]));
  }

  activeTrack(pi, t) {
    if (pi < 0) return null;
    for (const id of this.personTracks(pi)) if (this.tr.t0[id] <= t && t <= this.tr.t1[id]) return id;
    return null;
  }

  personId(track) { return this.persons[this.tr.person_i[track]]; }

  // Dokładne id albo jedyny prefiks => {followed}; inaczej {hits: [{id}]} (najwyżej 20), jak Player.lookup.
  lookup(query) {
    const q = String(query).trim();
    if (!q) return {hits: []};
    const ids = this.persons;
    let lo = 0, hi = ids.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (ids[mid] < q) lo = mid + 1; else hi = mid; }
    const hits = [];
    for (let j = lo; j < ids.length && ids[j].startsWith(q) && hits.length < 20; j++) hits.push(ids[j]);
    if (hits.length && hits[0] === q) return {followed: q};
    if (hits.length === 1) return {followed: hits[0]};
    return {hits: hits.map((id) => ({id}))};
  }

  // Ślad przejazdu `track` do czasu t, [[lat, lon], ...]. Używa załadowanych porcji.
  trail(track, t) {
    const T = [], X = [], Y = [], L = [];
    let lastG = -1;
    const lo = this.chunkIndex(this.tr.t0[track]), hi = this.chunkIndex(t);
    for (let ci = lo; ci <= hi; ci++) {
      const ch = this.chunks.get(ci);
      if (!ch) continue;
      let a = 0, b = ch.track.length;
      while (a < b) { const mid = (a + b) >> 1; if (ch.track[mid] < track) a = mid + 1; else b = mid; }
      if (a >= ch.track.length || ch.track[a] !== track) continue;
      const k0 = ch.knot_off[a], k1 = ch.knot_off[a + 1], g0 = ch.g0[a];
      for (let q = k0; q < k1; q++) {
        const g = g0 + (q - k0);
        if (g <= lastG) continue;
        lastG = g;
        T.push(ch.knot_t[q]); X.push(this.lon0 + ch.knot_dlon[q]); Y.push(this.lat0 + ch.knot_dlat[q]); L.push(ch.knot_link[q]);
      }
    }
    if (!T.length) return [];
    const tf = Math.fround(t);
    let n = 0;
    while (n < T.length && T[n] <= tf) n++;
    n = Math.min(Math.max(n, 1), T.length);
    const xs = X.slice(0, n), ys = Y.slice(0, n), ls = L.slice(0, n);
    const cur = this.positionOf(track, t);
    if (cur) {
      const d = Math.hypot((xs[n - 1] - cur[0]) * this.cosLat, ys[n - 1] - cur[1]) * M_PER_DEG;
      if (d > 1e-3) { xs.push(cur[0]); ys.push(cur[1]); ls.push(cur[2]); }
    }
    const out = [];
    for (let i = 0; i < xs.length; i++) {
      const li = ls[i];
      const bent = this.curves && li >= 0 && this.curves.off[li + 1] - this.curves.off[li] >= 3;
      if (!bent) { out.push([xs[i], ys[i]]); continue; }
      const ca = this.curves.off[li], cb = this.curves.off[li + 1];
      if (i > 0 && ls[i - 1] === li) {
        let pts = this.span(ca, cb, this.chordU(li, xs[i - 1], ys[i - 1]), this.chordU(li, xs[i], ys[i]));
        if (out.length && pts.length) pts = pts.slice(1);
        pts.forEach((p) => out.push(p));
      } else {
        const p = this.pointAt(ca, cb, this.chordU(li, xs[i], ys[i]));
        out.push([p[0], p[1]]);
      }
    }
    return out.map((p) => [p[1], p[0]]);
  }

  // Surowa pozycja przejazdu na cięciwie [lon, lat, link] (bez łamanej) albo null.
  positionOf(track, t) {
    const ch = this.chunks.get(this.chunkIndex(t));
    if (!ch) return null;
    let a = 0, b = ch.track.length;
    while (a < b) { const mid = (a + b) >> 1; if (ch.track[mid] < track) a = mid + 1; else b = mid; }
    if (a >= ch.track.length || ch.track[a] !== track) return null;
    const k0 = ch.knot_off[a], k1 = ch.knot_off[a + 1], tf = Math.fround(t);
    if (k1 - k0 === 1) return [this.lon0 + ch.knot_dlon[k0], this.lat0 + ch.knot_dlat[k0], ch.knot_link[k0]];
    let lo = k0, hi = k1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (ch.knot_t[mid] <= tf) lo = mid + 1; else hi = mid; }
    const j = Math.min(Math.max(lo - 1, k0), k1 - 2);
    const t0 = ch.knot_t[j], t1 = ch.knot_t[j + 1], dt = t1 - t0;
    if (dt <= 0) return [this.lon0 + ch.knot_dlon[j + 1], this.lat0 + ch.knot_dlat[j + 1], ch.knot_link[j + 1]];
    const u = (t - t0) / dt;
    return [
      this.lon0 + ch.knot_dlon[j] + u * (ch.knot_dlon[j + 1] - ch.knot_dlon[j]),
      this.lat0 + ch.knot_dlat[j] + u * (ch.knot_dlat[j + 1] - ch.knot_dlat[j]),
      t >= t1 ? ch.knot_link[j + 1] : ch.knot_link[j],
    ];
  }

  // Auta na linku w klatce: {n, speed_mean} (średnia prędkość, m/s), jak viz_engine.link_now.
  linkNow(fr, link) {
    let n = 0, sum = 0;
    for (let i = 0; i < fr.n; i++) if (fr.link[i] === link) { n++; sum += fr.speed[i]; }
    return {n, speed_mean: n ? sum / n : null};
  }
}

root.Engine = Engine;
root.readColumns = readColumns;
if (typeof module !== "undefined" && module.exports) module.exports = {Engine, readColumns};
})(typeof window !== "undefined" ? window : globalThis);
