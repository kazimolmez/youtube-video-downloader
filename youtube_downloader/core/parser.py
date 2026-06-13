"""Kullanici girisini (her satirda 'link | format') DownloadJob'lara cevirir.

Tasarim: ayristirma saf (pure) ve yan etkisizdir; gecerli isleri ve hatalari
ayri ayri dondurur. Bu sayede UI hem isleri kuyruga ekleyebilir hem de
kullaniciya satir bazli hata gosterebilir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DownloadJob, MediaFormat

# Satirdaki link ile format ayraci. Bircok yaygin ayraci kabul ederiz.
_SEPARATOR = re.compile(r"\s*[|;,\t]\s*")

# Kabaca http(s) baglantisi dogrulamasi. yt-dlp asil dogrulamayi kendi yapar;
# burada amac kullaniciya erken ve anlasilir geri bildirim vermektir.
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class ParseError:
    """Ayristirilamayan bir satir hakkinda bilgi."""

    line_number: int
    raw: str
    reason: str


@dataclass
class ParseResult:
    jobs: list[DownloadJob]
    errors: list[ParseError]


def parse_input(text: str, default_format: MediaFormat) -> ParseResult:
    """Cok satirli girisi ayristirir.

    Kurallar:
      * Bos satirlar ve '#' ile baslayan satirlar (yorum) atlanir.
      * Bir satir 'URL | format' seklindedir; format kismi opsiyoneldir.
      * Format belirtilmezse `default_format` kullanilir.
      * Ayrac olarak '|', ';', ',' veya sekme kabul edilir.

    Args:
        text: Kullanicinin metin alanina girdigi ham metin.
        default_format: Satirda format belirtilmediginde kullanilacak varsayilan.

    Returns:
        Gecerli isleri ve satir bazli hatalari iceren ParseResult.
    """
    jobs: list[DownloadJob] = []
    errors: list[ParseError] = []

    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = _SEPARATOR.split(line, maxsplit=1)
        url = parts[0].strip()
        format_text = parts[1].strip() if len(parts) > 1 else ""

        if not _URL_PATTERN.match(url):
            errors.append(
                ParseError(index, raw_line, "Geçerli bir http(s) bağlantısı değil")
            )
            continue

        if format_text:
            try:
                media_format = MediaFormat.from_text(format_text)
            except ValueError:
                errors.append(
                    ParseError(
                        index,
                        raw_line,
                        f"Bilinmeyen format {format_text!r} (video veya mp3 kullanın)",
                    )
                )
                continue
        else:
            media_format = default_format

        jobs.append(DownloadJob(url=url, media_format=media_format, line_number=index))

    return ParseResult(jobs=jobs, errors=errors)
