"""Ana uygulama penceresi (PySide6).

Sorumluluk: kullanici girisini toplamak, isleri olusturmak (core.parser),
cozumleme + indirmeyi bir worker thread'e devretmek ve ilerlemeyi gostermek.
Is mantigi burada DEGIL core katmanindadir; bu pencere yalnizca sunum/orkestrasyon yapar.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __app_name__, __version__
from ..core.downloader import Downloader
from ..core.models import DownloadJob, JobStatus, MediaFormat
from ..core.parser import parse_input
from ..resources import available_js_runtimes
from .theme import apply_theme
from .worker import DownloadWorker

# Tarayici cerezleri secenekleri (bot/yas dogrulamasi engellerini asmak icin).
_COOKIE_BROWSERS = ["Kapalı", "chrome", "firefox", "edge", "brave", "chromium", "opera", "vivaldi"]

# Tablo sutunlari.
_COL_NUM, _COL_NAME, _COL_FORMAT, _COL_STATUS, _COL_PROGRESS = range(5)

_PLACEHOLDER = (
    "Her satıra bir bağlantı yazın. İsterseniz '|' ile format belirtin:\n\n"
    "https://www.youtube.com/watch?v=... | video\n"
    "https://youtu.be/... | mp3\n"
    "https://www.youtube.com/playlist?list=... | mp3   (tüm liste iner)\n"
    "https://www.youtube.com/watch?v=...   (format yoksa varsayılan kullanılır)\n\n"
    "# '#' ile başlayan satırlar yorumdur, atlanır."
)


class MainWindow(QWidget):
    """Uygulamanin tek penceresi."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: DownloadWorker | None = None

        # Calisma durumu.
        self._row_by_id: dict[int, int] = {}     # job_id -> tablo satiri
        self._title_by_id: dict[int, str] = {}   # job_id -> gosterim adi
        self._progress: dict[int, float] = {}    # job_id -> yuzde (0..100)
        self._path_by_row: dict[int, str] = {}   # tablo satiri -> indirilen dosya yolu (cift-tik oynatma)
        self._private_playlists: list[tuple[int, str]] = []  # acilamayan ozel listeler
        self._total = 0
        self._completed = 0
        self._active_text = "—"

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setMinimumSize(960, 740)
        self._build_ui()

    # ------------------------------------------------------------------ #
    # Arayuz kurulumu
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 6)  # alt boşluk kısaldı
        root.setSpacing(10)

        root.addWidget(self._build_header())
        self.input_group = self._build_input_group()
        self.settings_group = self._build_settings_group()
        # Giris gorunumunde artan bos alani Baglantilar kutusu yutar (kuyruk gizliyken).
        root.addWidget(self.input_group, stretch=1)
        root.addWidget(self.settings_group)
        root.addLayout(self._build_action_bar())
        root.addWidget(self._build_status_panel())
        self.queue_group = self._build_queue_table()
        root.addWidget(self.queue_group, stretch=1)  # tum bos alani kuyruk alir
        root.addWidget(self._build_log_view(), stretch=0)  # gunluk kucuk, sabit kalir
        root.addWidget(self._build_footer())

        # Baslangicta kuyruk gizli; "İndir"e basilinca acilir.
        self.queue_group.hide()

    def _build_header(self) -> QWidget:
        header = QLabel(
            f"<b>{__app_name__}</b> — TV ve araç ekranı uyumlu indirme "
            "(Video: MP4/H.264 · Ses: MP3 · Oynatma listeleri desteklenir)"
        )
        header.setTextFormat(Qt.RichText)
        return header

    def _build_input_group(self) -> QWidget:
        group = QGroupBox("Bağlantılar")
        layout = QVBoxLayout(group)
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText(_PLACEHOLDER)
        self.input_edit.setFont(QFont("monospace"))
        self.input_edit.setMinimumHeight(130)
        layout.addWidget(self.input_edit)
        return group

    def _build_settings_group(self) -> QWidget:
        # Kompakt iki sutunlu yerlesim: 5 satir yerine 3 satira sigar.
        group = QGroupBox("Ayarlar")
        grid = QGridLayout(group)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        # Alan sutunlari esnesin; etiket sutunlari dar kalsin.
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        # Varsayilan format (satirda format yoksa kullanilir).
        fmt_box = QHBoxLayout()
        fmt_box.setContentsMargins(0, 0, 0, 0)
        self.radio_video = QRadioButton("Video (MP4)")
        self.radio_mp3 = QRadioButton("Ses (MP3)")
        self.radio_video.setChecked(True)
        fmt_box.addWidget(self.radio_video)
        fmt_box.addWidget(self.radio_mp3)
        fmt_box.addStretch()
        fmt_widget = QWidget()
        fmt_widget.setLayout(fmt_box)

        # Video kalitesi (TV/arac uyumu icin 1080p varsayilan).
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p (önerilen)", "720p", "480p"])

        # MP3 kalitesi.
        self.mp3_combo = QComboBox()
        self.mp3_combo.addItems(["320 kbps (önerilen)", "256 kbps", "192 kbps"])

        # Tarayici cerezleri (engelleri asmak icin).
        self.cookie_combo = QComboBox()
        self.cookie_combo.addItems(_COOKIE_BROWSERS)
        self.cookie_combo.setToolTip(
            "YouTube 'oturum açın' veya yaş doğrulaması istediğinde,\n"
            "seçili tarayıcının çerezlerini kullanarak engeli aşar."
        )

        # Cikti klasoru (tum satiri kaplar).
        out_box = QHBoxLayout()
        out_box.setContentsMargins(0, 0, 0, 0)
        self.output_edit = QLineEdit(self._default_output_dir())
        browse_btn = QPushButton("Gözat…")
        browse_btn.clicked.connect(self._choose_output_dir)
        out_box.addWidget(self.output_edit)
        out_box.addWidget(browse_btn)
        out_widget = QWidget()
        out_widget.setLayout(out_box)

        # Yerlesim: (etiket, alan) ciftleri iki sutun halinde.
        grid.addWidget(QLabel("Varsayılan format:"), 0, 0)
        grid.addWidget(fmt_widget, 0, 1)
        grid.addWidget(QLabel("Maks. video kalitesi:"), 0, 2)
        grid.addWidget(self.quality_combo, 0, 3)

        grid.addWidget(QLabel("MP3 kalitesi:"), 1, 0)
        grid.addWidget(self.mp3_combo, 1, 1)
        grid.addWidget(QLabel("Tarayıcı çerezleri:"), 1, 2)
        grid.addWidget(self.cookie_combo, 1, 3)

        grid.addWidget(QLabel("Kayıt klasörü:"), 2, 0)
        grid.addWidget(out_widget, 2, 1, 1, 3)  # 3 sutun boyunca uzar

        return group

    def _build_action_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.download_btn = QPushButton("⬇  İndir")
        self.download_btn.setObjectName("primaryButton")  # vurgulu (accent) buton
        self.download_btn.setMinimumHeight(40)
        self.download_btn.clicked.connect(self._start_downloads)

        # Indirme bitince gorunur; girisi/ayarlari geri getirir.
        self.new_btn = QPushButton("↩  Yeni İndirme")
        self.new_btn.setObjectName("primaryButton")
        self.new_btn.setMinimumHeight(40)
        self.new_btn.clicked.connect(self._show_input_view)
        self.new_btn.hide()

        self.cancel_btn = QPushButton("⏹  Durdur")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_downloads)

        # Genel ilerleme cubugu (tum ogelerin ortalamasi -> genel yuzde).
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        self.overall_bar.setTextVisible(True)
        self.overall_bar.setFormat("Genel: %p%")

        bar.addWidget(self.download_btn)
        bar.addWidget(self.new_btn)
        bar.addWidget(self.cancel_btn)
        bar.addWidget(self.overall_bar, stretch=1)
        return bar

    def _build_status_panel(self) -> QWidget:
        # Genel yuzde / tamamlanan sayisi / aktif islem bilgisini gosterir.
        self.status_label = QLabel(self._status_text())
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setWordWrap(True)
        return self.status_label

    def _build_queue_table(self) -> QWidget:
        group = QGroupBox("İndirme Kuyruğu  —  oynatmak için satıra çift tıklayın")
        layout = QVBoxLayout(group)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Ad", "Format", "Durum", "İlerleme"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        # Tamamlanmis bir ogeye cift tiklayinca varsayilan oynatici ile ac.
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_NUM, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_FORMAT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)
        return group

    def _build_log_view(self) -> QWidget:
        group = QGroupBox("Günlük")
        # Dikeyde sabit kalsin; artan bos alani yutup buyumesin.
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace"))
        self.log_view.setMaximumBlockCount(2000)  # bellek sismesini onler
        self.log_view.setFixedHeight(90)  # gunluk kucuk tutulur; kuyruk one cikar
        layout.addWidget(self.log_view)
        return group

    def _build_footer(self) -> QWidget:
        # Gelistirici bilgisi ve surum — kucuk, soluk renkli, altta.
        footer = QLabel(
            f"Geliştirici: <b>Kazım Ölmez</b> · "
            f"<a href='mailto:kazimolmez.dev@gmail.com'>kazimolmez.dev@gmail.com</a> · "
            f"Sürüm {__version__}"
        )
        footer.setTextFormat(Qt.RichText)
        footer.setOpenExternalLinks(True)  # mail bağlantısı tıklanabilir
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: gray; font-size: 11px; margin: 0px; padding: 0px;")
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setMaximumHeight(16)  # üst/alt boşluğu kısar
        return footer

    # ------------------------------------------------------------------ #
    # Ayar yardimcilari
    # ------------------------------------------------------------------ #
    @staticmethod
    def _default_output_dir() -> str:
        return os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Kayıt klasörünü seçin", self.output_edit.text() or os.path.expanduser("~")
        )
        if path:
            self.output_edit.setText(path)

    def _selected_default_format(self) -> MediaFormat:
        return MediaFormat.VIDEO if self.radio_video.isChecked() else MediaFormat.MP3

    def _selected_max_height(self) -> int:
        return {0: 1080, 1: 720, 2: 480}[self.quality_combo.currentIndex()]

    def _selected_mp3_quality(self) -> str:
        return {0: "320", 1: "256", 2: "192"}[self.mp3_combo.currentIndex()]

    def _selected_cookie_browser(self) -> str | None:
        value = self.cookie_combo.currentText()
        return None if value == "Kapalı" else value

    # ------------------------------------------------------------------ #
    # Indirme akisi
    # ------------------------------------------------------------------ #
    def _start_downloads(self) -> None:
        if self._thread is not None:
            return  # zaten calisiyor

        result = parse_input(self.input_edit.toPlainText(), self._selected_default_format())

        if result.errors:
            details = "\n".join(
                f"  • Satır {e.line_number}: {e.reason}  →  {e.raw.strip()}"
                for e in result.errors
            )
            QMessageBox.warning(self, "Hatalı satırlar", f"Bazı satırlar atlanacak:\n\n{details}")

        if not result.jobs:
            QMessageBox.information(
                self, "İndirilecek bir şey yok", "Geçerli en az bir bağlantı girin."
            )
            return

        # YouTube artik format cozumu icin bir JS calisma ortami ister; yoksa
        # formatlar eksik gelir ("Requested format is not available").
        if not available_js_runtimes():
            proceed = QMessageBox.warning(
                self,
                "JavaScript çalışma ortamı bulunamadı",
                "Sistemde Deno/Node bulunamadı. YouTube, formatları çözmek için bir "
                "JavaScript çalışma ortamı ister; olmadan indirme büyük olasılıkla "
                "“Requested format is not available” hatası verir.\n\n"
                "Önerilen çözüm — Deno kurun:\n"
                "    curl -fsSL https://deno.land/install.sh | sh\n\n"
                "Yine de denemek istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if proceed != QMessageBox.Yes:
                return

        output_dir = self.output_edit.text().strip() or self._default_output_dir()
        downloader = Downloader(
            output_dir=output_dir,
            max_height=self._selected_max_height(),
            mp3_quality=self._selected_mp3_quality(),
            cookies_from_browser=self._selected_cookie_browser(),
        )

        self._reset_run_state()
        self._show_download_view()
        self._set_running(True)
        self._active_text = "Çözümleniyor…"
        self._refresh_status()

        # Worker'i ayri bir thread'de calistir.
        self._thread = QThread(self)
        self._worker = DownloadWorker(result.jobs, downloader)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.resolving.connect(self._on_resolving)
        self._worker.jobs_added.connect(self._on_jobs_added)
        self._worker.private_playlist.connect(self._on_private_playlist)
        self._worker.resolve_done.connect(self._on_resolve_done)
        self._worker.progress.connect(self._on_progress)
        self._worker.job_done.connect(self._on_job_done)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_all_finished)
        self._thread.start()

    def _cancel_downloads(self) -> None:
        if self._worker is not None:
            self.cancel_btn.setEnabled(False)
            self._append_log("⏹ Durdurma isteği gönderildi (mevcut indirme bitince durur)…")
            self._worker.cancel()

    def _reset_run_state(self) -> None:
        self.table.setRowCount(0)
        self._row_by_id.clear()
        self._title_by_id.clear()
        self._progress.clear()
        self._path_by_row.clear()
        self._private_playlists.clear()
        self._total = 0
        self._completed = 0
        self._active_text = "—"
        self.overall_bar.setValue(0)

    # ------------------------------------------------------------------ #
    # Cozumleme fazi sinyalleri
    # ------------------------------------------------------------------ #
    def _on_resolving(self, line_number: int) -> None:
        self._active_text = f"Çözümleniyor: satır {line_number}…"
        self._refresh_status()

    def _on_jobs_added(self, jobs: list[DownloadJob]) -> None:
        """Cozumlenen ogeleri tabloya satir olarak ekler (adlariyla birlikte)."""
        for job in jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_by_id[job.job_id] = row
            self._title_by_id[job.job_id] = job.display_name
            self._progress[job.job_id] = 0.0

            num_item = QTableWidgetItem(str(row + 1))
            name_item = QTableWidgetItem(job.display_name)
            tooltip = job.url
            if job.playlist_title:
                tooltip = f"Liste: {job.playlist_title}\n{job.url}"
            name_item.setToolTip(tooltip)

            self.table.setItem(row, _COL_NUM, num_item)
            self.table.setItem(row, _COL_NAME, name_item)
            self.table.setItem(row, _COL_FORMAT, QTableWidgetItem(job.media_format.label))
            self.table.setItem(row, _COL_STATUS, QTableWidgetItem(JobStatus.PENDING.value))

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            self.table.setCellWidget(row, _COL_PROGRESS, bar)

    def _on_private_playlist(self, line_number: int, url: str) -> None:
        """Acilamayan (ozel/erisime kapali) liste tespit edildi — biriktir."""
        self._private_playlists.append((line_number, url))

    def _on_resolve_done(self, total: int) -> None:
        self._total = total
        self._append_log(f"≡ Çözümleme bitti: toplam {total} öğe sıraya alındı.")
        self._refresh_status()
        if self._private_playlists:
            self._warn_private_playlists()

    def _warn_private_playlists(self) -> None:
        """Gizli/erisime kapali listeler icin belirgin bir uyari penceresi gosterir."""
        lines = "\n".join(f"  • Satır {ln}: {url}" for ln, url in self._private_playlists)
        QMessageBox.warning(
            self,
            "Gizli / erişime kapalı liste",
            "Aşağıdaki oynatma liste(ler)i açılamadı — büyük olasılıkla "
            "<b>gizli (private) veya erişime kapalı</b>:\n\n"
            f"{lines}\n\n"
            "Listeye giriş yaptığınız bir hesapla erişebiliyorsanız, "
            "<b>Ayarlar → “Tarayıcı çerezleri”</b> kısmından o tarayıcıyı seçip "
            "tekrar deneyin. (Herkese açık listeler çerez gerektirmez.)",
        )

    # ------------------------------------------------------------------ #
    # Indirme fazi sinyalleri
    # ------------------------------------------------------------------ #
    def _on_progress(self, job_id: int, percent: float, status: str) -> None:
        row = self._row_by_id.get(job_id)
        if row is None:
            return
        self.table.item(row, _COL_STATUS).setText(status)
        bar = self.table.cellWidget(row, _COL_PROGRESS)
        if isinstance(bar, QProgressBar):
            bar.setValue(int(percent))

        self._progress[job_id] = percent
        title = self._title_by_id.get(job_id, "")
        self._active_text = f"▶ {title} — %{percent:.0f} ({status})"
        self._refresh_status()

    def _on_job_done(self, job_id: int, success: bool, message: str) -> None:
        row = self._row_by_id.get(job_id)
        if row is not None:
            status = JobStatus.DONE.value if success else JobStatus.ERROR.value
            item = self.table.item(row, _COL_STATUS)
            item.setText(status)
            if success:
                # message = indirilen dosya yolu -> cift-tik ile oynatma icin sakla.
                self._path_by_row[row] = message
                name_item = self.table.item(row, _COL_NAME)
                if name_item is not None:
                    name_item.setToolTip(f"Oynatmak için çift tıklayın:\n{message}")
            elif message != "İptal edildi":
                item.setToolTip(message)
            bar = self.table.cellWidget(row, _COL_PROGRESS)
            if isinstance(bar, QProgressBar) and success:
                bar.setValue(100)

        self._progress[job_id] = 100.0 if success else self._progress.get(job_id, 0.0)
        self._completed += 1
        self._refresh_status()

    def _on_all_finished(self, success: int, total: int) -> None:
        self._append_log(f"✔ Bitti: {success}/{total} öğe başarıyla indirildi.")
        self._active_text = "Tamamlandı"
        self._refresh_status()
        self._teardown_thread()
        self._set_running(False)
        # Kuyruk gorunur kalir (sonuclari gostermek icin); geri donmek icin dugme cikar.
        self.new_btn.show()
        if total:
            QMessageBox.information(
                self, "Tamamlandı", f"{success}/{total} öğe başarıyla indirildi."
            )

    # ------------------------------------------------------------------ #
    # Durum gostergesi
    # ------------------------------------------------------------------ #
    def _overall_percent(self) -> float:
        """Tum ogelerin ortalama ilerlemesi -> genel yuzde."""
        if not self._total:
            return 0.0
        return sum(self._progress.values()) / self._total

    def _refresh_status(self) -> None:
        self.overall_bar.setValue(int(self._overall_percent()))
        self.status_label.setText(self._status_text())

    def _status_text(self) -> str:
        overall = self._overall_percent()
        return (
            f"<b>Genel:</b> %{overall:.0f}  ·  "
            f"<b>Tamamlanan:</b> {self._completed}/{self._total}  ·  "
            f"<b>Aktif:</b> {self._active_text}"
        )

    # ------------------------------------------------------------------ #
    # Thread/pencere yonetimi
    # ------------------------------------------------------------------ #
    def _teardown_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        """Tamamlanmis bir satira cift tiklayinca dosyayi varsayilan oynatici ile acar."""
        path = self._path_by_row.get(row)
        if not path:
            self._append_log("⚠ Bu öğe henüz indirilmedi (oynatmak için tamamlanmasını bekleyin).")
            return
        if not os.path.exists(path):
            self._append_log(f"⚠ Dosya bulunamadı: {path}")
            return
        # QDesktopServices, platformun varsayilan medya oynaticisini kullanir
        # (Linux: xdg-open, Windows: ilişkili uygulama, macOS: open).
        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self._append_log(f"▶ Oynatılıyor: {path}")
        else:
            self._append_log(f"⚠ Oynatıcı açılamadı: {path}")

    def _show_download_view(self) -> None:
        """Indirmeye gecis: giris+ayarlar gizlenir, kuyruk genis sekilde acilir."""
        self.input_group.hide()
        self.settings_group.hide()
        self.download_btn.hide()
        self.new_btn.hide()
        self.queue_group.show()

    def _show_input_view(self) -> None:
        """Giris gorunumune don: kuyruk gizlenir, baglantilar+ayarlar geri gelir."""
        self.queue_group.hide()
        self.new_btn.hide()
        self.input_group.show()
        self.settings_group.show()
        self.download_btn.show()

    def _set_running(self, running: bool) -> None:
        self.download_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.input_edit.setReadOnly(running)

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt imzasi
        if self._thread is not None:
            reply = QMessageBox.question(
                self,
                "İndirme sürüyor",
                "İndirme devam ediyor. Yine de çıkmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            if self._worker is not None:
                self._worker.cancel()
            self._teardown_thread()
        event.accept()


def run() -> int:
    """Uygulamayi baslatir ve cikis kodunu dondurur."""
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    apply_theme(app)  # modern koyu tema
    window = MainWindow()
    window.show()
    return app.exec()
