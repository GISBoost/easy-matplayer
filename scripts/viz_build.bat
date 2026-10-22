@echo off
REM Builds easy-matanimation (PyInstaller onedir) and zips it to build_viz\easy-matanimation-windows.zip.
REM Single source of truth for local and release builds. Needs uv (https://docs.astral.sh/uv/); uv fetches Python 3.12 itself.
setlocal
cd /d "%~dp0.."

where uv >nul 2>nul
if errorlevel 1 (
    echo Brak uv w PATH. Zainstaluj: https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

if not exist build_viz\venv\Scripts\python.exe (
    uv venv build_viz\venv --python 3.12 || exit /b 1
)
uv pip install -q --python build_viz\venv\Scripts\python.exe -r viz_player\requirements.txt -r viz_player\requirements-build.txt || exit /b 1

build_viz\venv\Scripts\python.exe -m PyInstaller viz_player\easy-matanimation.spec --noconfirm --clean --distpath build_viz\dist --workpath build_viz\work
if errorlevel 1 (
    echo Budowa nie powiodla sie.
    exit /b 1
)

REM PyInstaller reports a module it cannot compile (e.g. a syntax error) only as a warning and still builds; treat that as a failed build.
findstr /C:"invalid module" build_viz\work\easy-matanimation\warn-easy-matanimation.txt >nul 2>nul
if not errorlevel 1 (
    echo Build has invalid modules, see build_viz\work\easy-matanimation\warn-easy-matanimation.txt
    exit /b 1
)

REM Quick check of the built exe: it must start and print its version (a windowed exe writes it to the log in the data dir).
set "EASY_MATANIMATION_DATA=%CD%\build_viz\check_data"
if exist "%EASY_MATANIMATION_DATA%" rmdir /s /q "%EASY_MATANIMATION_DATA%"
mkdir "%EASY_MATANIMATION_DATA%"
start /wait "" build_viz\dist\easy-matanimation\easy-matanimation.exe --version
if errorlevel 1 (
    echo The built exe does not start.
    exit /b 1
)
findstr /C:"easy-matanimation 0." "%EASY_MATANIMATION_DATA%\easy-matanimation.log" >nul 2>nul
if errorlevel 1 (
    echo The built exe did not report its version.
    exit /b 1
)
set "EASY_MATANIMATION_DATA="

if exist build_viz\easy-matanimation-windows.zip del build_viz\easy-matanimation-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'build_viz\dist\easy-matanimation' -DestinationPath 'build_viz\easy-matanimation-windows.zip'"
if errorlevel 1 exit /b 1

echo.
echo Gotowe: %CD%\build_viz\dist\easy-matanimation\easy-matanimation.exe
echo Zip:    %CD%\build_viz\easy-matanimation-windows.zip
