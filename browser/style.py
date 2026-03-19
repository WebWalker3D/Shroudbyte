"""Centralized stylesheet for Blade Browser — modern dark theme."""

# Colour palette
BG_DARK = "#111115"        # deepest background
BG_MID = "#18181c"         # panels / toolbar
BG_CARD = "#1f1f25"        # cards, inputs, tab bar
BG_HOVER = "#2a2a32"       # hover states
BG_ACTIVE = "#33333d"      # pressed / active states
BORDER = "#2c2c34"         # subtle borders
BORDER_FOCUS = "#6366f1"   # indigo accent for focus rings
ACCENT = "#6366f1"         # primary accent (indigo)
ACCENT_HOVER = "#818cf8"   # lighter accent on hover
ACCENT_TEXT = "#c7d2fe"    # light accent for text highlights
TEXT = "#e4e4e9"           # primary text
TEXT_DIM = "#9494a3"       # secondary / muted text
TEXT_FAINT = "#5c5c6b"     # placeholder text
GREEN = "#34d399"          # success / complete
RED = "#f87171"            # error / cancel
YELLOW = "#fbbf24"         # warning


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
    padding: 2px 4px;
    font-size: 13px;
}}
QMenuBar::item {{
    padding: 5px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {BG_HOVER};
    color: {TEXT};
}}
QMenu {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 6px 28px 6px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 12px;
}}

/* ── Toolbar / nav bar ───────────────────────────── */
QToolBar {{
    background: {BG_MID};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 6px 10px;
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
    padding: 8px 18px;
    margin: 4px 1px 0px 1px;
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    min-width: 80px;
    max-width: 220px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: {BG_DARK};
    color: {TEXT};
}}
QTabBar::tab:hover:!selected {{
    background: {BG_HOVER};
    color: {TEXT};
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
    color: {TEXT_DIM};
    font-size: 12px;
    border-top: 1px solid {BORDER};
    padding: 2px 8px;
}}

/* ── Progress bar (loading indicator) ────────────── */
QProgressBar {{
    background: {BG_CARD};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
    height: 4px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_HOVER}
    );
    border-radius: 4px;
}}

/* ── Scroll bars ─────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BG_ACTIVE};
    border-radius: 4px;
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
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BG_ACTIVE};
    border-radius: 4px;
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
    border-radius: 6px;
    padding: 5px 8px;
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
        font-size: 15px;
        font-weight: 500;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_DIM};
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
        padding: 8px 16px;
        font-size: 14px;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        border: 2px solid {BORDER};
        border-radius: 20px;
        background: {BG_CARD};
        color: {TEXT};
        selection-background-color: {ACCENT};
        selection-color: white;
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
        background: {BG_DARK};
    }}
"""

BOOKMARK_BTN_STYLE = f"""
    QPushButton {{
        font-size: 18px;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_DIM};
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
        font-size: 18px;
        font-weight: bold;
        min-width: 36px;
        max-width: 36px;
        min-height: 36px;
        max-height: 36px;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: {TEXT_DIM};
    }}
    QPushButton:hover {{
        background: {ACCENT};
        color: white;
    }}
    QPushButton:pressed {{
        background: {ACCENT_HOVER};
    }}
"""

DIALOG_BTN_STYLE = f"""
    QPushButton {{
        padding: 8px 20px;
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
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        background: {ACCENT};
        color: white;
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: #4f46e5;
    }}
"""

DIALOG_BTN_DANGER_STYLE = f"""
    QPushButton {{
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid {RED};
        border-radius: 8px;
        background: transparent;
        color: {RED};
    }}
    QPushButton:hover {{
        background: {RED};
        color: white;
    }}
"""

LIST_WIDGET_STYLE = f"""
    QListWidget {{
        background: {BG_DARK};
        color: {TEXT};
        font-size: 13px;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 6px;
        margin: 2px;
    }}
    QListWidget::item:selected {{
        background: {ACCENT};
        color: white;
    }}
    QListWidget::item:hover:!selected {{
        background: {BG_HOVER};
    }}
"""

SEARCH_INPUT_STYLE = f"""
    QLineEdit {{
        padding: 10px 14px;
        font-size: 14px;
        background: {BG_DARK};
        color: {TEXT};
        border: 2px solid {BORDER};
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
        padding: 8px 12px;
        background: {BG_DARK};
        color: {TEXT};
        border: 2px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
    QSpinBox {{
        padding: 8px 12px;
        background: {BG_DARK};
        color: {TEXT};
        border: 2px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QSpinBox:focus {{ border-color: {ACCENT}; }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 20px; height: 20px;
        border-radius: 4px;
        border: 2px solid {BORDER};
        background: {BG_DARK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    QDialogButtonBox {{ button-layout: 0; }}
"""

ADBLOCK_LABEL_ON_STYLE = f"color: {GREEN}; font-size: 12px; padding: 0 8px;"
ADBLOCK_LABEL_OFF_STYLE = f"color: {TEXT_FAINT}; font-size: 12px; padding: 0 8px;"

COMPLETER_POPUP_STYLE = f"""
    QListView {{
        background: {BG_CARD};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        font-size: 13px;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }}
    QListView::item {{
        padding: 6px 10px;
        border-radius: 6px;
        margin: 1px 2px;
    }}
    QListView::item:selected {{
        background: {ACCENT};
        color: white;
    }}
    QListView::item:hover:!selected {{
        background: {BG_HOVER};
    }}
"""

PASSWORD_DIALOG_STYLE = f"""
    QDialog {{ background: {BG_MID}; color: {TEXT}; }}
    QLabel {{ color: {TEXT_DIM}; font-size: 13px; }}
    QLineEdit {{
        padding: 8px 12px;
        background: {BG_DARK};
        color: {TEXT};
        border: 2px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

PASSWORD_SAVE_BAR_STYLE = f"""
    QFrame {{
        background: {BG_CARD};
        border-bottom: 1px solid {BORDER};
        padding: 6px 12px;
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
        border-radius: 8px;
        padding: 12px;
        margin-top: 8px;
    }}
    QGroupBox::title {{
        color: {ACCENT_TEXT};
        subcontrol-origin: margin;
        padding: 0 6px;
    }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; font-size: 13px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 4px;
        border: 2px solid {BORDER};
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
        padding: 4px 8px;
    }}
    QLineEdit {{
        padding: 6px 10px;
        font-size: 13px;
        background: {BG_DARK};
        color: {TEXT};
        border: 2px solid {BORDER};
        border-radius: 6px;
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
        border-radius: 3px;
        border: 2px solid {BORDER};
        background: {BG_DARK};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""

FIND_BAR_BTN_STYLE = f"""
    QPushButton {{
        padding: 4px 10px;
        font-size: 12px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background: {BG_CARD};
        color: {TEXT};
        min-width: 28px;
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        border-color: {ACCENT};
    }}
"""

SOURCE_EDITOR_STYLE = f"""
    QTextEdit {{
        background: {BG_DARK};
        color: {GREEN};
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
        font-size: 13px;
        border: none;
        padding: 12px;
    }}
"""
