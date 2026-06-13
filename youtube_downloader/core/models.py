"""Etki alanı (domain) modelleri.

Bu modul UI ve indirme motorundan bagimsizdir; yalnizca veri yapilarini ve
bunlarin temel davranislarini tanimlar. Boylece is mantigi test edilebilir kalir.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MediaFormat(Enum):
    """Indirilecek medya turu."""

    VIDEO = "video"
    MP3 = "mp3"

    @classmethod
    def from_text(cls, text: str) -> "MediaFormat":
        """Serbest metni (ör. 'MP3', 'video', 'ses') bir MediaFormat'a cevirir.

        Raises:
            ValueError: Metin taninmayan bir formatsa.
        """
        key = text.strip().lower()
        if key not in _FORMAT_ALIASES:
            raise ValueError(f"Tanınmayan format: {text!r}")
        return _FORMAT_ALIASES[key]

    @property
    def label(self) -> str:
        return "Video (MP4)" if self is MediaFormat.VIDEO else "Ses (MP3)"


# Kullanicinin yazabilecegi takma adlar -> format eslemesi.
# Enum disinda tutulur ki Enum metaclass'i bunu bir uye sanmasin.
_FORMAT_ALIASES: dict[str, MediaFormat] = {
    "video": MediaFormat.VIDEO,
    "mp4": MediaFormat.VIDEO,
    "görüntü": MediaFormat.VIDEO,
    "goruntu": MediaFormat.VIDEO,
    "v": MediaFormat.VIDEO,
    "mp3": MediaFormat.MP3,
    "ses": MediaFormat.MP3,
    "audio": MediaFormat.MP3,
    "müzik": MediaFormat.MP3,
    "muzik": MediaFormat.MP3,
    "m": MediaFormat.MP3,
}


class JobStatus(Enum):
    """Bir indirme isinin yasam dongusundeki durumu."""

    PENDING = "Bekliyor"
    DOWNLOADING = "İndiriliyor"
    PROCESSING = "Dönüştürülüyor"
    DONE = "Tamamlandı"
    ERROR = "Hata"
    CANCELLED = "İptal edildi"


@dataclass
class DownloadJob:
    """Tek bir indirme isi. Kullanicinin girdigi her gecerli satira karsilik gelir."""

    url: str
    media_format: MediaFormat
    line_number: int  # Kullanicinin girdigi 1 tabanli satir numarasi.

    # Benzersiz kuyruk kimligi. Tek bir satir (oynatma listesi) birden cok ise
    # acilabildiginden, satir numarasi tek basina kimlik olamaz. Orkestrator atar.
    job_id: int = 0
    # Is bir oynatma listesinden geldiyse listenin basligi (bos ise tekil video).
    playlist_title: str = ""

    # Calisma sirasinda guncellenen alanlar.
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0  # 0.0 - 100.0
    title: str = ""
    output_path: str = ""
    error: str = ""

    @property
    def display_name(self) -> str:
        """Tabloda gosterilecek ad: baslik varsa baslik, yoksa kisa URL."""
        return self.title or self.short_url

    @property
    def short_url(self) -> str:
        """Tabloya sigacak kisaltilmis URL gosterimi."""
        return self.url if len(self.url) <= 60 else self.url[:57] + "..."
