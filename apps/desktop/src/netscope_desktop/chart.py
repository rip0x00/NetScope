"""Latency chart widget: QPainter rendering of the sampler's series.

The chart is deliberately plain: a grid with a millisecond scale, one
line that breaks where a sample failed, and a small cross on the
baseline for each failure. All geometry comes from
:class:`~netscope_desktop.sampler.ChartModel`; this widget only
paints. Colours come from the design tokens of the active theme.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .sampler import ChartModel

_LEFT_PAD = 44.0
_RIGHT_PAD = 8.0
_TOP_PAD = 8.0
_BOTTOM_PAD = 6.0


class LatencyChart(QWidget):
    """A live latency line chart with failure markers."""

    def __init__(self, colors: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = ChartModel([])
        self.set_colors(colors)
        self.setMinimumHeight(180)
        self.setAccessibleName("Latency chart")
        self.setAccessibleDescription("No samples yet.")

    def set_colors(self, colors: dict[str, str]) -> None:
        self._colors = colors
        self.update()

    def set_series(self, series: list[float | None]) -> None:
        self._model = ChartModel(series)
        good = [s for s in series if s is not None]
        if good:
            self.setAccessibleDescription(
                f"{len(series)} samples, {len(good)} successful, "
                f"latest {good[-1]:.1f} milliseconds, axis ceiling "
                f"{self._model.ceiling_ms():.0f} milliseconds."
            )
        else:
            self.setAccessibleDescription("No successful samples yet.")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        colors = self._colors
        plot = QRectF(
            _LEFT_PAD,
            _TOP_PAD,
            max(1.0, self.width() - _LEFT_PAD - _RIGHT_PAD),
            max(1.0, self.height() - _TOP_PAD - _BOTTOM_PAD),
        )
        painter.fillRect(self.rect(), QColor(colors["surface"]))
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawRect(plot)

        ceiling = self._model.ceiling_ms()
        painter.setPen(QColor(colors["textSecondary"]))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(QPen(QColor(colors["border"]), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(QColor(colors["textSecondary"]))
            painter.drawText(
                QRectF(0, y - 8, _LEFT_PAD - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{ceiling * fraction:.0f}",
            )

        segments = self._model.segments(plot.width(), plot.height())
        painter.setPen(QPen(QColor(colors["accent"]), 2))
        for segment in segments:
            for (x1, y1), (x2, y2) in zip(segment, segment[1:]):
                painter.drawLine(
                    int(plot.left() + x1), int(plot.top() + y1),
                    int(plot.left() + x2), int(plot.top() + y2),
                )

        painter.setPen(QPen(QColor(colors["error"]), 1))
        baseline = int(plot.bottom())
        for x in self._model.failure_positions(plot.width()):
            px = int(plot.left() + x)
            painter.drawLine(px - 3, baseline - 3, px + 3, baseline + 3)
            painter.drawLine(px - 3, baseline + 3, px + 3, baseline - 3)
        painter.end()
