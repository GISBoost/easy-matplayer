import viz_models


def test_car_mesh_from_quaternius_obj():
    m = viz_models.convert()
    lo, hi = m["bbox"]
    assert m["n"] > 1000 and m["n"] % 3 == 0 and len(m["positions"]) == 3 * m["n"] == len(m["normals"]) == 3 * len(m["roles"])
    assert abs((hi[0] - lo[0]) - viz_models.LENGTH_M) < 0.01 and abs(lo[0] + hi[0]) < 0.01  # długość 4,5 m, środek w 0
    assert lo[2] == 0.0 and hi[2] > 1.0  # koła na ziemi
    assert set(m["roles"]) <= set(range(5)) and 0 in m["roles"]
