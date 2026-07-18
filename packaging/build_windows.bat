@echo off
REM Windows icin tek dosyali .exe uretir.
REM
REM Kullanim (proje kokunden, Windows komut isteminde):
REM     packaging\build_windows.bat
REM
REM Cikti:  dist\youtube-downloader.exe
REM
REM Notlar:
REM   * ffmpeg.exe ve ffprobe.exe dosyalarini packaging\vendor\ffmpeg\ icine
REM     koyarsaniz .exe icine gomulur (kullanici ayrica ffmpeg kurmak zorunda kalmaz).
REM     ffmpeg'i https://www.gyan.dev/ffmpeg/builds/ adresinden indirebilirsiniz.
REM   * qjs.exe (QuickJS) dosyasini packaging\vendor\js\ icine koyarsaniz .exe icine
REM     gomulur. YouTube imza/challenge cozumu icin bir JS ortami SARTTIR; yoksa
REM     formatlar eksik gelir ("Requested format is not available"). QuickJS kucuk
REM     tek dosyadir (~2 MB), onefile'a sorunsuz gomulur:
REM     https://github.com/quickjs-ng/quickjs/releases (qjs-windows-x86_64.exe)
REM     Indirdikten sonra 'qjs.exe' adiyla kaydedin (resources.py bu adla arar).
REM   * Windows .exe yalnizca Windows'ta derlenebilir (capraz derleme yok).

setlocal
cd /d "%~dp0\.."

echo ==^> Derleme ortami hazirlaniyor...
py -3 -m venv .build-venv || python -m venv .build-venv
call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo ==^> PyInstaller derlemesi...
pyinstaller packaging\youtube-downloader.spec --noconfirm --clean

echo ==^> Tamamlandi:
dir /b dist\youtube-downloader.exe
echo    Calistirmak icin: dist\youtube-downloader.exe
endlocal
