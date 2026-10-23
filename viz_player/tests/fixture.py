"""Wspólna fixtura testów wizualizera: mały run MATSim (sieć 6 linków po 100 m, eventy, config).

Współrzędne świata zaczynają się w BASE; origin indeksu wychodzi z bbox sieci,
więc testy przeliczają je przez local() albo czytają meta["origin"].
"""
import tempfile
from pathlib import Path

import viz_index

BASE = (524805.0, 485023.0)
# środek bbox (BASE + 0..600 m) zaokrąglony do 1000 m
ORIGIN = (525000.0, 485000.0)
N_LINKS = 6


def local(x, y=0.0):
    """Punkt mini-sieci (m od BASE) na współrzędne lokalne indeksu."""
    return BASE[0] + x - ORIGIN[0], BASE[1] + y - ORIGIN[1]


def world(x, y=0.0):
    return BASE[0] + x, BASE[1] + y


def network_xml():
    nodes = "".join(f'<node id="n{i}" x="{BASE[0] + 100 * i}" y="{BASE[1]}"/>' for i in range(N_LINKS + 1))
    links = "".join(
        f'<link id="l{i}" from="n{i}" to="n{i + 1}" length="100" freespeed="10" '
        f'permlanes="1" capacity="600" oneway="1" modes="car">'
        f'<attributes><attribute name="type" class="java.lang.String">residential</attribute></attributes>'
        f'</link>'
        for i in range(N_LINKS)
    )
    return f'<?xml version="1.0"?><network>{nodes}{links}</network>'


def enter(vid, t, link="l0", rel="0", person=None):
    person = f' person="{person}"' if person else ""
    return (f'<event time="{t}" type="vehicle enters traffic"{person} vehicle="{vid}" '
            f'link="{link}" relativePosition="{rel}"/>')


def leave(vid, t, link="l0", person=None):
    person = f' person="{person}"' if person else ""
    return f'<event time="{t}" type="vehicle leaves traffic"{person} vehicle="{vid}" link="{link}"/>'


def act(kind, person, t, link, x, typ):
    wx, wy = world(x)
    return f'<event time="{t}" type="{kind}" person="{person}" link="{link}" x="{wx}" y="{wy}" actType="{typ}"/>'


def leg(vid, t0, t1, person=None):
    """Jedno-linkowy przejazd l0, wjazd na początku linku."""
    return [enter(vid, t0, person=person), leave(vid, t1, person=person)]


def trip(vid, t_enter, person=None, acts=True):
    """Sześć linków po 10 s. Z acts: home (actend) przed i work (actstart) po, car interaction pomijane."""
    person = person or vid
    rows = []
    if acts:
        rows += [act("actend", person, t_enter - 1, "l0", 0, "home"),
                 act("actstart", person, t_enter, "l0", 0, "car interaction")]
    rows.append(enter(vid, t_enter, person=person))
    t = t_enter
    for i in range(N_LINKS):
        t += 10
        rows.append(f'<event time="{t}" type="left link" vehicle="{vid}" link="l{i}"/>')
        if i < N_LINKS - 1:
            rows.append(f'<event time="{t}" type="entered link" vehicle="{vid}" link="l{i + 1}"/>')
    rows.append(leave(vid, t, link=f"l{N_LINKS - 1}", person=person))
    if acts:
        rows.append(act("actstart", person, t + 1, f"l{N_LINKS - 1}", 600, "work"))
    return rows


def write_run(run_dir, events, sample="0.25", network=None):
    """Zapisuje sieć, config i eventy (posortowane po czasie, jak w MATSim). Zwraca run_dir."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    viz_index.write_zst(run_dir / viz_index.NETWORK_NAME, network or network_xml())
    (run_dir / viz_index.CONFIG_NAME).write_text(
        f'<config><module name="global"><param name="coordinateSystem" value="EPSG:2180"/></module><module name="qsim"><param name="sampleSize" value="{sample}"/></module></config>',
        encoding="utf-8",
    )
    rows = sorted(events, key=lambda line: float(viz_index.field(line, "time")))
    viz_index.write_zst(
        run_dir / viz_index.EVENTS_NAME,
        '<?xml version="1.0"?>\n<events>\n' + "\n".join(rows) + "\n</events>\n",
    )
    return run_dir


class TempRun:
    """with TempRun(events) as run_dir: ... Katalog znika po wyjściu."""

    def __init__(self, events, **kw):
        self.events, self.kw = events, kw

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="viz_test_")
        return write_run(Path(self._tmp.name) / "mini", self.events, **self.kw)

    def __exit__(self, *exc):
        self._tmp.cleanup()


def write_plans(run_dir, kinds):
    """output_plans.xml.zst z samymi atrybutami osób ({person: {atrybut: wartość}}), w układzie linii MATSim."""
    lines = ['<?xml version="1.0"?>', "<population>"]
    for person, attrs in kinds.items():
        lines.append(f'<person id="{person}">')
        lines.append("<attributes>")
        lines += [f'<attribute name="{k}" class="java.lang.String">{v}</attribute>' for k, v in attrs.items()]
        lines += ["</attributes>", '<plan score="1" selected="yes">', "</plan>", "</person>"]
    lines.append("</population>")
    viz_index.write_zst(Path(run_dir) / "output_plans.xml.zst", "\n".join(lines) + "\n")
