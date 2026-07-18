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


# yt-dlp'nin desteklegi JS calisma ortamlari -> (yt-dlp anahtari, calistirilabilir adi).
# Oncelik sirasi yt-dlp ile ayni (en yuksek once). YouTube artik imza/n cozumu icin
# bir JS ortami ISTER; yoksa bircok format (MP3 icin gereken m4a ses dahil) eksik gelir
# -> "Requested format is not available". Cozucu betikler 'yt-dlp-ejs' paketinden gelir.
_JS_RUNTIMES: tuple[tuple[str, str], ...] = (
    ("deno", "deno"),
    ("node", "node"),
    ("bun", "bun"),
    ("quickjs", "qjs"),
)


def _bundled_runtime_path(binary: str) -> str | None:
    """Paketlenmis (frozen) surumde uygulama yaninda gomulu bir JS ikilisi arar.

    Windows .exe'sine (ffmpeg gibi) bir JS ortami gomuldugunde, sistemde deno/node
    kurulu olmasa bile calissin diye. Kaynaktan calisirken None doner (sistem PATH'i
    kullanilir).
    """
    if not getattr(sys, "frozen", False):
        return None
    for base in _frozen_base_dirs():
        for name in (f"{binary}.exe", binary):
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                return candidate
    return None


def available_js_runtimes() -> dict[str, dict]:
    """Sistemde bulunan JS calisma ortamlarini yt-dlp icin hazir sekilde dondurur.

    Once uygulamayla gomulu ikili (frozen surum), yoksa sistemdeki PATH aranir.
    Donen sozluk dogrudan yt-dlp'nin 'js_runtimes' secenegine verilir:
    {ad: {"path": <ikili>}}. Bos sozluk hicbir ortam bulunamadigi anlamina gelir
    (bu durumda YouTube formatlari eksik gelebilir; kullaniciya Deno/Node onerilir).
    """
    runtimes: dict[str, dict] = {}
    for key, binary in _JS_RUNTIMES:
        path = _bundled_runtime_path(binary) or shutil.which(binary)
        if path:
            runtimes[key] = {"path": path}
    return runtimes
