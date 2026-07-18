# YouTube İndirici

YouTube'dan **video (MP4)** veya **ses (MP3)** indiren masaüstü uygulaması.
İndirilen dosyalar **TV ve araç içi ekranlarda** sorunsuz oynatılacak biçimde
üretilir. Bağlantıları satır satır yapıştırır, her biri için (isterseniz)
formatı belirtirsiniz; uygulama sırayla indirir.

---

## Öne çıkanlar

- 🎬 **Video → MP4 (H.264/AVC + AAC)** — TV ve araç oynatıcılarının neredeyse
  tamamıyla uyumlu format. Maks. 1080p (720p/480p de seçilebilir).
- 🎵 **Ses → MP3** — 320/256/192 kbps, **ID3 etiketleri** (başlık, sanatçı, yıl)
  ve **gömülü kapak görseli** ile. Araç ekranında parça bilgisi düzgün görünür.
- 📃 **Oynatma listesi desteği** — liste bağlantısı verdiğinizde tüm videolar
  tek tek çözümlenir ve her biri adıyla ayrı satır olarak kuyruğa eklenir.
- 📊 **Genel + tekil ilerleme** — genel yüzde, tamamlanan sayısı ve o an indirilen
  öğenin adı/yüzdesi anlık gösterilir; her satırın kendi ilerleme çubuğu vardır.
- ▶️ **Toplu ve sıralı indirme** — her satıra bir bağlantı; istediğiniz sırada.
- 🪟 **Pencere arayüzü** (PySide6/Qt) — ilerleme çubukları, kuyruk tablosu, günlük.
- 🛡️ **YouTube engellerine karşı dayanıklı** — otomatik yeniden denemeler ve
  isteğe bağlı **tarayıcı çerezleri** (bot / yaş doğrulaması engellerini aşmak için).
- ⚡ **TV için faststart** — MP4'lerde `moov` atomu başa alınır, anında oynatma.

---

## Hızlı başlangıç

### Gereksinimler

- Python 3.10+
- **ffmpeg** (format dönüştürme/birleştirme için zorunlu)
  ```bash
  sudo apt install ffmpeg        # Ubuntu/Debian
  ```

### Kurulum ve çalıştırma

En kolayı, sağlanan başlatıcıyı kullanmak (sanal ortamı kendisi kurar):

```bash
./run.sh
```

