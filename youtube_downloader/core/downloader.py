"""yt-dlp tabanli indirme motoru.

Tasarim hedefleri:
  * UI'dan tamamen bagimsiz (Qt importu yok) -> test edilebilir, yeniden kullanilabilir.
  * TV ve arac ekranlariyla azami uyum: Video = MP4 (H.264/AVC + AAC),
    MP3 = standart MP3 + ID3 etiketleri + kapak gorseli.
  * YouTube engellerine karsi dayaniklilik: yeniden denemeler, tarayici
    cerezleri secenegi ve guncel bir istemci yapilandirmasi.
  * Iptal edilebilirlik: bir threading.Event ile guvenli durdurma.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

import yt_dlp

from ..resources import available_js_runtimes, bundled_ffmpeg_location
from .models import DownloadJob, JobStatus, MediaFormat


def _js_runtime_opts() -> dict:
    """YouTube imza/challenge cozumu icin JS ortami secenekleri.

    YouTube artik formatlari cozmek icin bir JS calisma ortami (deno/node) ister;
    yoksa cogu format eksik gelir ("Requested format is not available"). Sistemde
    bir ortam bulunursa yt-dlp'ye bildirilir; cozucu betikler 'yt-dlp-ejs' paketinden
    yerel olarak gelir (calisma aninda agdan indirmeye gerek kalmaz).
    """
    runtimes = available_js_runtimes()
    return {"js_runtimes": runtimes} if runtimes else {}

# Ilerleme bildirimi icin geri cagrim imzasi: (yuzde, durum).
ProgressCallback = Callable[[float, JobStatus], None]
# Serbest metin gunluk satirlari icin geri cagrim.
LogCallback = Callable[[str], None]


@dataclass
class ResolvedEntry:
    """Cozumlenmis tek bir indirilebilir oge (tekil video veya liste ogesi)."""

    url: str
    title: str = ""
    playlist_title: str = ""  # Bir oynatma listesinden geldiyse listenin basligi.


class DownloadCancelled(Exception):
    """Kullanici indirmeyi iptal ettiginde ic akista firlatilir."""


class Downloader:
    """Tek tek isleri indiren motor. Durumsuzdur; her cagri kendi icinde tamdir."""

    def __init__(
        self,
        output_dir: str,
        max_height: int = 1080,
        mp3_quality: str = "320",
        cookies_from_browser: str | None = None,
    ) -> None:
        """
        Args:
            output_dir: Indirilen dosyalarin yazilacagi klasor.
            max_height: Azami video yuksekligi (piksel). TV/arac uyumu icin 1080.
            mp3_quality: MP3 bit hizi (kbps), ornegin '320' veya '192'.
            cookies_from_browser: 'chrome'/'firefox'/'edge' gibi; bot/yas
                dogrulamalarini asmak icin tarayici cerezlerini kullanir. None ise kapali.
        """
        self.output_dir = output_dir
        self.max_height = max_height
        self.mp3_quality = mp3_quality
        self.cookies_from_browser = cookies_from_browser or None

    # ------------------------------------------------------------------ #
    # Format secimi
    # ------------------------------------------------------------------ #
    def _video_format_selector(self) -> str:
        """H.264 (avc1) + AAC (m4a) onceligi olan format secici dizesi.

        Oncelik sirasi:
          1. avc1 video + m4a ses  -> dogrudan MP4, kayipsiz birlestirme.
          2. avc1 video + en iyi ses -> ses farkli ise yine de avc1 video.
          3. avc1 birlesik akis     -> tek parca avc1.
          4. herhangi bir akis      -> son care (yine de MP4'e remux edilir).

        avc1/m4a YouTube'da 1080p'ye kadar mevcuttur; bu da TV ve arac
        oynaticilarinda en genis uyumu saglar (VP9/AV1/Opus genelde desteklenmez).
        """
        h = self.max_height
        return (
            f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio/"
            f"best[vcodec^=avc1][height<={h}]/"
            f"best[height<={h}]/best"
        )

    def _base_opts(self, progress_hook: Callable[[dict], None]) -> dict:
        """Hem video hem ses icin ortak yt-dlp secenekleri."""
        opts: dict = {
            # Cikti sablonu: araba USB'leri FAT32 oldugundan guvenli dosya adlari.
            "outtmpl": os.path.join(self.output_dir, "%(title)s.%(ext)s"),
            "windowsfilenames": True,  # FAT32/USB uyumu icin gecersiz karakterleri eler.
            "trim_file_name": 180,
            # Her satir tek bir videodur; yanlislikla koca oynatma listesi inmesin.
            "noplaylist": True,
            # Dayaniklilik.
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "concurrent_fragment_downloads": 4,
            "ignoreerrors": False,
            "continuedl": True,
            # Gurultu yonetimi: yt-dlp kendi yazdirmasin, biz hook ile yonetelim.
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "consoletitle": False,
            "progress_hooks": [progress_hook],
            # YouTube imza/challenge cozumu icin JS ortami (deno/node) bildir.
            **_js_runtime_opts(),
        }
        if self.cookies_from_browser:
            # Bot/yas dogrulamasi ("Sign in to confirm...") engellerini asmaya yardimci olur.
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
        # Paketlenmis (Windows .exe) surumde ffmpeg uygulamayla birlikte gelir.
        ffmpeg_dir = bundled_ffmpeg_location()
        if ffmpeg_dir:
            opts["ffmpeg_location"] = ffmpeg_dir
        return opts

    def _build_opts(self, job: DownloadJob, progress_hook: Callable[[dict], None]) -> dict:
        """Ise (video/mp3) gore tam yt-dlp secenek sozlugunu olusturur."""
        opts = self._base_opts(progress_hook)

        if job.media_format is MediaFormat.VIDEO:
            opts.update(
                {
                    "format": self._video_format_selector(),
                    "merge_output_format": "mp4",
                    "postprocessors": [
                        # Konteyner kesin MP4 olsun (gerekirse yeniden paketle).
                        {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
                        # Baslik/sanatci gibi ust verileri goma.
                        {"key": "FFmpegMetadata", "add_metadata": True},
                    ],
                    # 'faststart': moov atomunu basa alir -> TV'lerde aninda oynatma.
                    "postprocessor_args": {"merger": ["-movflags", "+faststart"]},
                }
            )
        else:  # MP3
            opts.update(
                {
                    "format": "bestaudio/best",
                    "writethumbnail": True,  # Kapak gomme icin gereklidir.
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": self.mp3_quality,
                        },
                        # ID3 etiketleri: arac ekraninda sanatci/parca adi gorunur.
                        {"key": "FFmpegMetadata", "add_metadata": True},
                        # Kapak gorselini ID3'e goma (oynaticilarda albtum kapagi).
                        {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                    ],
                }
            )
        return opts

    # ------------------------------------------------------------------ #
    # Cozumleme (oynatma listelerini ogelere acma)
    # ------------------------------------------------------------------ #
    def expand_entries(
        self, url: str, cancel_event: threading.Event | None = None
    ) -> list[ResolvedEntry]:
        """Bir URL'yi indirilebilir ogelere cozumler.

        Tekil video icin tek elemanli liste; oynatma listesi icin listedeki her
        video bir ResolvedEntry olarak doner. 'extract_flat' sayesinde liste
        ogeleri tek tek tam cozumlenmez -> hizli ve YouTube'a daha az istek.

        Args:
            url: Video veya oynatma listesi baglantisi.
            cancel_event: Ayarliysa cozumleme atlanir (kullanici iptal etti).

        Raises:
            yt_dlp.utils.DownloadError: Cozumleme basarisiz olursa.
        """
        if cancel_event is not None and cancel_event.is_set():
            return []

        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",  # Liste ogelerini tek tek acmadan listele.
            "skip_download": True,
            "ignoreerrors": True,  # Listedeki silinmis/ozel videolar tum isi bozmasin.
            # Cozumleme de JS ortami isteyebilir (tekil video meta verisi vb.).
            **_js_runtime_opts(),
        }
        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info is None:
            return []
        return self._entries_from_info(info)

    @classmethod
    def _entries_from_info(cls, info: dict, playlist_title: str = "") -> list[ResolvedEntry]:
        """yt-dlp info sozlugunu duz bir ResolvedEntry listesine cevirir (saf fonksiyon).

        Ic ice oynatma listelerini (liste icinde liste) ozyinelemeli cozer.
        Ag erisimi YAPMAZ; bu sayede test edilebilir.
        """
        entries = info.get("entries")
        if entries is None:
            # Tekil video.
            return [
                ResolvedEntry(
                    url=cls._clean_video_url(info),
                    title=info.get("title", "") or "",
                    playlist_title=playlist_title,
                )
            ]

        # Oynatma listesi: bu listenin basligini alt ogelere tasi.
        title = info.get("title", "") or playlist_title
        result: list[ResolvedEntry] = []
        for entry in entries:
            if not entry:  # silinmis/erisilemez oge -> None gelebilir
                continue
            result.extend(cls._entries_from_info(entry, playlist_title=title))
        return result

    @staticmethod
    def _clean_video_url(info: dict) -> str:
        """Info'dan temiz bir tekil-video URL'si uretir.

        Video kimliginden 'watch?v=ID' kurar; boylece artik &list= parametresi
        tasinmaz ve indirme sirasinda yanlislikla yeniden liste acilmaz.
        """
        video_id = info.get("id")
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return info.get("url") or info.get("webpage_url") or ""

    # ------------------------------------------------------------------ #
    # Indirme
    # ------------------------------------------------------------------ #
    def download(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback,
        cancel_event: threading.Event,
        log: LogCallback | None = None,
    ) -> None:
        """Tek bir isi indirir; ilerlemeyi geri cagrimlarla bildirir.

        Is nesnesi yerinde guncellenir (status, progress, title, output_path, error).

        Raises:
            DownloadCancelled: cancel_event indirme sirasinda set edilirse.
            yt_dlp.utils.DownloadError: Indirme basarisiz olursa.
        """
        os.makedirs(self.output_dir, exist_ok=True)

        def hook(d: dict) -> None:
            # Iptal istegi geldiyse akisin icinden guvenle cik.
            if cancel_event.is_set():
                raise DownloadCancelled()

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100.0) if total else 0.0
                job.progress = percent
                job.status = JobStatus.DOWNLOADING
                progress_callback(percent, JobStatus.DOWNLOADING)
            elif status == "finished":
                # Indirme bitti; siradaki asama ffmpeg ile donusturme/birlestirme.
                job.progress = 100.0
                job.status = JobStatus.PROCESSING
                progress_callback(100.0, JobStatus.PROCESSING)

        opts = self._build_opts(job, hook)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                job.title = info.get("title", "")
                # Son ciktinin yolunu bul (donusumden sonraki gercek dosya).
                job.output_path = self._resolve_output_path(ydl, info)
            job.status = JobStatus.DONE
            if log:
                log(f"✓ [{job.line_number}] {job.title or job.url} → {job.output_path}")
        except DownloadCancelled:
            job.status = JobStatus.CANCELLED
            if log:
                log(f"⏹ [{job.line_number}] İptal edildi: {job.url}")
            raise
        except Exception as exc:  # noqa: BLE001 - kullaniciya tum hatalari yansitiriz.
            job.status = JobStatus.ERROR
            job.error = str(exc)
            if log:
                log(f"✗ [{job.line_number}] Hata: {exc}")
            raise

    @staticmethod
    def _resolve_output_path(ydl: "yt_dlp.YoutubeDL", info: dict) -> str:
        """Donusum sonrasi olusan son dosyanin yolunu bulmaya calisir."""
        # Son islenen dosya yolu varsa onu kullan (en guvenilir).
        requested = info.get("requested_downloads")
        if requested:
            last = requested[-1]
            return last.get("filepath") or last.get("_filename", "")
        try:
            return ydl.prepare_filename(info)
        except Exception:  # noqa: BLE001
            return ""
