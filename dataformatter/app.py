"""Start the Qt Quick UI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .bridge.backend import Backend
from .bridge.settings import AppSettings

QML_DIR = Path(__file__).resolve().parent / "qml"
CONTROLS_STYLE = "Basic"  # the only built-in style that fully follows our colours


def create_engine(
    backend: Backend,
    settings: AppSettings,
    on_warnings: Callable[[list], None] | None = None,
) -> QQmlApplicationEngine:
    QQuickStyle.setStyle(CONTROLS_STYLE)
    engine = QQmlApplicationEngine()
    if on_warnings is not None:
        engine.warnings.connect(on_warnings)
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("settings", settings)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def run() -> int:
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("dataformatter")
    app.setApplicationName("dataformatter")
    settings = AppSettings()
    backend = Backend(settings=settings)
    engine = create_engine(backend, settings)
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(backend.close)
    return app.exec()
