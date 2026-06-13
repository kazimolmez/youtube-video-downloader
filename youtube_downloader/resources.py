"""Calisma zamani kaynak (resource) bulucular.

Uygulama hem kaynaktan (python -m ...) hem de PyInstaller ile paketlenmis
(donmus / 'frozen') halde calisabilir. Bu modul, ffmpeg gibi disaridan gelen
kaynaklarin her iki durumda da dogru bulunmasini saglar.
"""

from __future__ import annotations

import os
import shutil
import sys


def _frozen_base_dirs() -> list[str]:
    """Paketlenmis uygulamada kaynaklarin aranacagi olasi klasorler."""
    dirs: list[str] = []
    # PyInstaller onefile: kaynaklar gecici _MEIPASS klasorune acilir.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(meipass)
    # onedir / yaninda duran ikililer: calistirilabilirin yani.
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    dirs.append(exe_dir)
    dirs.append(os.path.join(exe_dir, "ffmpeg"))
    return dirs


def bundled_ffmpeg_location() -> str | None:
    """Paketlenmis ffmpeg'in bulundugu klasoru dondurur; yoksa None.

    yt-dlp'nin 'ffmpeg_location' secenegine verilir. None donerse yt-dlp
    sistemdeki ffmpeg'i (PATH) kullanir — bu, .deb kurulumunda 'Depends: ffmpeg'
    sayesinde mevcut olur.
    """
    if not getattr(sys, "frozen", False):
        return None  # Kaynaktan calisiyoruz: sistem ffmpeg'i kullanilir.

    exe_names = ("ffmpeg.exe", "ffmpeg")
    for base in _frozen_base_dirs():
        for name in exe_names:
            if os.path.isfile(os.path.join(base, name)):
                return base
    return None


def system_ffmpeg_available() -> bool:
    """Sistemde (PATH) ffmpeg var mi? Kullaniciya erken uyari icin."""
    return shutil.which("ffmpeg") is not None or bundled_ffmpeg_location() is not None
