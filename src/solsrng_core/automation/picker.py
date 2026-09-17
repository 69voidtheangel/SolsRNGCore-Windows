from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)


class _CoordinateOverlay(QWidget):
    def __init__(
        self,
        screen,
        callback,
    ):
        super().__init__()

        self._callback = callback

        self.setGeometry(
            screen.geometry()
        )

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            False,
        )

        self.setCursor(
            Qt.CursorShape.CrossCursor
        )

        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ):
        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            return

        position = event.globalPosition().toPoint()

        self._callback(
            QPoint(
                position.x(),
                position.y(),
            )
        )


class CoordinatePicker:
    @staticmethod
    def capture(
        parent,
        label: str,
    ) -> tuple[int, int] | None:
        QMessageBox.information(
            parent,
            "Set Coordinate",
            (
                f"Move to the {label} control on Roblox "
                "and click it.\n\n"
                "The click will be recorded as the coordinate; "
                "it will NOT activate the Roblox control."
            ),
        )

        app = QApplication.instance()

        if app is None:
            return None

        result = {
            "point": None,
        }

        overlays: list[_CoordinateOverlay] = []

        def captured(point):
            result["point"] = (
                int(point.x()),
                int(point.y()),
            )

            for overlay in overlays:
                overlay.close()
                overlay.deleteLater()

            overlays.clear()

        for screen in app.screens():
            overlays.append(
                _CoordinateOverlay(
                    screen,
                    captured,
                )
            )

        while overlays and result["point"] is None:
            app.processEvents()

        return result["point"]
