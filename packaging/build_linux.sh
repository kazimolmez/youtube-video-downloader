#!/usr/bin/env bash
# Linux icin tek dosyali ikili + .deb paketi uretir.
#
# Kullanim (proje kokunden):
#     packaging/build_linux.sh
#
# Cikti:
#     dist/youtube-downloader                 (tek dosyali calistirilabilir)
#     dist/youtube-downloader_<surum>_amd64.deb
#
# Gereksinim: python3-venv, dpkg-deb (dpkg), build sirasinda internet.
set -euo pipefail

cd "$(dirname "$0")/.."          # proje koku
ROOT="$(pwd)"
VERSION="$(python3 -c "import youtube_downloader as p; print(p.__version__)")"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
BUILD_VENV=".build-venv"

echo "==> Sürüm: ${VERSION}  Mimari: ${ARCH}"

# 1) Yalitilmis derleme ortami.
echo "==> Derleme ortamı hazırlanıyor…"
python3 -m venv "${BUILD_VENV}"
"${BUILD_VENV}/bin/python" -m pip install --upgrade pip >/dev/null
"${BUILD_VENV}/bin/python" -m pip install -r requirements.txt pyinstaller >/dev/null

# 2) PyInstaller ile tek dosyali ikili.
echo "==> PyInstaller derlemesi…"
"${BUILD_VENV}/bin/pyinstaller" packaging/youtube-downloader.spec --noconfirm --clean >/dev/null
BIN="dist/youtube-downloader"
test -f "${BIN}"

# 3) .deb agac yapisini olustur.
echo "==> .deb paketi oluşturuluyor…"
PKG="build/deb/youtube-downloader_${VERSION}_${ARCH}"
rm -rf "${PKG}"
mkdir -p "${PKG}/DEBIAN" \
         "${PKG}/opt/youtube-downloader" \
         "${PKG}/usr/bin" \
         "${PKG}/usr/share/applications" \
         "${PKG}/usr/share/icons/hicolor/scalable/apps"

install -m 0755 "${BIN}" "${PKG}/opt/youtube-downloader/youtube-downloader"
ln -sf /opt/youtube-downloader/youtube-downloader "${PKG}/usr/bin/youtube-downloader"
install -m 0644 packaging/deb/youtube-downloader.desktop \
        "${PKG}/usr/share/applications/youtube-downloader.desktop"
install -m 0644 packaging/assets/icon.svg \
        "${PKG}/usr/share/icons/hicolor/scalable/apps/youtube-downloader.svg"

INSTALLED_KB="$(du -sk "${PKG}/opt" | cut -f1)"
cat > "${PKG}/DEBIAN/control" <<EOF
Package: youtube-downloader
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: ffmpeg
Recommends: nodejs
Installed-Size: ${INSTALLED_KB}
Maintainer: YouTube İndirici <noreply@example.com>
Description: TV ve araç ekranı uyumlu YouTube video/mp3 indirici
 Bağlantıları satır satır vererek video (MP4/H.264) veya ses (MP3) indirir.
 Oynatma listeleri desteklenir. Dosyalar TV ve araç ekranlarıyla uyumludur.
EOF

dpkg-deb --build --root-owner-group "${PKG}" "dist/" >/dev/null
echo "==> Tamamlandı:"
ls -1 dist/*.deb
echo "   Kurulum:  sudo apt install ./$(ls dist/*.deb | head -1)"