Veya elle:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m youtube_downloader.app
```

---

## Kullanım

1. Üstteki metin alanına **her satıra bir bağlantı** yazın.
2. Formatı `|` ile belirtin (opsiyonel). Belirtmezseniz seçili **varsayılan format** kullanılır.

```text
https://www.youtube.com/watch?v=XXXX | video
https://youtu.be/YYYY | mp3
https://www.youtube.com/playlist?list=ZZZZ | mp3   # tüm liste mp3 olarak iner
https://www.youtube.com/watch?v=WWWW               # format yok → varsayılan
# '#' ile başlayan satırlar yorumdur, atlanır
```

- Ayraç olarak `|`, `;`, `,` veya sekme kullanılabilir.
- Format takma adları: `video`/`mp4` ve `mp3`/`ses`/`audio`/`müzik`.
- **Oynatma listeleri:** Bağlantı bir liste içeriyorsa (örn. `&list=...`), liste
  tamamen çözümlenir ve her video o satırın formatında indirilir.

3. **Ayarlar**'dan kayıt klasörü, kalite ve (gerekiyorsa) tarayıcı çerezlerini seçin.
4. **İndir**'e bastığınızda önce bağlantılar **çözümlenir** (liste varsa videolara
   açılır), her öğe adıyla tabloya düşer, ardından sırayla indirilir. İlerlemeyi
   üstteki genel çubuktan, satır bazlı çubuklardan ve günlükten izleyin.

> **Engelle karşılaşırsanız** ("Sign in to confirm you're not a bot" vb.):
> *Ayarlar → Tarayıcı çerezleri* kısmından giriş yaptığınız tarayıcıyı seçin.
> Uygulama o tarayıcının çerezlerini kullanarak engeli aşar.

---

## Neden bu formatlar? (TV / araç uyumu)

| Hedef | Seçim | Gerekçe |
|-------|-------|---------|
| Video kodek | **H.264 (avc1)** | Donanım çözücü desteği en yaygın kodek. VP9/AV1 birçok TV/araç ünitesinde oynamaz. |
| Ses kodek | **AAC (m4a)** | MP4 ile standart, evrensel destek. (Opus genelde desteklenmez.) |
| Konteyner | **MP4** | USB/araç üniteleri için en güvenli kap. |
| MP3 | **320 kbps + ID3 + kapak** | Araç ekranında sanatçı/parça/kapak gösterimi için. |
| MP4 oynatma | **`+faststart`** | `moov` atomu başta → ileri sarma ve anında oynatma. |
| Dosya adı | **FAT32-güvenli** | Araç USB'leri çoğunlukla FAT32; geçersiz karakterler ayıklanır. |

---

## Mimari

Kod, **iş mantığı** ile **arayüz** kesin biçimde ayrılacak şekilde katmanlıdır
(düşük teknik borç, test edilebilirlik):

```
youtube_downloader/
├── core/                 # UI'dan bağımsız iş mantığı (Qt importu YOK)
│   ├── models.py         # MediaFormat, JobStatus, DownloadJob (domain modelleri)
│   ├── parser.py         # "link | format" satırlarını DownloadJob'lara çevirir (saf fonksiyon)
│   └── downloader.py     # yt-dlp sarmalayıcısı; format seçimi, liste çözümleme, iptal, ilerleme
├── gui/                  # PySide6 sunum katmanı
│   ├── worker.py         # QThread worker — çözümle→indir; iki fazlı, UI'yı dondurmaz
│   ├── theme.py          # Modern açık-mavi tema (tek PALETTE sözlüğü → kolay değiştirilir)
│   └── main_window.py    # Pencere; yalnızca sunum/orkestrasyon
├── resources.py          # Paketlenmiş ffmpeg/ikon bulucu (frozen & kaynak modunda)
└── app.py                # Giriş noktası
packaging/                # .deb ve .exe paketleme
├── youtube-downloader.spec   # PyInstaller (her iki platform)
├── build_linux.sh            # .deb üretir
├── build_windows.bat         # .exe üretir
├── deb/                      # .desktop tanımı
└── assets/icon.svg
.github/workflows/build.yml   # CI: .deb (Ubuntu) + .exe (Windows) otomatik
tests/
└── test_core.py          # Çekirdek mantık testleri (ayrıştırma + format + liste çözümleme)
```

**Tasarım ilkeleri**

- `core` katmanı Qt'ye bağımlı değildir → kolayca test edilir, CLI'a da uyarlanabilir.
- Ayrıştırma **saf** ve yan etkisizdir; geçerli işleri ve satır bazlı hataları ayrı döndürür.
- İndirme **ayrı thread**'de çalışır; UI ile yalnızca Qt sinyalleri üzerinden konuşur.
- İndirme **iptal edilebilir** (`threading.Event` ile güvenli durdurma).
- İndirmeler **sıralıdır** — kullanıcının verdiği sırayı korur ve YouTube'a nazik davranır.

---

## Paketleme (.deb ve .exe)

Uygulama hem **Ubuntu (.deb)** hem **Windows (.exe)** olarak paketlenebilir.
Her ikisi de PyInstaller ile tek dosyalı (onefile) üretilir.

### Ubuntu (.deb)

```bash
packaging/build_linux.sh
# Çıktı: dist/youtube-downloader_1.0.0_amd64.deb
sudo apt install ./dist/youtube-downloader_*.deb
```

- `.deb`, `ffmpeg`'i **bağımlılık** olarak tanımlar (apt otomatik kurar).
- Kurulumdan sonra menüde **YouTube İndirici** görünür; terminalden
  `youtube-downloader` ile de açılır.

### Windows (.exe)

Windows bir makinede (çapraz derleme mümkün değildir):

```bat
packaging\build_windows.bat
:: Çıktı: dist\youtube-downloader.exe
```

- ffmpeg'i kullanıcıya kurdurtmamak için `ffmpeg.exe` ve `ffprobe.exe` dosyalarını
  `packaging\vendor\ffmpeg\` klasörüne koyun; bunlar `.exe` içine gömülür ve
  çalışma anında otomatik kullanılır.

### Otomatik (GitHub Actions)

Bu Linux makinesinde Windows `.exe` üretilemez. En pratik yol CI'dır:
bir `v*` etiketi gönderdiğinizde [.github/workflows/build.yml](.github/workflows/build.yml)
**hem `.deb` hem `.exe`** üretir (Windows için ffmpeg'i otomatik indirip gömer) ve
artefakt olarak yükler.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

## Testler

```bash
.venv/bin/python tests/test_core.py
# veya pytest kuruluysa:
.venv/bin/python -m pytest -q
```

---

## Sık karşılaşılan durumlar

- **`ffmpeg not found`** → `sudo apt install ffmpeg`.
- **Engel / bot doğrulaması** → Tarayıcı çerezlerini seçin (yukarı bakın).
- **Liste verdim ama tek video indi / hiç inmedi** → Oynatma listesi **özel
  (private) veya erişime kapalı** olabilir (YouTube "permission/403" döner). Listeye
  giriş yaptığınız hesapla erişebiliyorsanız, *Ayarlar → Tarayıcı çerezleri*'nden o
  tarayıcıyı seçin; uygulama oturum çerezlerinizle listeyi açar. (Genel/herkese açık
  listeler çerez gerektirmez.)
- **"Requested format is not available" / "No supported JavaScript runtime" /
  bazı formatların eksik gelmesi** → YouTube artık imza/challenge çözümü için bir
  **JavaScript çalışma ortamı** ister; olmadan formatlar (MP3 için gereken m4a ses
  dahil) eksik gelir. Çözüm: **Deno** kurun —
  `curl -fsSL https://deno.land/install.sh | sh` (Node.js kuruluysa o da kullanılır;
  uygulama ikisini de otomatik bulur). Çözücü betikler `yt-dlp-ejs` paketiyle gelir
  (`requirements.txt` içinde), böylece çalışma anında ağdan bir şey indirilmez.
- **yt-dlp eskidi / indirme bozuldu** → YouTube sık değişir; güncel tutun:
  ```bash
  .venv/bin/pip install -U yt-dlp
  ```
- **4K istiyorum** → Kod 1080p ile sınırlı (TV/araç uyumu için). `Ayarlar`'da
  daha düşük seçebilirsiniz; üst sınırı artırmak için `main_window._selected_max_height`
  ve `Downloader.max_height` değerlerini düzenleyin.

---

## Yasal not

Bu araç kişisel kullanım içindir. İndirdiğiniz içeriğin telif hakkı ve
YouTube Hizmet Şartları'na uygunluğundan kullanıcı sorumludur.
