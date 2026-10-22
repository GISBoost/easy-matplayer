"""Zrzut okna easy-matanimation przez user32 (Windows, PowerShell). Tylko do smoke; błąd zrzutu nie wywala testu."""
import os
import subprocess
import tempfile
from pathlib import Path


def window_png(path, title="easy-matanimation"):
    script = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Grab {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string c, string t);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[Grab]::SetProcessDPIAware() | Out-Null
$hwnd = [Grab]::FindWindowW([NullString]::Value, "__TITLE__")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "NOWINDOW"; exit 2 }
[Grab]::SetWindowPos($hwnd, [IntPtr](-1), 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
Start-Sleep -Milliseconds 400
$rect = New-Object Grab+RECT
[Grab]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
if ($w -lt 100 -or $h -lt 100) { Write-Output "SMALL $w $h"; exit 3 }
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
$bmp.Save($env:VIZ_GRAB, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
[Grab]::SetWindowPos($hwnd, [IntPtr](-2), 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
Write-Output "OK $w $h"
"""
    # ponytail: zrzut przez System.Drawing, bez dokładania Pillow do projektu
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script.replace("__TITLE__", title))
        ps1 = handle.name
    try:
        env = dict(os.environ)
        env["VIZ_GRAB"] = str(path)
        done = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30,
        )
        return (done.stdout or "") + (done.stderr or ""), done.returncode
    finally:
        Path(ps1).unlink(missing_ok=True)
