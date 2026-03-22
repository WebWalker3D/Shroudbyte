"""Centralized stylesheet for Shroudbyte — Forged Dark theme."""

# ── Colour palette — warm, premium dark ──────────────────────────
BG_DARK = "#0c0b10"        # deepest background — warm near-black
BG_MID = "#14131a"          # panels / toolbar / tab bar
BG_CARD = "#1c1b24"         # cards, inputs, surfaces
BG_HOVER = "#262430"        # hover states
BG_ACTIVE = "#302e3b"       # pressed / active states
BORDER = "#282633"          # subtle warm borders
BORDER_FOCUS = "#cd8d6a"    # copper accent for focus rings
ACCENT = "#cd8d6a"          # primary accent — warm copper
ACCENT_HOVER = "#dba888"    # lighter copper on hover
ACCENT_TEXT = "#e8c8b0"     # light copper for text highlights
TEXT = "#ede8e3"            # primary text — warm off-white
TEXT_DIM = "#8a8494"        # secondary / muted text
TEXT_FAINT = "#5a5568"      # placeholder text
GREEN = "#7db88f"           # success — sage green
RED = "#d96b6b"             # error — muted warm red
YELLOW = "#d4a857"          # warning — warm gold


GLOBAL_STYLESHEET = f"""
/* ── Main window ─────────────────────────────────── */
QMainWindow {{
    background: {BG_DARK};
}}

/* ── Menu bar ────────────────────────────────────── */
QMenuBar {{
    background: {BG_MID};
    color: {TEXT_DIM};
    border-bottom: 1px solid {BORDER};
    padding: 2px 6px;
    font-size: 13px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background: {BG_HOVER};
    color: {TEXT};
}}
QMenu {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 0px;
}}
QMenu::item {{
    padding: 8px 32px 8px 18px;
    border-radius: 6px;
    margin: 2px 6px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: {BG_DARK};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 14px;
}}

/* ── Toolbar / nav bar ───────────────────────────── */
QToolBar {{
    background: {BG_MID};
    border: none;
    spacing: 4px;
    padding: 8px 12px;
}}

/* ── Tab bar ─────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: {BG_DARK};
}}
QTabBar {{
    background: {BG_MID};
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    padding: 10px 22px;
    margin: 0;
    background: transparent;
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
    max-width: 220px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom-color: {ACCENT};
    background: transparent;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_DIM};
    background: #1a1923;
}}
QTabBar::close-button {{
    image: none;
    subcontrol-position: right;
    padding: 2px;
    border-radius: 4px;
}}
QTabBar::close-button:hover {{
    background: {RED};
}}

/* ── Status bar ──────────────────────────────────── */
QStatusBar {{
    background: {BG_MID};
    color: {TEXT_FAINT};
    font-size: 11px;
    border-top: 1px solid {BORDER};
    padding: 3px 10px;
}}

/* ── Progress bar (loading indicator) ────────────── */
QProgressBar {{
    background: {BG_DARK};
    border: none;
    border-radius: 0px;
    text-align: center;
    color: transparent;
    max-height: 3px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_HOVER}
    );
    border-radius: 0px;
}}

/* ── Scroll bars ─────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BG_ACTIVE};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_FAINT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BG_ACTIVE};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_FAINT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Tooltips ────────────────────────────────────── */
QToolTip {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── Generic dialog styling ──────────────────────── */
QDialog {{
    background: {BG_MID};
    color: {TEXT};
}}
QLabel {{
    color: {TEXT};
}}
"""


# ── Component-level styles used in code ──────────────────────

NAV_BTN_STYLE = f"""
    QPushButton {{
        font-size: 14px;
        font-weight: 500;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_FAINT};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        color: {TEXT};
    }}
    QPushButton:pressed {{
        background: {BG_ACTIVE};
    }}
"""

URL_BAR_STYLE = f"""
    QLineEdit {{
        padding: 9px 18px;
        font-size: 14px;
        font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
        border: 1px solid {BORDER};
        border-radius: 10px;
        background: {BG_CARD};
        color: {TEXT};
        selection-background-color: {ACCENT};
        selection-color: {BG_DARK};
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
        background: {BG_DARK};
    }}
"""

BOOKMARK_BTN_STYLE = f"""
    QPushButton {{
        font-size: 17px;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_FAINT};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        color: {YELLOW};
    }}
    QPushButton:pressed {{
        background: {BG_ACTIVE};
    }}
"""

NEW_TAB_BTN_STYLE = f"""
    QPushButton {{
        font-size: 17px;
        font-weight: bold;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_FAINT};
    }}
    QPushButton:hover {{
        background: {ACCENT};
        color: {BG_DARK};
    }}
    QPushButton:pressed {{
        background: {ACCENT_HOVER};
    }}
"""

READER_BTN_ACTIVE_STYLE = f"""
    QPushButton {{
        font-size: 13px;
        font-weight: 600;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        border: none;
        border-radius: 8px;
        background: {ACCENT};
        color: {BG_DARK};
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: #b87a5a;
    }}
"""

