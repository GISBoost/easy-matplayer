import io
import urllib.parse

import pytest

from viz_player import ogc

WMS = """<?xml version="1.0"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms" xmlns:xlink="http://www.w3.org/1999/xlink">
 <Service><Title>Testowa usługa</Title></Service>
 <Capability>
  <Request><GetMap><Format>image/jpeg</Format><Format>image/png</Format>
   <DCPType><HTTP><Get><OnlineResource xlink:href="http://example.test/wms?"/></Get></HTTP></DCPType></GetMap></Request>
  <Layer><Title>Korzeń</Title><CRS>EPSG:2180</CRS>
   <Layer><Name>orto</Name><Title>Ortofotomapa</Title><CRS>EPSG:3857</CRS><CRS>EPSG:4326</CRS></Layer>
   <Layer><Name>dzialki</Name><Title>Działki</Title></Layer>
   <Layer><Name>geo</Name><Title>Tylko stopnie</Title><CRS>CRS:84</CRS><CRS>EPSG:4326</CRS></Layer>
  </Layer>
 </Capability>
</WMS_Capabilities>"""

WMTS = """<?xml version="1.0"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1" version="1.0.0">
 <ows:ServiceIdentification><ows:Title>WMTS test</ows:Title></ows:ServiceIdentification>
 <Contents>
  <Layer><ows:Title>Ortofoto</ows:Title><ows:Identifier>orto</ows:Identifier>
   <Style isDefault="true"><ows:Identifier>default</ows:Identifier></Style>
   <Format>image/jpeg</Format>
   <TileMatrixSetLink><TileMatrixSet>stary</TileMatrixSet></TileMatrixSetLink>
   <TileMatrixSetLink><TileMatrixSet>web</TileMatrixSet></TileMatrixSetLink>
   <ResourceURL format="image/jpeg" resourceType="tile" template="http://example.test/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.jpg"/>
  </Layer>
  <TileMatrixSet><ows:Identifier>stary</ows:Identifier><ows:SupportedCRS>urn:ogc:def:crs:EPSG::2180</ows:SupportedCRS>
   <TileMatrix><ows:Identifier>0</ows:Identifier><ScaleDenominator>1000000</ScaleDenominator><TileWidth>256</TileWidth><TileHeight>256</TileHeight></TileMatrix></TileMatrixSet>
  <TileMatrixSet><ows:Identifier>web</ows:Identifier><ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
   <TileMatrix><ows:Identifier>EPSG:3857:0</ows:Identifier><ScaleDenominator>559082264.0287178</ScaleDenominator><TileWidth>256</TileWidth><TileHeight>256</TileHeight></TileMatrix>
   <TileMatrix><ows:Identifier>EPSG:3857:1</ows:Identifier><ScaleDenominator>279541132.0143589</ScaleDenominator><TileWidth>256</TileWidth><TileHeight>256</TileHeight></TileMatrix>
   <TileMatrix><ows:Identifier>EPSG:3857:2</ows:Identifier><ScaleDenominator>139770566.00717944</ScaleDenominator><TileWidth>256</TileWidth><TileHeight>256</TileHeight></TileMatrix>
  </TileMatrixSet>
 </Contents>
</Capabilities>"""


@pytest.fixture
def served(monkeypatch):
    calls = []

    def fake(url, timeout=0):
        calls.append(url)
        if "WMTS" in url and "GetCapabilities" in url:
            return WMTS.encode(), "text/xml"
        if "GetCapabilities" in url:
            return WMS.encode(), "text/xml"
        return b"\x89PNG....", "image/png"

    monkeypatch.setattr(ogc, "_fetch", fake)
    return calls


def test_wms_layers_inherit_crs(served):
    cap = ogc.capabilities("http://example.test/wms")
    assert cap["kind"] == "wms" and cap["title"] == "Testowa usługa" and cap["getmap"] == "http://example.test/wms?"
    by = {l["name"]: l for l in cap["layers"]}
    assert by["orto"]["crs"] == ["EPSG:2180", "EPSG:3857", "EPSG:4326"]
    assert by["dzialki"]["crs"] == ["EPSG:2180"]


def test_wms_spec_prefers_mercator_then_degrees_then_projected(served):
    cap = ogc.capabilities("http://example.test/wms")
    assert ogc.make_spec(cap, "orto")["mode"] == "3857"
    geo = ogc.make_spec(cap, "geo")
    assert geo["mode"] == "4326" and geo["crs"] == "CRS:84"
    assert ogc.make_spec(cap, "dzialki")["mode"] == "proj"
    assert ogc.make_spec(cap, "orto")["format"] == "image/png"


def test_wms_3857_url_bbox(served):
    cap = ogc.capabilities("http://example.test/wms")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(ogc.wms_tile_url(ogc.make_spec(cap, "orto"), 0, 0, 0)).query)
    assert q["CRS"] == ["EPSG:3857"] and q["LAYERS"] == ["orto"] and q["WIDTH"] == ["256"]
    minx, miny, maxx, maxy = (float(v) for v in q["BBOX"][0].split(","))
    assert (minx, maxx) == (-ogc.ORIGIN, ogc.ORIGIN) and (miny, maxy) == (-ogc.ORIGIN, ogc.ORIGIN)
    q1 = urllib.parse.parse_qs(urllib.parse.urlsplit(ogc.wms_tile_url(ogc.make_spec(cap, "orto"), 1, 1, 0)).query)
    assert [float(v) for v in q1["BBOX"][0].split(",")][:2] == [0.0, 0.0]


