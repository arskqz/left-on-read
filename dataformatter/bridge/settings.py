"""User settings exposed to QML as ``settings``: appearance and recent projects.

Stored with QSettings in the per-user config location. Nothing here touches
the network: the backdrops folder is a local directory the user fills.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSettings, QStandardPaths, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices

DEFAULT_BACKGROUND = "#020618"
DEFAULT_HIGHLIGHT = "#01ffff"
MAX_RECENT = 10
BACKDROP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def default_backdrops_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "backdrops"


class AppSettings(QObject):
    appearanceChanged = Signal()
    recentChanged = Signal()
    backdropsChanged = Signal()

    def __init__(
        self,
        store: QSettings | None = None,
        backdrops_dir: Path | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._store = store if store is not None else QSettings()
        self._backdrops_dir = backdrops_dir if backdrops_dir is not None else default_backdrops_dir()
        self._backdrops: list[str] = []
        self._scan_backdrops()

    # -- appearance ----------------------------------------------------------

    def _color(self, key: str, default: str) -> QColor:
        color = QColor(str(self._store.value(key, default)))
        return color if color.isValid() else QColor(default)

    def _background(self) -> QColor:
        return self._color("appearance/background", DEFAULT_BACKGROUND)

    def _highlight(self) -> QColor:
        return self._color("appearance/highlight", DEFAULT_HIGHLIGHT)

    def _backdrop(self) -> str:
        value = str(self._store.value("appearance/backdrop", "") or "")
        if value and not Path(QUrl(value).toLocalFile()).is_file():
            return ""
        return value

    backgroundColor = Property(QColor, _background, notify=appearanceChanged)
    highlightColor = Property(QColor, _highlight, notify=appearanceChanged)
    backdrop = Property(str, _backdrop, notify=appearanceChanged)

    @Slot(QColor)
    def setBackgroundColor(self, color: QColor) -> None:
        self._set("appearance/background", QColor(color).name())

    @Slot(QColor)
    def setHighlightColor(self, color: QColor) -> None:
        self._set("appearance/highlight", QColor(color).name())

    @Slot(str)
    def setBackdrop(self, url: str) -> None:
        self._set("appearance/backdrop", url)

    @Slot()
    def resetAppearance(self) -> None:
        for key in ("appearance/background", "appearance/highlight", "appearance/backdrop"):
            self._store.remove(key)
        self._store.sync()
        self.appearanceChanged.emit()

    def _set(self, key: str, value: str) -> None:
        self._store.setValue(key, value)
        self._store.sync()
        self.appearanceChanged.emit()

    # -- backdrops -----------------------------------------------------------

    def _backdrop_list(self) -> list[str]:
        return self._backdrops

    def _backdrops_folder(self) -> str:
        return str(self._backdrops_dir)

    backdrops = Property("QVariantList", _backdrop_list, notify=backdropsChanged)
    backdropsFolder = Property(str, _backdrops_folder, constant=True)

    @Slot()
    def reloadBackdrops(self) -> None:
        self._scan_backdrops()
        self.backdropsChanged.emit()
        self.appearanceChanged.emit()  # the chosen backdrop may have disappeared

    @Slot()
    def openBackdropsFolder(self) -> None:
        self._backdrops_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._backdrops_dir)))

    def _scan_backdrops(self) -> None:
        folder = self._backdrops_dir
        files = sorted(folder.iterdir()) if folder.is_dir() else []
        self._backdrops = [
            QUrl.fromLocalFile(str(p)).toString()
            for p in files
            if p.is_file() and p.suffix.lower() in BACKDROP_SUFFIXES
        ]

    # -- recent projects -----------------------------------------------------

    def _recent_paths(self) -> list[str]:
        try:
            value = json.loads(str(self._store.value("recent/projects", "[]")))
        except ValueError:
            return []
        return [p for p in value if isinstance(p, str)] if isinstance(value, list) else []

    def _recent(self) -> list[dict]:
        return [
            {"path": p, "name": Path(p).name, "url": QUrl.fromLocalFile(p).toString(), "exists": Path(p).is_file()}
            for p in self._recent_paths()
        ]

    recentProjects = Property("QVariantList", _recent, notify=recentChanged)

    def add_recent(self, path: Path) -> None:
        entry = str(Path(path).resolve())
        paths = [entry] + [p for p in self._recent_paths() if p != entry]
        self._save_recent(paths[:MAX_RECENT])

    @Slot(str)
    def removeRecent(self, path: str) -> None:
        self._save_recent([p for p in self._recent_paths() if p != path])

    def _save_recent(self, paths: list[str]) -> None:
        self._store.setValue("recent/projects", json.dumps(paths))
        self._store.sync()
        self.recentChanged.emit()
