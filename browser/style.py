"""Centralized stylesheet for Shroudbyte — theme support (dark / light)."""

# ── Palettes ─────────────────────────────────────────────────────
_DARK = {
    "BG_DARK":       "#0c0b10",
    "BG_MID":        "#14131a",
    "BG_CARD":       "#1c1b24",
    "BG_HOVER":      "#262430",
    "BG_ACTIVE":     "#302e3b",
    "BORDER":        "#282633",
    "BORDER_FOCUS":  "#cd8d6a",
    "ACCENT":        "#cd8d6a",
    "ACCENT_HOVER":  "#dba888",
    "ACCENT_TEXT":   "#e8c8b0",
    "TEXT":          "#ede8e3",
    "TEXT_DIM":      "#8a8494",
    "TEXT_FAINT":    "#5a5568",
    "GREEN":         "#7db88f",
    "RED":           "#d96b6b",
    "YELLOW":        "#d4a857",
    "TAB_HOVER_BG":  "#1a1923",
    "ACCENT_ALPHA":  "rgba(205, 141, 106, 0.06)",
}

_LIGHT = {
    "BG_DARK":       "#f0eeeb",
    "BG_MID":        "#ffffff",
    "BG_CARD":       "#f7f5f2",
    "BG_HOVER":      "#ece9e4",
    "BG_ACTIVE":     "#e2ded8",
    "BORDER":        "#ddd8d0",
    "BORDER_FOCUS":  "#b87a5a",
    "ACCENT":        "#b87a5a",
    "ACCENT_HOVER":  "#a06840",
    "ACCENT_TEXT":   "#8b5e3c",
    "TEXT":          "#2c2520",
    "TEXT_DIM":      "#6b6460",
    "TEXT_FAINT":    "#9a948e",
    "GREEN":         "#3a8a52",
    "RED":           "#c04040",
    "YELLOW":        "#b08930",
    "TAB_HOVER_BG":  "#f0ede8",
    "ACCENT_ALPHA":  "rgba(184, 122, 90, 0.08)",
}

# WCAG-AAA-leaning palette: pure black/white, saturated focus colors,
# heavy borders so every interactive element has a visible boundary.
_HIGH_CONTRAST = {
    "BG_DARK":       "#000000",
    "BG_MID":        "#000000",
    "BG_CARD":       "#0a0a0a",
    "BG_HOVER":      "#1f1f1f",
    "BG_ACTIVE":     "#333333",
    "BORDER":        "#ffffff",
    "BORDER_FOCUS":  "#ffff00",
    "ACCENT":        "#ffff00",
    "ACCENT_HOVER":  "#ffea00",
    "ACCENT_TEXT":   "#ffff00",
    "TEXT":          "#ffffff",
    "TEXT_DIM":      "#e0e0e0",
    "TEXT_FAINT":    "#bdbdbd",
    "GREEN":         "#00ff7f",
    "RED":           "#ff5252",
    "YELLOW":        "#ffd600",
    "TAB_HOVER_BG":  "#1f1f1f",
    "ACCENT_ALPHA":  "rgba(255, 255, 0, 0.18)",
}


# Theme can be "dark", "light", or "high_contrast". _is_dark is kept as
# a back-compat alias for older call sites that just check truthiness.
_theme = "dark"
_is_dark = True

# ── Module-level colour exports (updated by set_dark_mode) ──────
BG_DARK = _DARK["BG_DARK"]
BG_MID = _DARK["BG_MID"]
BG_CARD = _DARK["BG_CARD"]
BG_HOVER = _DARK["BG_HOVER"]
BG_ACTIVE = _DARK["BG_ACTIVE"]
BORDER = _DARK["BORDER"]
BORDER_FOCUS = _DARK["BORDER_FOCUS"]
ACCENT = _DARK["ACCENT"]
ACCENT_HOVER = _DARK["ACCENT_HOVER"]
ACCENT_TEXT = _DARK["ACCENT_TEXT"]
TEXT = _DARK["TEXT"]
TEXT_DIM = _DARK["TEXT_DIM"]
TEXT_FAINT = _DARK["TEXT_FAINT"]
GREEN = _DARK["GREEN"]
RED = _DARK["RED"]
YELLOW = _DARK["YELLOW"]
TAB_HOVER_BG = _DARK["TAB_HOVER_BG"]
ACCENT_ALPHA = _DARK["ACCENT_ALPHA"]


# ── Theme switching ──────────────────────────────────────────────

def is_dark_mode():
    return _is_dark


def get_theme() -> str:
    """Return the active theme name: 'dark', 'light', or 'high_contrast'."""
    return _theme


_PALETTES = {
    "dark":          _DARK,
    "light":         _LIGHT,
    "high_contrast": _HIGH_CONTRAST,
}


def set_theme(name: str):
    """Switch palette by name and rebuild every stylesheet string."""
    global _theme, _is_dark
    palette = _PALETTES.get(name)
    if palette is None:
        # Unknown theme — fall back to dark rather than break.
        name = "dark"
        palette = _DARK
    _theme = name
    _is_dark = name != "light"  # high-contrast counts as a dark-ish theme
    g = globals()
    for key, val in palette.items():
        g[key] = val
    _rebuild()


def set_dark_mode(enabled):
    """Back-compat: legacy bool API for callers that haven't migrated."""
    set_theme("dark" if enabled else "light")


# ── Stylesheet builders (read current module globals) ────────────

