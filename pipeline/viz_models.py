"""Model samochodu dla okna odtwarzacza: Quaternius BasicCar.obj -> viz_player/vendor/quaternius/car_mesh.json.

Osie wyjściowe: +x przód, +y lewo, +z góra, w metrach; długość 4,5 m, środek po długości w 0, koła na z = 0.
Kolor z tekstury-palety 32×32 (po UV środka ściany) zamieniony na rolę: 0 nadwozie (malowane kolorem pojazdu w oknie),
1 szyby, 2 koła i podwozie, 3 światła, 4 detale. Wierzchołki nie są współdzielone (płaskie cieniowanie z vn z OBJ).

  uv run python pipeline/viz_models.py
"""
import json
from pathlib import Path

import numpy as np
from matplotlib.image import imread

DIR = Path(__file__).resolve().parents[1] / "viz_player" / "vendor" / "quaternius"
LENGTH_M = 4.5
FRONT_SIGN = 1  # przód modelu jest w +z OBJ (sprawdzone w oknie: przy −1 auta jechały tyłem); po zmianie uruchomić ten skrypt
ROLES = {(94, 160, 242): 0, (90, 235, 235): 1, (117, 112, 143): 2, (243, 230, 65): 3, (255, 255, 255): 4}


def convert(obj=DIR / "BasicCar.obj", tex=DIR / "CarTexture.png"):
    img = (imread(tex)[..., :3] * 255).round().astype(int)
    v, vt, vn, faces = [], [], [], []
    for line in Path(obj).read_text().splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "vn":
            vn.append([float(x) for x in p[1:4]])
        elif p[0] == "f":
            faces.append([tuple(int(i) if i else 0 for i in t.split("/")) for t in p[1:]])
    v, vt, vn = np.array(v), np.array(vt), np.array(vn)
    s = FRONT_SIGN
    M = np.array([[0, 0, s], [s, 0, 0], [0, 1, 0]], float)  # (x, y, z) OBJ -> (przód, lewo, góra), det = +1
    k = LENGTH_M / (v[:, 2].max() - v[:, 2].min())
    mid_z = (v[:, 2].max() + v[:, 2].min()) / 2
    low = v[:, 1].min()

    def place(p):
        return M @ (np.array([p[0], p[1] - low, p[2] - mid_z]) * k)

    pos, nor, role = [], [], []
    for f in faces:
        uv = vt[[t[1] - 1 for t in f]].mean(0)
        px = tuple(img[int(np.clip((1 - uv[1]) * img.shape[0], 0, img.shape[0] - 1)), int(np.clip(uv[0] * img.shape[1], 0, img.shape[1] - 1))])
        r = min(ROLES.items(), key=lambda kv: sum((a - b) ** 2 for a, b in zip(kv[0], px)))[1]
        for i in range(1, len(f) - 1):
            for t in (f[0], f[i], f[i + 1]):
                pos.append(place(v[t[0] - 1]))
                nor.append(M @ vn[t[2] - 1] if t[2] else [0, 0, 1])
                role.append(r)
    pos, nor = np.array(pos), np.array(nor)
    return {
        "length_m": LENGTH_M, "n": len(pos), "bbox": [pos.min(0).round(3).tolist(), pos.max(0).round(3).tolist()],
        "positions": pos.round(3).ravel().tolist(), "normals": nor.round(2).ravel().tolist(), "roles": role,
        "roles_legend": ["nadwozie", "szyby", "koła i podwozie", "światła", "detale"],
        "source": "Quaternius LowPoly Car pack, CC0 (opengameart.org/content/lowpoly-cars)",
    }


def main():
    out = convert()
    path = DIR / "car_mesh.json"
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{path.name}: {out['n']} wierzchołków, bbox {out['bbox']}, {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
