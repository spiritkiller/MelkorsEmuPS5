"""
MelkorS PS5 - Fenerbahçe Laciverti & Sauron Orange Hybrid Theme
Obsidian black, deep Fenerbahçe navy blue (#002147 / #002855 / #003875) styling,
with Sauron burning orange reserved exclusively for the MELKORS PS5 emblem.
"""

import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _base_theme = sys._MEIPASS
elif getattr(sys, "frozen", False):
    _base_theme = os.path.dirname(sys.executable)
else:
    _base_theme = os.path.dirname(__file__)

CHECKMARK_PATH = os.path.join(_base_theme, "checkmark.png").replace("\\", "/")
if not os.path.exists(CHECKMARK_PATH):
    _alt = os.path.join(_base_theme, "gui", "checkmark.png").replace("\\", "/")
    if os.path.exists(_alt):
        CHECKMARK_PATH = _alt

PS5_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #06090e;
    color: #e6edf3;
    font-family: 'Segoe UI', 'Ubuntu', 'Roboto', sans-serif;
}

QWidget {
    color: #c9d1d9;
    font-size: 13px;
}

/* Tab Bar - Deep Navy */
QTabWidget::pane {
    border: 1px solid #152238;
    background-color: #0a0f18;
    border-radius: 8px;
    padding: 10px;
}

QTabBar::tab {
    background: #06090e;
    color: #7a889b;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #0f1826;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00234a, stop:1 #0c1422);
    color: #58a6ff;
    border-top: 2px solid #1f6feb;
    border-left: 1px solid #003875;
    border-right: 1px solid #003875;
}

QTabBar::tab:hover:!selected {
    background: #0e1726;
    color: #b0c4de;
    border-color: #1a2a44;
}

/* Buttons - Fenerbahce Lacivert & Obsidian */
QPushButton {
    background-color: #0d1522;
    color: #f0f6fc;
    border: 1px solid #1c2e4a;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #142136;
    border-color: #1f6feb;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #090e17;
    border-color: #003875;
}

QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002147, stop:1 #003875);
    border: 1px solid #1f6feb;
    color: #ffffff;
    font-weight: bold;
    letter-spacing: 0.5px;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002b5c, stop:1 #004b9e);
    border-color: #58a6ff;
}

QPushButton#primaryBtn:pressed {
    background: #001833;
}

QPushButton#stopBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #800a00, stop:1 #b31000);
    border: 1px solid #ff3300;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#stopBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a60d00, stop:1 #e61900);
}

/* Inputs & ComboBox - Deep Navy Obsidian */
QLineEdit, QComboBox, QSpinBox {
    background-color: #090e17;
    border: 1px solid #182842;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e6edf3;
    font-size: 13px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #1f6feb;
    background-color: #0d1522;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #0d1522;
    border: 1px solid #1f6feb;
    selection-background-color: #002855;
    selection-color: #ffffff;
    color: #f0f6fc;
}

/* Text Editors & Console - Midnight Blue Obsidian */
QTextEdit, QPlainTextEdit {
    background-color: #04070b;
    border: 1px solid #121c2e;
    border-radius: 6px;
    color: #8bb2d9;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #06090e;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #182842;
    min-height: 25px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #1f6feb;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* GroupBox & Frames - Navy Accents */
QGroupBox {
    border: 1px solid #182842;
    border-radius: 8px;
    margin-top: 20px;
    font-weight: bold;
    color: #58a6ff;
    padding: 15px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #0a0f18;
}

/* Sliders - Navy Fill & Handle */
QSlider::groove:horizontal {
    border: 1px solid #182842;
    height: 8px;
    background: #0d1522;
    border-radius: 4px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002147, stop:1 #1f6feb);
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #388bfd;
    border: 2px solid #ffffff;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #79c0ff;
    border-color: #1f6feb;
}

/* Checkbox */
QCheckBox {
    spacing: 10px;
    color: #c9d1d9;
    font-size: 13px;
}

QCheckBox:hover {
    color: #ffffff;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #1f3254;
    background-color: #090e17;
    border-radius: 4px;
}

QCheckBox::indicator:hover {
    border-color: #388bfd;
    background-color: #0d1522;
}

QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border-color: #58a6ff;
    image: url("__CHECKMARK_PATH__");
}

QCheckBox::indicator:checked:hover {
    background-color: #388bfd;
    border-color: #79c0ff;
    image: url("__CHECKMARK_PATH__");
}

/* Lists */
QListWidget {
    background-color: #06090e;
    border: 1px solid #152238;
    border-radius: 6px;
    padding: 5px;
}

QListWidget::item {
    padding: 12px;
    margin: 4px;
    border-radius: 6px;
    background-color: #0c1320;
    border-left: 3px solid #003366;
    color: #f0f6fc;
    font-weight: bold;
    font-size: 14px;
}

QListWidget::item:hover {
    background-color: #111b2d;
    border-left: 3px solid #1f6feb;
}

QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002855, stop:1 #0c1320);
    border-left: 4px solid #58a6ff;
    color: #ffffff;
}
"""

PS5_STYLESHEET = PS5_STYLESHEET.replace("__CHECKMARK_PATH__", CHECKMARK_PATH)
