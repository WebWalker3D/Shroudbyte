"""Download shelf and download handling — Chrome/Firefox-style bottom bar."""

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

from . import style

# File extensions that could execute code
_DANGEROUS_EXTENSIONS = frozenset({
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".wsh",
    ".wsf", ".scr", ".pif", ".com",  # Windows
    ".sh", ".bash", ".zsh", ".fish", ".csh", ".ksh",  # Shell scripts
    ".run", ".bin", ".appimage",  # Linux executables
    ".deb", ".rpm", ".pkg.tar.zst", ".pkg.tar.xz",  # Packages
    ".py", ".pl", ".rb", ".php",  # Scripting languages
    ".jar", ".class",  # Java
})


class DownloadItem(QWidget):
    """Compact widget representing a single download."""

    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self._download = download
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"DownloadItem {{ background: {style.BG_CARD}; border: 1px solid {style.BORDER};"
            f" border-radius: 8px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # File info (name + status stacked)
        info = QVBoxLayout()
        info.setSpacing(1)
        fname = Path(download.downloadFileName()).name
        # Show source domain so user knows where the download came from
        source_page = download.page()
        source_host = ""
        if source_page and source_page.url().host():
            source_host = source_page.url().host()
        self._name_label = QLabel(fname)
        self._name_label.setStyleSheet(
            f"font-weight: 600; font-size: 12px; color: {style.TEXT};"
            f" border: none; background: transparent;"
        )
        self._name_label.setMaximumWidth(200)
        self._name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        tooltip = f"File: {fname}\nFrom: {download.url().toString()}"
        if source_host:
            tooltip += f"\nInitiated by: {source_host}"
        self._name_label.setToolTip(tooltip)

        initial_status = f"from {source_host}" if source_host else "Starting\u2026"
        self._status_label = QLabel(initial_status)
        self._status_label.setStyleSheet(
            f"font-size: 11px; color: {style.TEXT_DIM}; border: none; background: transparent;"
        )
        info.addWidget(self._name_label)
        info.addWidget(self._status_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(100)
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)

        # Buttons
        self._pause_btn = QPushButton("\u23F8")
        self._pause_btn.setToolTip("Pause download")
        self._pause_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 4px; background: transparent;"
            f" color: {style.TEXT_FAINT}; font-size: 14px; min-width: 24px; max-width: 24px;"
            f" min-height: 24px; max-height: 24px; }}"
            f"QPushButton:hover {{ background: {style.BG_HOVER}; color: {style.TEXT}; }}"
        )
        self._pause_btn.clicked.connect(self._toggle_pause)

        self._cancel_btn = QPushButton("\u2715")
        self._cancel_btn.setToolTip("Cancel download")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 4px; background: transparent;"
            f" color: {style.TEXT_FAINT}; font-size: 14px; min-width: 24px; max-width: 24px;"
            f" min-height: 24px; max-height: 24px; }}"
            f"QPushButton:hover {{ background: {style.RED}; color: {style.BG_DARK}; }}"
        )
        self._cancel_btn.clicked.connect(self._cancel)

        self._open_btn = QPushButton("Open")
        self._open_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 6px;"
            f" background: {style.ACCENT}; color: {style.BG_DARK};"
            f" font-size: 11px; font-weight: 600;"
            f" padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {style.ACCENT_HOVER}; }}"
        )
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self._open_file)

        layout.addLayout(info, 1)
        layout.addWidget(self._progress)
        layout.addWidget(self._pause_btn)
        layout.addWidget(self._cancel_btn)
        layout.addWidget(self._open_btn)

        # Warn if file type is potentially dangerous
        fname = download.downloadFileName()
        if any(fname.lower().endswith(ext) for ext in _DANGEROUS_EXTENSIONS):
            self._status_label.setText("\u26A0 Executable file")
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {style.YELLOW}; border: none; background: transparent;"
            )

        download.receivedBytesChanged.connect(self._update_progress)
        download.stateChanged.connect(self._state_changed)

    def _format_size(self, nbytes: int) -> str:
        if nbytes < 1024:
            return f"{nbytes} B"
        elif nbytes < 1024 * 1024:
            return f"{nbytes / 1024:.0f} KB"
        else:
            return f"{nbytes / (1024 * 1024):.1f} MB"

    def _update_progress(self):
        received = self._download.receivedBytes()
        total = self._download.totalBytes()
        if total > 0:
            pct = int(received * 100 / total)
            self._progress.setValue(pct)
            self._status_label.setText(
                f"{self._format_size(received)} / {self._format_size(total)}"
            )
        else:
            self._status_label.setText(f"{self._format_size(received)} downloaded")

    def _state_changed(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._progress.setValue(100)
            self._progress.setVisible(False)
            self._status_label.setText("Complete")
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {style.GREEN}; border: none; background: transparent;"
            )
            self._pause_btn.setVisible(False)
            self._cancel_btn.setVisible(False)
            self._open_btn.setVisible(True)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self._progress.setVisible(False)
            self._status_label.setText("Cancelled")
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {style.TEXT_FAINT}; border: none; background: transparent;"
            )
            self._pause_btn.setVisible(False)
            self._cancel_btn.setVisible(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self._progress.setVisible(False)
            self._status_label.setText("Failed")
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {style.RED}; border: none; background: transparent;"
            )
            self._pause_btn.setVisible(False)
            self._cancel_btn.setVisible(False)

    def _toggle_pause(self):
        if self._download.isPaused():
            self._download.resume()
            self._pause_btn.setText("\u23F8")
            self._pause_btn.setToolTip("Pause download")
        else:
            self._download.pause()
            self._pause_btn.setText("\u25B6")
            self._pause_btn.setToolTip("Resume download")
            self._status_label.setText("Paused")

    def _cancel(self):
        self._download.cancel()

    def _open_file(self):
        path = self._download.downloadDirectory() + "/" + self._download.downloadFileName()
        if not os.path.exists(path):
            return
        name = self._download.downloadFileName()
        if any(name.lower().endswith(ext) for ext in _DANGEROUS_EXTENSIONS):
            reply = QMessageBox.warning(
                self, "Potentially Dangerous File",
                f'"{name}" is an executable file.\n\n'
                "Opening it could harm your computer. Are you sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        subprocess.Popen(
            ["xdg-open", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


class DownloadShelf(QFrame):
    """Bottom shelf showing active/recent downloads, embedded in the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setFixedHeight(68)
        self.setStyleSheet(
            f"DownloadShelf {{"
            f"  background: {style.BG_MID};"
            f"  border-top: 1px solid {style.BORDER};"
            f"}}"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Scrollable horizontal area for download items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(52)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._item_layout = QHBoxLayout(self._container)
        self._item_layout.setContentsMargins(0, 0, 0, 0)
        self._item_layout.setSpacing(6)
        self._item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._container)

        outer.addWidget(scroll, 1)

        # Close shelf button
        close_btn = QPushButton("\u2715")
        close_btn.setToolTip("Close download shelf")
        close_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 6px; background: transparent;"
            f" color: {style.TEXT_FAINT}; font-size: 14px; min-width: 28px; max-width: 28px;"
            f" min-height: 28px; max-height: 28px; }}"
            f"QPushButton:hover {{ background: {style.BG_HOVER}; color: {style.TEXT}; }}"
        )
        close_btn.clicked.connect(lambda: self.setVisible(False))
        outer.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        self._items: list[DownloadItem] = []

    def handle_download(self, download: QWebEngineDownloadRequest):
        """Accept and track a new download."""
        downloads_dir = str(Path.home() / "Downloads")
        download.setDownloadDirectory(downloads_dir)
        download.accept()

        item = DownloadItem(download)
        self._item_layout.insertWidget(0, item)
        self._items.append(item)

        self.setVisible(True)

    def toggle(self):
        """Toggle the shelf visibility."""
        self.setVisible(not self.isVisible())