def test_wms_4326_axis_order(served):
    cap = ogc.capabilities("http://example.test/wms")
    cap["layers"].append({"name": "stopnie", "title": "s", "path": "s", "crs": ["EPSG:4326"]})
    spec = ogc.make_spec(cap, "stopnie")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(ogc.wms_tile_url(spec, 1, 1, 0)).query)
    lat0, lon0, lat1, lon1 = (float(v) for v in q["BBOX"][0].split(","))
    assert lon0 == pytest.approx(0) and lon1 == pytest.approx(180) and lat0 == pytest.approx(0) and lat1 == pytest.approx(85.0511, abs=1e-3)


def test_wmts_matrices_and_urls(served):
    cap = ogc.capabilities("http://example.test/wmts")
    assert cap["kind"] == "wmts" and [l["name"] for l in cap["layers"]] == ["orto"]
    spec = ogc.make_spec(cap, "orto")
    assert spec["set"] == "web" and spec["matrices"] == {"0": "EPSG:3857:0", "1": "EPSG:3857:1", "2": "EPSG:3857:2"}
    assert ogc.wmts_tile_url(spec, 2, 3, 1) == "http://example.test/web/EPSG:3857:2/3/1.jpg"
    spec.pop("rest")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(ogc.wmts_tile_url(spec, 1, 1, 0)).query)
    assert q["TILEMATRIX"] == ["EPSG:3857:1"] and q["TILECOL"] == ["1"] and q["TILEROW"] == ["0"]


def test_wmts_without_mercator_is_an_error(served):
    cap = ogc.capabilities("http://example.test/wmts")
    cap["layers"][0]["sets"] = ["stary"]
    with pytest.raises(ogc.OgcError, match="EPSG:3857"):
        ogc.make_spec(cap, "orto")


def test_tile_rejects_non_image(monkeypatch):
    monkeypatch.setattr(ogc, "_fetch", lambda url, timeout=0: (b"<ServiceException>brak warstwy</ServiceException>", "text/xml"))
    spec = {"kind": "wms", "getmap": "http://example.test/wms", "version": "1.3.0", "layer": "x", "format": "image/png", "crs": "EPSG:3857", "mode": "3857"}
    with pytest.raises(ogc.OgcError, match="brak warstwy"):
        ogc.tile(spec, 3, 4, 2)


def test_bad_scheme_and_empty_url():
    with pytest.raises(ogc.OgcError):
        ogc.capabilities("  ")
    with pytest.raises(ogc.OgcError, match="http"):
        ogc._fetch("file:///c:/windows/win.ini")


def test_projected_tile_is_resampled(monkeypatch):
    """Obraz w EPSG:2180 z gradientem po x: kafelek Kutna ma kolor rosnący ku wschodowi."""
    import numpy as np
    from PIL import Image

    def fake(url, timeout=0):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        seen.append([float(v) for v in q["BBOX"][0].split(",")])
        w = int(q["WIDTH"][0])
        img = np.zeros((w, w, 4), np.uint8)
        img[..., 0] = np.linspace(0, 255, w).astype(np.uint8)[None, :]
        img[..., 3] = 255
        buf = io.BytesIO()
        Image.fromarray(img, "RGBA").save(buf, "PNG")
        return buf.getvalue(), "image/png"

    seen = []
    monkeypatch.setattr(ogc, "_fetch", fake)
    spec = {"kind": "wms", "getmap": "http://example.test/wms", "version": "1.3.0", "layer": "x", "format": "image/png", "crs": "EPSG:2180", "mode": "proj"}
    mime, body = ogc.tile(spec, 15, 18077, 10450)  # okolice Gdańska: w CS92 północ (~730 tys.) jest większa od wschodu (~450 tys.)
    out = np.asarray(Image.open(io.BytesIO(body)))
    assert mime == "image/png" and out.shape == (256, 256, 4) and out[..., 3].min() == 255
    assert out[:, -1, 0].mean() > out[:, 0, 0].mean() + 100
    assert seen[0][0] > seen[0][1] + 1e5  # WMS 1.3.0 + EPSG:2180: najpierw północ, potem wschód


def test_xyz_template_is_recognised_and_formatted(monkeypatch):
    cap = ogc.capabilities("https://t.example/{z}/{x}/{y}.png")
    spec = ogc.make_spec(cap, "xyz")
    assert cap["kind"] == "xyz" and spec == {"kind": "xyz", "template": "https://t.example/{z}/{x}/{y}.png"}
    assert ogc.xyz_tile_url("https://{s}.t/{z}/{x}/{-y}.png", 3, 5, 2) == "https://a.t/3/5/5.png"
    seen = []
    monkeypatch.setattr(ogc, "_fetch", lambda url, timeout=0: (seen.append(url), (b"x", "image/png"))[1])
    assert ogc.tile(spec, 4, 8, 6)[0] == "image/png" and seen == ["https://t.example/4/8/6.png"]


def test_epsg_code_forms():
    assert ogc.epsg("urn:ogc:def:crs:EPSG::3857") == "3857"
    assert ogc.epsg("urn:ogc:def:crs:EPSG:6.18.3:3857") == "3857"  # basemap.at: wersja bazy EPSG w URN
    assert ogc.epsg("EPSG:2180") == "2180" and ogc.epsg("epsg:900913") == "900913"
    assert ogc.epsg("CRS:84") is None
