import pytest
from PIL import Image, TiffImagePlugin

from viz_player import rasters


def _png(path, size=(40, 20), mode="RGB"):
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(path)
    return path


def test_world_file_shifts_to_pixel_corner(tmp_path):
    img = _png(tmp_path / "plan.png")
    (tmp_path / "plan.pgw").write_text("10\n0\n0\n-10\n500005\n599995\n")  # środek lewego-górnego piksela
    g = rasters.read_georef(img)
    assert g["source"] == "plik świata" and g["crs"] is None
    assert g["affine"] == (10.0, 0.0, 500000.0, 0.0, -10.0, 600000.0)
    assert rasters.guess_crs(g["affine"], (40, 20)) == 2180


def test_world_file_with_prj_gives_epsg(tmp_path):
    from pyproj import CRS
    img = _png(tmp_path / "plan.jpg")
    (tmp_path / "plan.jgw").write_text("1\n0\n0\n-1\n0.5\n0.5\n")
    (tmp_path / "plan.prj").write_text(CRS.from_epsg(2180).to_wkt())
    assert rasters.read_georef(img)["crs"] == 2180


def test_bad_world_file_is_a_sentence(tmp_path):
    img = _png(tmp_path / "a.png")
    (tmp_path / "a.wld").write_text("nie liczby\n")
    with pytest.raises(rasters.RasterError, match="a.wld"):
        rasters.read_georef(img)


def test_geotiff_tags(tmp_path):
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (10.0, 10.0, 0.0)
    ifd.tagtype[33550] = 12
    ifd[33922] = (0.0, 0.0, 0.0, 500000.0, 600000.0, 0.0)
    ifd.tagtype[33922] = 12
    ifd[34735] = (1, 1, 0, 2, 1024, 0, 1, 1, 3072, 0, 1, 2180)
    ifd.tagtype[34735] = 3
    path = tmp_path / "g.tif"
    Image.new("RGB", (40, 20), (1, 2, 3)).save(path, tiffinfo=ifd)
    g = rasters.read_georef(path)
    assert g["source"] == "GeoTIFF" and g["crs"] == 2180
    assert g["affine"] == (10.0, 0.0, 500000.0, 0.0, -10.0, 600000.0)
    c = rasters.corners_from_affine(g["affine"], (40, 20), g["crs"])
    assert c[0][0] < c[1][0] and c[0][1] > c[3][1]  # lewy-górny na zachód i północ od prawego-dolnego
    assert 14 < c[0][0] < 20 and 50 < c[0][1] < 54


def test_plain_image_has_no_georef(tmp_path):
    assert rasters.read_georef(_png(tmp_path / "szkic.png")) is None


def test_bbox_corners_degrees_and_projected():
    c = rasters.corners_from_bbox(19.3, 52.2, 19.4, 52.3)
    assert c == [[19.3, 52.3], [19.4, 52.3], [19.4, 52.2], [19.3, 52.2]]
    c2 = rasters.corners_from_bbox(500000, 480000, 510000, 490000, 2180)
    assert all(18 < p[0] < 21 and 51 < p[1] < 54 for p in c2)
    with pytest.raises(rasters.RasterError):
        rasters.corners_from_bbox(2, 0, 1, 1)


def test_manual_corners_keep_aspect_and_center():
    cx, cy = rasters.lonlat_to_merc(19.35, 52.23)
    c = rasters.manual_corners({"cx": cx, "cy": cy, "w": 1000.0}, (200, 100))
    m = [rasters.lonlat_to_merc(*p) for p in c]
    width = m[1][0] - m[0][0]
    height = m[0][1] - m[3][1]
    assert width == pytest.approx(600.0) and height == pytest.approx(300.0)
    assert (m[0][0] + m[2][0]) / 2 == pytest.approx(cx) and (m[0][1] + m[2][1]) / 2 == pytest.approx(cy)


def test_store_downscales_and_keeps_alpha(tmp_path):
    big = _png(tmp_path / "duzy.png", (300, 100), "RGBA")
    name, size, src = rasters.store_image(big, tmp_path / "out", "x1", max_px=100)
    assert name == "x1.png" and size == (100, 33) and src == (300, 100)
    mime, data = rasters.read_stored(tmp_path / "out", name)
    assert mime == "image/png" and data[:4] == b"\x89PNG"
    name2, size2, _ = rasters.store_image(_png(tmp_path / "foto.png"), tmp_path / "out", "x2")
    assert name2 == "x2.jpg" and size2 == (40, 20)


def test_missing_file_is_a_sentence(tmp_path):
    with pytest.raises(rasters.RasterError, match="Brak pliku"):
        rasters.store_image(tmp_path / "brak.png", tmp_path, "x")
