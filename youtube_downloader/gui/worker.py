"""Indirmeleri arka planda calistiran QObject worker.

Iki fazli calisir:
  1. COZUMLEME: Her girdi satiri ogelere acilir. Tekil video -> 1 oge;
     oynatma listesi -> N oge. Cozumlenen her oge tabloya satir olarak eklenir.
  2. INDIRME: Cozumlenen ogeler SIRAYLA indirilir.
       * Kullanici "o sirayla indirsin" dedigi icin sira korunur.
       * Sirali indirme YouTube'a daha nazik davranir -> engellenme riski azalir.

UI ile yalnizca Qt sinyalleri uzerinden konusur; UI'yi dogrudan ellemez.
Her is benzersiz job_id ile tanimlanir (bir satir birden cok ise acilabildigi icin).
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot

from ..core.downloader import DownloadCancelled, Downloader, ResolvedEntry
from ..core.models import DownloadJob, JobStatus


class DownloadWorker(QObject):
    """Girdi satirlarini cozumleyip indiren worker. Kendi QThread'inde calistirilir."""

    # --- Cozumleme fazi sinyalleri ---
    resolving = Signal(int)        # cozumlenmekte olan satir numarasi
    jobs_added = Signal(object)    # list[DownloadJob] — bir kaynaktan cikan ogeler (tabloya eklenir)
    resolve_done = Signal(int)     # toplam cozumlenen oge sayisi

    # --- Indirme fazi sinyalleri ---
    progress = Signal(int, float, str)  # job_id, yuzde, durum_metni
    job_done = Signal(int, bool, str)   # job_id, basari, mesaj (yol veya hata)

    # --- Uyari ---
    # Liste verildigi halde acilamadi (ozel/erisime kapali): line_number, url
    private_playlist = Signal(int, str)

    # --- Genel ---
    log = Signal(str)
    finished = Signal(int, int)    # basarili_sayisi, toplam

    # Ozel/erisime kapali liste icin kullaniciya gosterilecek ipucu.
    _PRIVATE_PLAYLIST_HINT = (
        "Liste özel/erişime kapalı olabilir. Ayarlar → 'Tarayıcı çerezleri'nden "
        "YouTube'a giriş yaptığınız tarayıcıyı seçip tekrar deneyin."
    )

    def __init__(self, source_jobs: list[DownloadJob], downloader: Downloader) -> None:
        super().__init__()
        self._source_jobs = source_jobs
        self._downloader = downloader
        self._cancel_event = threading.Event()

    @Slot()
    def run(self) -> None:
        """QThread.started sinyaline baglanir; cozumleme + indirme yapar."""
        resolved = self._resolve_phase()
        self.resolve_done.emit(len(resolved))
        if not resolved or self._cancel_event.is_set():
            self.finished.emit(0, len(resolved))
            return
        self._download_phase(resolved)

    # ------------------------------------------------------------------ #
    # Faz 1: Cozumleme
    # ------------------------------------------------------------------ #
    def _resolve_phase(self) -> list[DownloadJob]:
        resolved: list[DownloadJob] = []
        next_id = 0

        for src in self._source_jobs:
            if self._cancel_event.is_set():
                break
            self.resolving.emit(src.line_number)

            looks_like_playlist = "list=" in src.url.lower()

            try:
                entries = self._downloader.expand_entries(src.url, self._cancel_event)
            except DownloadCancelled:
                break
            except Exception as exc:  # noqa: BLE001 - cozumleme basarisizsa tekil dene
                self.log.emit(
                    f"⚠ [{src.line_number}] Çözümlenemedi, tek video olarak denenecek: {exc}"
                )
                entries = [ResolvedEntry(url=src.url)]

            if not entries:
                # Liste bekleniyordu ama hicbir oge cikmadi -> muhtemelen ozel/erisime kapali.
                msg = f"✗ [{src.line_number}] İçerik bulunamadı: {src.url}"
                if looks_like_playlist:
                    msg += "\n     ↳ " + self._PRIVATE_PLAYLIST_HINT
                    self.private_playlist.emit(src.line_number, src.url)
                self.log.emit(msg)
                continue

            # Liste bağlantısı verildi ama tek öğe çıktıysa liste açılamamıştır (özel olabilir).
            if looks_like_playlist and len(entries) <= 1:
                self.log.emit(
                    f"⚠ [{src.line_number}] Liste açılamadı, yalnızca 1 öğe alındı.\n"
                    f"     ↳ {self._PRIVATE_PLAYLIST_HINT}"
                )
                self.private_playlist.emit(src.line_number, src.url)

            batch: list[DownloadJob] = []
            for entry in entries:
                job = DownloadJob(
                    url=entry.url,
                    media_format=src.media_format,
                    line_number=src.line_number,
                    job_id=next_id,
                    playlist_title=entry.playlist_title,
                )
                job.title = entry.title
                resolved.append(job)
                batch.append(job)
                next_id += 1

            if len(entries) > 1:
                name = entries[0].playlist_title or "Oynatma listesi"
                self.log.emit(f"≡ [{src.line_number}] Liste: “{name}” — {len(entries)} öğe")
            self.jobs_added.emit(batch)

        return resolved

    # ------------------------------------------------------------------ #
    # Faz 2: Indirme
    # ------------------------------------------------------------------ #
    def _download_phase(self, jobs: list[DownloadJob]) -> None:
        success = 0
        total = len(jobs)
        self.log.emit(f"▶ {total} öğe indiriliyor…")

        for job in jobs:
            if self._cancel_event.is_set():
                self.log.emit("⏹ Kalan işler iptal edildi.")
                break

            self.progress.emit(job.job_id, 0.0, JobStatus.DOWNLOADING.value)

            def on_progress(percent: float, status: JobStatus, jid=job.job_id) -> None:
                self.progress.emit(jid, percent, status.value)

            try:
                self._downloader.download(
                    job,
                    progress_callback=on_progress,
                    cancel_event=self._cancel_event,
                    log=self.log.emit,
                )
                success += 1
                self.job_done.emit(job.job_id, True, job.output_path)
            except DownloadCancelled:
                self.job_done.emit(job.job_id, False, "İptal edildi")
                self.log.emit("⏹ Kalan işler iptal edildi.")
                break
            except Exception as exc:  # noqa: BLE001
                self.job_done.emit(job.job_id, False, str(exc))

        self.finished.emit(success, total)

    @Slot()
    def cancel(self) -> None:
        """Indirmeyi durdurmayi ister; aktif indirme bir sonraki adimda kesilir."""
        self._cancel_event.set()
