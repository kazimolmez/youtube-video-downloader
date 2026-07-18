# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — hem Linux hem Windows icin tek dosyali (onefile) derleme.

Kullanim (proje kokunden):
    pyinstaller packaging/youtube-downloader.spec --noconfirm

Notlar:
  * yt-dlp'nin tum alt modulleri/verisi toplanir (lazy extractor'lar kaybolmasin).
  * packaging/vendor/ffmpeg/ klasoru varsa icindeki ikililer gomulur (Windows).
    Linux'ta ffmpeg .deb bagimliligi (Depends: ffmpeg) ile gelir, gomulmez.
  * packaging/assets/icon.ico (Windows) varsa uygulama ikonu olarak kullanilir.
"""

import os

from PyInstaller.utils.hooks import collect_all

# SPECPATH: bu spec dosyasinin bulundugu klasor (PyInstaller saglar).
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))  # noqa: F821

datas = []
binaries = []
hiddenimports = []

# yt-dlp eksiksiz toplansin (extractor'lar dinamik yuklendigi icin sart).
# yt_dlp_ejs: YouTube JS challenge cozucu .min.js dosyalari (veri olarak toplanmali).
for pkg in ("yt_dlp", "yt_dlp_ejs"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Opsiyonel: packaging/vendor/ altindaki tum ikilileri goml (ozellikle Windows .exe icin).
#   vendor/ffmpeg/ -> ffmpeg.exe, ffprobe.exe
#   vendor/js/     -> deno.exe (YouTube JS challenge cozumu; yoksa formatlar eksik gelir)
# Hepsi frozen uygulamanin kok klasorune (".") acilir; resources.py oradan bulur.
vendor_root = os.path.join(PROJECT_ROOT, "packaging", "vendor")
if os.path.isdir(vendor_root):
    for dirpath, _dirs, files in os.walk(vendor_root):
        for name in files:
            full = os.path.join(dirpath, name)
            if os.path.isfile(full):
                binaries.append((full, "."))

# Opsiyonel ikon (Windows .ico).
icon_ico = os.path.join(PROJECT_ROOT, "packaging", "assets", "icon.ico")
icon_arg = icon_ico if os.path.isfile(icon_ico) else None

a = Analysis(
    [os.path.join(PROJECT_ROOT, "youtube_downloader", "app.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],  # kullanilmiyor; boyutu kuculur.
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="youtube-downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,        # pencere uygulamasi; konsol acilmaz.
    disable_windowed_traceback=False,
    icon=icon_arg,
)
