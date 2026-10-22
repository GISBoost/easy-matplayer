"""Generuje viz_player/icon.ico: tymczasowa ikona easy-matanimation (ciemny kwadrat, niebieska trasa i żółty znacznik auta).
Uruchomienie: uv run --group viz python scripts/viz_make_icon.py. Plik .ico jest w repo; skrypt służy do zmian wyglądu."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).resolve().parents[1] / "viz_player" / "icon.ico"


def draw():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=210, fill=(18, 20, 24, 255))
    d.rounded_rectangle([40, 40, SIZE - 41, SIZE - 41], radius=180, outline=(42, 49, 64, 255), width=10)
    route = [(170, 770), (360, 640), (480, 700), (640, 430), (780, 300), (860, 250)]
    d.line(route, fill=(79, 156, 249, 255), width=86, joint="curve")
    for x, y in (route[0], route[-1]):
        d.ellipse([x - 43, y - 43, x + 43, y + 43], fill=(79, 156, 249, 255))
    x, y = route[3]
    d.ellipse([x - 92, y - 92, x + 92, y + 92], fill=(250, 204, 21, 255), outline=(18, 20, 24, 255), width=22)
    return img


if __name__ == "__main__":
    big = draw()
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    big.resize((256, 256), Image.LANCZOS).save(OUT, format="ICO", sizes=sizes)
    print(OUT, OUT.stat().st_size, "B")