def _rebuild():
    """Regenerate all stylesheet module globals from current colours."""
    g = globals()
    g["GLOBAL_STYLESHEET"] = _build_global()
    g["NAV_BTN_STYLE"] = _build_nav_btn()
    g["URL_BAR_STYLE"] = _build_url_bar()
    g["BOOKMARK_BTN_STYLE"] = _build_bookmark_btn()
    g["NEW_TAB_BTN_STYLE"] = _build_new_tab_btn()
    g["READER_BTN_ACTIVE_STYLE"] = _build_reader_btn_active()
    g["DIALOG_BTN_STYLE"] = _build_dialog_btn()
    g["DIALOG_BTN_PRIMARY_STYLE"] = _build_dialog_btn_primary()
    g["DIALOG_BTN_DANGER_STYLE"] = _build_dialog_btn_danger()
    g["LIST_WIDGET_STYLE"] = _build_list_widget()
    g["SEARCH_INPUT_STYLE"] = _build_search_input()
    g["SETTINGS_FORM_STYLE"] = _build_settings_form()
    g["WATCH_LABEL_STYLE"] = _build_watch_label()
    g["ADBLOCK_LABEL_ON_STYLE"] = _build_adblock_label_on()
    g["ADBLOCK_LABEL_OFF_STYLE"] = _build_adblock_label_off()
    g["COMPLETER_POPUP_STYLE"] = _build_completer_popup()
    g["PASSWORD_DIALOG_STYLE"] = _build_password_dialog()
    g["PASSWORD_SAVE_BAR_STYLE"] = _build_password_save_bar()
    g["FILTER_LIST_STYLE"] = _build_filter_list()
    g["FIND_BAR_STYLE"] = _build_find_bar()
    g["FIND_BAR_BTN_STYLE"] = _build_find_bar_btn()
    g["TOAST_STYLE"] = _build_toast()
    g["SOURCE_EDITOR_STYLE"] = _build_source_editor()
    g["PRIVACY_PANEL_STYLE"] = _build_privacy_panel()
    g["PRIVACY_SECTION_HEADER"] = _build_privacy_section_header()
    g["PRIVACY_SECTION_BOX"] = _build_privacy_section_box()
    g["PRIVACY_ROW_BTN"] = _build_privacy_row_btn()
    g["PRIVACY_ROW_BTN_DANGER"] = _build_privacy_row_btn_danger()


def _build_global():
    return f"""
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
    background: {TAB_HOVER_BG};
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


# ── Component-level styles ───────────────────────────────────────

def _build_nav_btn():
    return f"""
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


def _build_url_bar():
    return f"""
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


def _build_bookmark_btn():
    return f"""
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


def _build_new_tab_btn():
    return f"""
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


def _build_reader_btn_active():
    return f"""
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


def _build_dialog_btn():
    return f"""
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


def _build_dialog_btn_primary():
    return f"""
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


def _build_dialog_btn_danger():
    return f"""
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


def _build_list_widget():
    return f"""
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


def _build_search_input():
    return f"""
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


def _build_settings_form():
    return f"""
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


def _build_watch_label():
    return (
        f"QPushButton {{ color: {ACCENT_TEXT}; font-size: 11px; padding: 0 8px; "
        f"border: none; background: transparent; }}"
        f"QPushButton:hover {{ color: {TEXT}; }}"
    )


def _build_adblock_label_on():
    return (
        f"QPushButton {{ color: {GREEN}; font-size: 11px; padding: 0 8px; "
        f"border: none; background: transparent; }}"
        f"QPushButton:hover {{ color: {ACCENT_TEXT}; }}"
    )


def _build_adblock_label_off():
    return (
        f"QPushButton {{ color: {TEXT_FAINT}; font-size: 11px; padding: 0 8px; "
        f"border: none; background: transparent; }}"
        f"QPushButton:hover {{ color: {TEXT_DIM}; }}"
    )


def _build_completer_popup():
    return f"""
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


def _build_password_dialog():
    return f"""
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


def _build_password_save_bar():
    return f"""
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


def _build_filter_list():
    return f"""
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


def _build_find_bar():
    return f"""
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


def _build_find_bar_btn():
    return f"""
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


def _build_toast():
    return f"""
    QFrame {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
"""


def _build_source_editor():
    return f"""
    QTextEdit {{
        background: {BG_DARK};
        color: {GREEN};
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
        font-size: 13px;
        border: none;
        padding: 14px;
    }}
"""


def _build_privacy_panel():
    return f"""
    QDialog {{
        background: {BG_MID};
        color: {TEXT};
    }}
    QLabel {{
        color: {TEXT};
    }}
    QScrollArea {{
        background: {BG_MID};
        border: none;
    }}
"""


def _build_privacy_section_header():
    return f"""
    color: {ACCENT_TEXT};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 8px 0 4px 0;
"""


def _build_privacy_section_box():
    return f"""
    QFrame {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 2px;
    }}
"""


def _build_privacy_row_btn():
    return f"""
    QPushButton {{
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 500;
        border: 1px solid {BORDER};
        border-radius: 5px;
        background: {BG_MID};
        color: {TEXT_DIM};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        border-color: {ACCENT};
        color: {TEXT};
    }}
"""


def _build_privacy_row_btn_danger():
    return f"""
    QPushButton {{
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 500;
        border: 1px solid {RED};
        border-radius: 5px;
        background: transparent;
        color: {RED};
    }}
    QPushButton:hover {{
        background: {RED};
        color: {BG_DARK};
    }}
"""


# ── Initialise stylesheet globals ────────────────────────────────
_rebuild()