DIALOG_BTN_STYLE = f"""
    QPushButton {{
        padding: 9px 22px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid {BORDER};
        border-radius: 8px;
        background: {BG_CARD};
        color: {TEXT};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        border-color: {ACCENT};
    }}
    QPushButton:pressed {{
        background: {BG_ACTIVE};
    }}
"""

DIALOG_BTN_PRIMARY_STYLE = f"""
    QPushButton {{
        padding: 9px 22px;
        font-size: 13px;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        background: {ACCENT};
        color: {BG_DARK};
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: #b87a5a;
    }}
"""

DIALOG_BTN_DANGER_STYLE = f"""
    QPushButton {{
        padding: 9px 22px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid {RED};
        border-radius: 8px;
        background: transparent;
        color: {RED};
    }}
    QPushButton:hover {{
        background: {RED};
        color: {BG_DARK};
    }}
"""

LIST_WIDGET_STYLE = f"""
    QListWidget {{
        background: {BG_DARK};
        color: {TEXT};
        font-size: 13px;
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 14px;
        border-radius: 6px;
        margin: 2px;
    }}
    QListWidget::item:selected {{
        background: {ACCENT};
        color: {BG_DARK};
    }}
    QListWidget::item:hover:!selected {{
        background: {BG_HOVER};
    }}
"""

SEARCH_INPUT_STYLE = f"""
    QLineEdit {{
        padding: 10px 16px;
        font-size: 14px;
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
    }}
"""

SETTINGS_FORM_STYLE = f"""
    QDialog {{ background: {BG_MID}; color: {TEXT}; }}
    QLabel {{ color: {TEXT_DIM}; font-size: 13px; }}
    QLineEdit {{
        padding: 9px 14px;
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
    QSpinBox {{
        padding: 9px 14px;
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QSpinBox:focus {{ border-color: {ACCENT}; }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 20px; height: 20px;
        border-radius: 5px;
        border: 1px solid {BORDER};
        background: {BG_DARK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    QDialogButtonBox {{ button-layout: 0; }}
"""

ADBLOCK_LABEL_ON_STYLE = f"color: {GREEN}; font-size: 11px; padding: 0 8px;"
ADBLOCK_LABEL_OFF_STYLE = f"color: {TEXT_FAINT}; font-size: 11px; padding: 0 8px;"

COMPLETER_POPUP_STYLE = f"""
    QListView {{
        background: {BG_CARD};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 4px;
        outline: none;
        font-size: 13px;
        font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    }}
    QListView::item {{
        padding: 7px 12px;
        border-radius: 6px;
        margin: 1px 2px;
    }}
    QListView::item:selected {{
        background: {ACCENT};
        color: {BG_DARK};
    }}
    QListView::item:hover:!selected {{
        background: {BG_HOVER};
    }}
"""

PASSWORD_DIALOG_STYLE = f"""
    QDialog {{ background: {BG_MID}; color: {TEXT}; }}
    QLabel {{ color: {TEXT_DIM}; font-size: 13px; }}
    QLineEdit {{
        padding: 9px 14px;
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

PASSWORD_SAVE_BAR_STYLE = f"""
    QFrame {{
        background: {BG_CARD};
        border-bottom: 1px solid {BORDER};
        padding: 6px 14px;
    }}
    QLabel {{
        color: {TEXT};
        font-size: 13px;
    }}
"""

FILTER_LIST_STYLE = f"""
    QDialog {{ background: {BG_MID}; color: {TEXT}; }}
    QLabel {{ color: {TEXT}; }}
    QGroupBox {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 14px;
        margin-top: 8px;
    }}
    QGroupBox::title {{
        color: {ACCENT_TEXT};
        subcontrol-origin: margin;
        padding: 0 8px;
    }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; font-size: 13px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 5px;
        border: 1px solid {BORDER};
        background: {BG_DARK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""

FIND_BAR_STYLE = f"""
    QFrame {{
        background: {BG_MID};
        border-top: 1px solid {BORDER};
        padding: 5px 10px;
    }}
    QLineEdit {{
        padding: 7px 12px;
        font-size: 13px;
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        min-width: 220px;
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
    }}
    QLabel {{
        color: {TEXT_DIM};
        font-size: 12px;
        padding: 0 4px;
    }}
    QCheckBox {{
        color: {TEXT_DIM};
        font-size: 12px;
        spacing: 4px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border-radius: 4px;
        border: 1px solid {BORDER};
        background: {BG_DARK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""

FIND_BAR_BTN_STYLE = f"""
    QPushButton {{
        padding: 5px 12px;
        font-size: 12px;
        border: 1px solid {BORDER};
        border-radius: 6px;
        background: {BG_CARD};
        color: {TEXT};
        min-width: 28px;
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        border-color: {ACCENT};
    }}
"""

TOAST_STYLE = f"""
    QFrame {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
"""

SOURCE_EDITOR_STYLE = f"""
    QTextEdit {{
        background: {BG_DARK};
        color: {GREEN};
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
        font-size: 13px;
        border: none;
        padding: 14px;
    }}
"""
