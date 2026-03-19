"""Download manager dialog and download handling."""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

from . import style


class DownloadItem(QWidget):
    """Widget representing a single download."""

    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self._download = download
        self.setStyleSheet(
            f"DownloadItem {{ background: {style.BG_CARD}; border: 1px solid {style.BORDER};"
            f" border-radius: 10px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        self._name_label = QLabel(Path(download.downloadFileName()).name)
        self._name_label.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {style.TEXT}; border: none; background: transparent;"
        )
        self._status_label = QLabel("Starting...")
        self._status_label.setStyleSheet(
            f"font-size: 12px; color: {style.TEXT_DIM}; border: none; background: transparent;"
        )
        info_layout.addWidget(self._name_label)
        info_layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setMaximum(100)
        self._progress.setFixedWidth(180)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        self._cancel_btn.setFixedWidth(70)
        self._cancel_btn.clicked.connect(self._cancel)

        self._open_btn = QPushButton("Open")
        self._open_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        self._open_btn.setFixedWidth(70)
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self._open_file)

        layout.addLayout(info_layout, 1)
        layout.addWidget(self._progress)
        layout.addWidget(self._cancel_btn)
        layout.addWidget(self._open_btn)

        download.receivedBytesChanged.connect(self._update_progress)
        download.stateChanged.connect(self._state_changed)

    def _update_progress(self):
        received = self._download.receivedBytes()
        total = self._download.totalBytes()
        if total > 0:
            pct = int(received * 100 / total)
            self._progress.setValue(pct)
            self._status_label.setText(
                f"{received // 1024} KB / {total // 1024} KB"
            )
        else:
            self._status_label.setText(f"{received // 1024} KB downloaded")

    def _state_changed(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._progress.setValue(100)
            self._status_label.setText("Complete")
            self._status_label.setStyleSheet(
                f"font-size: 12px; color: {style.GREEN}; border: none; background: transparent;"
            )
            self._cancel_btn.setVisible(False)
            self._open_btn.setVisible(True)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self._status_label.setText("Cancelled")
            self._status_label.setStyleSheet(
                f"font-size: 12px; color: {style.TEXT_FAINT}; border: none; background: transparent;"
            )
            self._cancel_btn.setVisible(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self._status_label.setText("Failed")
            self._status_label.setStyleSheet(
                f"font-size: 12px; color: {style.RED}; border: none; background: transparent;"
            )
            self._cancel_btn.setVisible(False)

    def _cancel(self):
        self._download.cancel()

    def _open_file(self):
        path = self._download.downloadDirectory() + "/" + self._download.downloadFileName()
        if os.path.exists(path):
            os.system(f'xdg-open "{path}" &')


class DownloadManager(QDialog):
    """Dialog showing all downloads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setMinimumSize(540, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }}"
        )
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._list_layout.setSpacing(8)
        scroll.setWidget(self._container)

        layout.addWidget(scroll)

        self._items = []

    def handle_download(self, download: QWebEngineDownloadRequest):
        """Accept and track a new download."""
        downloads_dir = str(Path.home() / "Downloads")
        download.setDownloadDirectory(downloads_dir)
        download.accept()

        item = DownloadItem(download)
        self._list_layout.insertWidget(0, item)
        self._items.append(item)
