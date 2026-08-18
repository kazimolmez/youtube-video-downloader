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

# yt-dlp'nin OPSIYONEL bagimliliklari (bkz. yt_dlp/dependencies/__init__.py).
# Hepsi try/except ile ice aktarilir: eksikse yt-dlp o yetenegi sessizce kapatir
# ya da calisma aninda hata basar ("... module is not installed").
# Kaynaktan calisirken sistemde bulunabilirler; ancak onefile ikili YALNIZCA kendi
# gomulu Python'ini kullanir, sistem site-packages'i GORMEZ. Bu yuzden burada
# acikca toplanmalari sart — aksi hâlde paket baska bir bilgisayarda hata verir.
#
# Platforma gore bir kismi kurulu olmayabilir (secretstorage/jeepney yalnizca
# Linux), o yuzden tek tek ve hata toleransli toplanir; Windows derlemesi kirilmaz.
OPTIONAL_PACKAGES = (
    "secretstorage",   # Chrome/Edge/Brave cerez anahtari (Linux, D-Bus Secret Service)
    "jeepney",         # secretstorage'in D-Bus katmani
    "cryptography",    # cerez sifre cozumu (Chrome v10/v11 AES-GCM)
    "certifi",         # SSL kok sertifikalari (cacert.pem VERI olarak da gomulmeli)
    "brotli",          # HTTP brotli acma (YouTube brotli ile yanit verir)
    "requests",        # yt-dlp'nin tercih ettigi HTTP arka ucu
    "urllib3",         # requests bagimliligi
    "websockets",      # canli yayin extractor'lari
    "mutagen",         # MP3 ID3 etiketi + kapak gorseli gomme
    "Cryptodome",      # pycryptodomex — HLS AES-128 cozumu
)

_missing = []
for pkg in OPTIONAL_PACKAGES:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    except Exception:
        _missing.append(pkg)   # bu platformda/ortamda yok — yetenek devre disi kalir
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

if _missing:
    print(f"[spec] UYARI: su opsiyonel paketler bulunamadi, gomulmedi: {', '.join(_missing)}")

# Opsiyonel: packaging/vendor/ altindaki tum ikilileri goml (ozellikle Windows .exe icin).
#   vendor/ffmpeg/ -> ffmpeg.exe, ffprobe.exe
#   vendor/js/     -> qjs.exe (QuickJS; YouTube JS challenge cozumu, yoksa formatlar eksik gelir.
#                    Kucuk tek dosya oldugu icin onefile'a sorunsuz gomulur — deno cok buyuktu.)
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
