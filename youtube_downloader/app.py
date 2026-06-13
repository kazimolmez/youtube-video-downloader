"""Uygulama giris noktasi.

Calistirma:
    python -m youtube_downloader.app
veya
    ./run.sh
"""

from __future__ import annotations

import sys

# Mutlak import: hem "python -m youtube_downloader.app" hem de PyInstaller ile
# paketlenmis (app.py'nin __main__ olarak calistigi) halde sorunsuz calisir.
from youtube_downloader.gui.main_window import run


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
