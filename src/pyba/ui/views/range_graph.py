"""DPS vs distance: compact custom-painted panel (no QtCharts).

Filled falloff curve + dashed hover-preview overlay, falloff start/end
markers, and a mouse hover readout mapping distance -> dps.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from deadlock_eos import Resolution
from deadlock_eos import weapon_math as wm

from .. import theme

_STEPS = 60


def _curve(resolution: Resolution | None) -> list[tuple[float, float]]:
    """(distance_m, dps) samples for the resolved gun; [] when no gun."""
    if resolution is None or resolution.gun is None:
        return []
    gun = resolution.gun
    info = gun.info
    end = info.damage_falloff_end_range or 2000.0
    # ranges are in game units; plotted as meters via /100 for readability
    max_d = end * gun.falloff_range_mult * 1.25
    thresholds = [
        t_m * wm.UNITS_PER_METER
        for bonus in gun.range_bonuses
        for t_m in (bonus.min_distance_m, bonus.max_distance_m)
        if t_m is not None and t_m > 0
    ]
    if thresholds:
        # a gate past the falloff tail (short-falloff gun + Long Range) must
        # still be on the plot, or its dps step never renders
        max_d = max(max_d, max(thresholds) * 1.15)
    xs = {max_d * i / _STEPS for i in range(_STEPS + 1)}
    # sample both edges of every range gate so the step renders as a sharp
    # vertical instead of being smeared across the sampling grid
    for t in thresholds:
        xs.update((t - 0.01, t))
    return [
        (d / wm.UNITS_PER_METER, gun.damage_per_second_at(d / wm.UNITS_PER_METER))
        for d in sorted(xs)
    ]


def _falloff_marks(resolution: Resolution | None) -> tuple[float | None, float | None]:
    """Falloff start/end in meters (after item falloff-range stretch)."""
    if resolution is None or resolution.gun is None:
        return None, None
    gun = resolution.gun
    start = gun.info.damage_falloff_start_range
    end = gun.info.damage_falloff_end_range
    k = gun.falloff_range_mult / wm.UNITS_PER_METER
    return (start * k if start else None), (end * k if end else None)


def _threshold_marks(resolution: Resolution | None) -> list[float]:
    """Range-gate thresholds in meters (Long Range 15m etc.), unique+sorted."""
    if resolution is None or resolution.gun is None:
        return []
    marks = {
        t_m
        for bonus in resolution.gun.range_bonuses
        for t_m in (bonus.min_distance_m, bonus.max_distance_m)
        if t_m is not None
    }
    return sorted(marks)


class _ChartCanvas(QWidget):
    """The painted plot area; owned by RangeGraph."""

    PAD_LEFT = 8
    PAD_RIGHT = 8
    PAD_TOP = 6
    PAD_BOTTOM = 16  # room for distance tick labels

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(160)
        self.setMouseTracking(True)
        self.points: list[tuple[float, float]] = []
        self.preview_points: list[tuple[float, float]] = []
        self.falloff_start: float | None = None
        self.falloff_end: float | None = None
        self.threshold_marks: list[float] = []  # range-gate distances (m)
        self._hover_x: float | None = None  # widget px, None = not hovering

    # --- coordinate mapping --------------------------------------------------

    def _plot_rect(self) -> QRectF:
        return QRectF(
            self.PAD_LEFT,
            self.PAD_TOP,
            self.width() - self.PAD_LEFT - self.PAD_RIGHT,
            self.height() - self.PAD_TOP - self.PAD_BOTTOM,
        )

    def _ranges(self) -> tuple[float, float]:
        max_x = (
            max(
                [x for x, _ in self.points] + [x for x, _ in self.preview_points],
                default=1.0,
            )
            or 1.0
        )
        max_y = max(
            [y for _, y in self.points] + [y for _, y in self.preview_points],
            default=1.0,
        )
        return max_x, (max_y * 1.08 or 1.0)

    def _to_px(self, x: float, y: float, rect: QRectF, max_x: float, max_y: float) -> QPointF:
        return QPointF(
            rect.left() + (x / max_x) * rect.width(),
            rect.bottom() - (y / max_y) * rect.height(),
        )

    @staticmethod
    def _dps_at(points: list[tuple[float, float]], dist: float) -> float | None:
        """Linear interpolation over the sampled curve."""
        if not points:
            return None
        if dist <= points[0][0]:
            return points[0][1]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 <= dist <= x1:
                t = (dist - x0) / (x1 - x0) if x1 > x0 else 0.0
                return y0 + t * (y1 - y0)
        return points[-1][1]

    # --- events ----------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:
        self._hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover_x = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.BG_PANEL))
        rect = self._plot_rect()
        painter.fillRect(rect, QColor(theme.BG_FIELD))

        small = QFont(painter.font())
        small.setPointSize(7)
        painter.setFont(small)

        if not self.points:
            painter.setPen(QColor(theme.FG_DIM))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "no weapon")
            painter.end()
            return

        max_x, max_y = self._ranges()

        # falloff marker lines + tick labels
        dotted = QPen(QColor(theme.BORDER))
        dotted.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(dotted)
        ticks: list[tuple[float, str]] = [(0.0, "0")]
        for mark in (self.falloff_start, self.falloff_end, *self.threshold_marks):
            if mark is not None and mark <= max_x:
                top = self._to_px(mark, max_y, rect, max_x, max_y)
                painter.drawLine(QPointF(top.x(), rect.top()), QPointF(top.x(), rect.bottom()))
                ticks.append((mark, f"{mark:.0f}m"))
        painter.setPen(QColor(theme.FG_DIM))
        for dist, text in ticks:
            px = self._to_px(dist, 0, rect, max_x, max_y)
            painter.drawText(
                QRectF(px.x() - 20, rect.bottom() + 2, 40, self.PAD_BOTTOM - 2),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                text,
            )

        # filled current curve
        line = QPainterPath()
        fill = QPainterPath()
        first = self._to_px(*self.points[0], rect, max_x, max_y)
        line.moveTo(first)
        fill.moveTo(QPointF(first.x(), rect.bottom()))
        fill.lineTo(first)
        for pt in self.points[1:]:
            px = self._to_px(*pt, rect, max_x, max_y)
            line.lineTo(px)
            fill.lineTo(px)
        fill.lineTo(QPointF(line.currentPosition().x(), rect.bottom()))
        fill.closeSubpath()
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        accent = QColor(theme.ACCENT)
        accent.setAlpha(70)
        gradient.setColorAt(0.0, accent)
        transparent = QColor(theme.ACCENT)
        transparent.setAlpha(0)
        gradient.setColorAt(1.0, transparent)
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor(theme.ACCENT), 2))
        painter.drawPath(line)

        # dashed preview overlay
        if self.preview_points:
            preview = QPainterPath()
            preview.moveTo(self._to_px(*self.preview_points[0], rect, max_x, max_y))
            for pt in self.preview_points[1:]:
                preview.lineTo(self._to_px(*pt, rect, max_x, max_y))
            pen = QPen(QColor(theme.DELTA_POSITIVE), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPath(preview)

        # max-dps inline label (top-left)
        painter.setPen(QColor(theme.FG_DIM))
        peak = max(y for _, y in self.points)
        painter.drawText(
            QRectF(rect.left() + 4, rect.top() + 2, 90, 12),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"{peak:.1f} dps",
        )

        # hover: marker dot + distance -> dps readout (top-right)
        if self._hover_x is not None and rect.left() <= self._hover_x <= rect.right():
            dist = (self._hover_x - rect.left()) / rect.width() * max_x
            dps = self._dps_at(self.points, dist)
            if dps is not None:
                px = self._to_px(dist, dps, rect, max_x, max_y)
                painter.setPen(QPen(QColor(theme.FG), 1))
                painter.setBrush(QColor(theme.ACCENT))
                painter.drawEllipse(px, 3, 3)
                readout = f"{dist:.1f} m → {dps:.1f} dps"
                painter.setPen(QColor(theme.FG))
                painter.drawText(
                    QRectF(rect.right() - 150, rect.top() + 2, 146, 12),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                    readout,
                )
                pre_dps = self._dps_at(self.preview_points, dist)
                if pre_dps is not None:
                    painter.setPen(QColor(theme.DELTA_POSITIVE))
                    painter.drawText(
                        QRectF(rect.right() - 150, rect.top() + 14, 146, 12),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                        f"{pre_dps:.1f} dps",
                    )
        painter.end()


class RangeGraph(QGroupBox):
    def __init__(self, session) -> None:
        super().__init__("DPS vs range")
        self.session = session
        self.canvas = _ChartCanvas()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.addWidget(self.canvas)

        session.changed.connect(lambda _res: self.refresh())
        session.previewChanged.connect(self._on_preview)
        self.refresh()

    def refresh(self) -> None:
        resolution = self.session.resolution
        self.canvas.points = _curve(resolution)
        self.canvas.preview_points = []  # a commit invalidates any hover preview
        self.canvas.falloff_start, self.canvas.falloff_end = _falloff_marks(resolution)
        self.canvas.threshold_marks = _threshold_marks(resolution)
        self.canvas.update()

    def _on_preview(self, resolution: Resolution | None) -> None:
        self.canvas.preview_points = _curve(resolution)
        self.canvas.update()
