# PyInstaller: easy-matplayer (folder z easy-matplayer.exe). Budowa: scripts\viz_build.bat (jedyne źródło prawdy, lokalnie i w CI).
#
# onedir, nie onefile: onefile rozpakowuje ok. 100 MB do katalogu tymczasowego przy każdym starcie (kilka do kilkunastu sekund)
# i częściej łapie go antywirus. console=False: okno bez czarnej konsoli; komunikaty idą do easy-matplayer.log (viz_player/startup.py).
#
# pathex musi zawierać pipeline/: viz_player/player.py dopisuje go do sys.path dopiero w czasie działania, a PyInstaller czyta tylko
# instrukcje import, więc bez pathex build przechodzi, a gotowy program kończy się ModuleNotFoundError (ta sama pułapka co w chart_lab).
# Źródła pipeline/viz_*.py leżą w paczce jako dane, bo moduły liczą skrót własnego pliku do klucza cache (w paczce __file__ to nieistniejący .pyc).
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct,
                                                 VSVersionInfo)

HERE = Path(SPECPATH).resolve()  # viz_player/
ROOT = HERE.parent
VERSION = re.search(r'__version__ = "([^"]+)"', (HERE / "__init__.py").read_text(encoding="utf-8")).group(1)
NUMS = tuple([int(x) for x in VERSION.split(".")] + [0, 0, 0, 0])[:4]

datas = [
    (str(HERE / "shell.html"), "viz_player"),
    (str(HERE / "engine.js"), "viz_player"),
    (str(HERE / "vendor"), "viz_player/vendor"),
    (str(HERE / "selftest"), "viz_player/selftest"),  # malutki plik OSM do smoke zbudowanego exe
    (str(ROOT / "config" / "viz_buildings.toml"), "config"),
    (str(ROOT / "LICENSE"), "."),
]
for name in ("viz_buildings", "viz_classes", "viz_engine", "viz_export", "viz_index"):
    datas.append((str(ROOT / "pipeline" / f"{name}.py"), "."))

hiddenimports = ["viz_buildings", "viz_classes", "viz_engine", "viz_export", "viz_index", "tkinter"]

a = Analysis(
    [str(HERE / "__main__.py")],
    pathex=[str(ROOT), str(ROOT / "pipeline")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "matplotlib", "pandas", "scipy", "geopandas", "IPython", "unittest", "pydoc_data"],
    noarchive=False,
)
pyz = PYZ(a.pure)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMS, prodvers=NUMS, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "GISBoost"),
            StringStruct("FileDescription", "easy-matplayer: MATSim run player"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "easy-matplayer"),
            StringStruct("LegalCopyright", "GPL-3.0-or-later"),
            StringStruct("OriginalFilename", "easy-matplayer.exe"),
            StringStruct("ProductName", "easy-matplayer"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="easy-matplayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(HERE / "icon.ico"),
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="easy-matplayer")
