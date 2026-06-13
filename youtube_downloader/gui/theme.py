"""Modern koyu (dark) tema.

Uygulama geneline tek bir Qt Style Sheet (QSS) uygulanir. Renkler tek yerde
tanimlandigi icin (asagidaki PALETTE) ileride tema degistirmek kolaydir.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Tek kaynak: renk paleti. Yeni tema icin yalnizca bu degerleri degistirin.
# Acik (light) mavi tema — uyumlu gri-mavi notrler.
PALETTE = {
    "bg": "#eef1f6",          # ana arka plan (acik gri-mavi)
    "surface": "#ffffff",     # gruplar / kartlar
    "surface_alt": "#f4f6fa",  # girisler, hucreler
    "border": "#d7dee8",      # kenarliklar
    "text": "#1b2430",        # ana metin (koyu)
    "muted": "#687284",       # ikincil metin
    "accent": "#2563eb",      # vurgu (mavi)
    "accent_hover": "#3b82f6",
    "accent_press": "#1d4ed8",
    "ok": "#16a34a",          # basari
    "selection": "#dbe7fb",   # secim arka plani (acik mavi)
    "progress": "#60a5fa",    # ilerleme dolgusu (koyu yazi okunabilsin diye acik mavi)
}


def _stylesheet() -> str:
    p = PALETTE
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
        font-size: 13px;
        color: {p['text']};
        outline: none;
    }}
    /* Ana arka plan QPalette.Window ile verilir; widget'lara genel bir dolgu
       BOYAMIYORUZ ki etiketler/konteynerler seffaf kalsin (kart uzerinde gri
       leke olusmasin). Etiket ve radyolar acikca seffaf. */
    QLabel, QRadioButton {{ background: transparent; }}

    /* Gruplar (kart görünümü) */
    QGroupBox {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        margin-top: 16px;
        padding: 12px 12px 12px 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 2px 8px;
        color: {p['muted']};
        font-weight: 600;
    }}

    /* Metin girişleri */
    QPlainTextEdit, QLineEdit {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {p['accent']};
        selection-color: #ffffff;
    }}
    QPlainTextEdit:focus, QLineEdit:focus {{ border: 1px solid {p['accent']}; }}
    QPlainTextEdit:read-only {{ color: {p['muted']}; }}

    /* Butonlar */
    QPushButton {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ border: 1px solid {p['accent']}; }}
    QPushButton:pressed {{ background: {p['selection']}; }}
    QPushButton:disabled {{ color: {p['muted']}; border-color: {p['border']}; }}

    /* Vurgulu (birincil) buton: İndir / Yeni İndirme */
    QPushButton#primaryButton {{
        background: {p['accent']};
        border: 1px solid {p['accent']};
        color: #ffffff;
    }}
    QPushButton#primaryButton:hover {{ background: {p['accent_hover']}; border-color: {p['accent_hover']}; }}
    QPushButton#primaryButton:pressed {{ background: {p['accent_press']}; }}
    QPushButton#primaryButton:disabled {{ background: {p['surface_alt']}; border-color: {p['border']}; color: {p['muted']}; }}

    /* Açılır menü */
    QComboBox {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 18px;
    }}
    QComboBox:hover {{ border: 1px solid {p['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {p['muted']};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        selection-background-color: {p['accent']};
        selection-color: #ffffff;
        padding: 4px;
    }}

    /* Radyo düğmeleri */
    QRadioButton {{ spacing: 8px; }}
    QRadioButton::indicator {{
        width: 16px; height: 16px;
        border-radius: 9px;
        border: 2px solid {p['border']};
        background: {p['surface_alt']};
    }}
    QRadioButton::indicator:hover {{ border: 2px solid {p['accent']}; }}
    QRadioButton::indicator:checked {{
        border: 2px solid {p['accent']};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                    fx:0.5, fy:0.5, stop:0 {p['accent']}, stop:0.5 {p['accent']},
                    stop:0.55 {p['surface']});
    }}

    /* İlerleme çubukları */
    QProgressBar {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        text-align: center;
        height: 18px;
        color: {p['text']};
    }}
    QProgressBar::chunk {{
        background: {p['progress']};
        border-radius: 7px;
    }}

    /* Tablo */
    QTableWidget {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        gridline-color: {p['border']};
        selection-background-color: {p['selection']};
        selection-color: {p['text']};
    }}
    QTableWidget::item {{ padding: 4px 6px; }}
    QHeaderView::section {{
        background: {p['surface']};
        color: {p['muted']};
        border: none;
        border-bottom: 1px solid {p['border']};
        padding: 8px 6px;
        font-weight: 600;
    }}
    QTableCornerButton::section {{ background: {p['surface']}; border: none; }}

    /* Kaydırma çubukları (ince, modern) */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {p['border']}; border-radius: 5px; min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: {p['border']}; border-radius: 5px; min-width: 28px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {p['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* İpucu balonları ve mesaj kutuları */
    QToolTip {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    QMessageBox {{ background: {p['surface']}; }}
    """


def apply_theme(app: QApplication) -> None:
    """Modern koyu temayi uygulamaya uygular."""
    app.setStyle("Fusion")  # Tutarli, QSS'e iyi uyan temel.

    # Fusion paletini de koyula (QSS'in kapsamadigi yerler icin emniyet).
    p = PALETTE
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p["bg"]))
    pal.setColor(QPalette.WindowText, QColor(p["text"]))
    pal.setColor(QPalette.Base, QColor(p["surface_alt"]))
    pal.setColor(QPalette.AlternateBase, QColor(p["surface"]))
    pal.setColor(QPalette.Text, QColor(p["text"]))
    pal.setColor(QPalette.Button, QColor(p["surface_alt"]))
    pal.setColor(QPalette.ButtonText, QColor(p["text"]))
    pal.setColor(QPalette.Highlight, QColor(p["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(p["surface"]))
    pal.setColor(QPalette.ToolTipText, QColor(p["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(p["muted"]))
    app.setPalette(pal)

    app.setStyleSheet(_stylesheet())
