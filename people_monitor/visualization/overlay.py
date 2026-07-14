"""Прозрачный оверлей поверх рабочего стола для source_kind=screen."""

from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from collections.abc import Callable
from typing import Final

from people_monitor.config import VisualizationConfig
from people_monitor.config._base import BgrColor
from people_monitor.domain import FrameAnalysis, RoiMembership
from people_monitor.geometry import ConvexPolygonRoi

# Chroma-key фона: эти пиксели Windows делает полностью прозрачными. Цвет
# намеренно «неудобный», чтобы не совпасть с цветами разметки.
_TRANSPARENT_COLOR: Final = "#010203"
_FONT_FAMILY: Final = "Segoe UI"
# cv2 FONT_HERSHEY_SIMPLEX при scale=1 даёт примерно такую высоту в пикселях.
_FONT_SCALE_TO_PIXELS: Final = 22.0
_MINIMUM_FONT_PIXELS: Final = 8

_GWL_EXSTYLE: Final = -20
_WS_EX_LAYERED: Final = 0x0008_0000
_WS_EX_TRANSPARENT: Final = 0x0000_0020
_WS_EX_TOOLWINDOW: Final = 0x0000_0080
_WS_EX_NOACTIVATE: Final = 0x0800_0000
# Windows 10 2004+: окно полностью отсутствует в захвате экрана.
_WDA_EXCLUDEFROMCAPTURE: Final = 0x0000_0011
_PROCESS_PER_MONITOR_DPI_AWARE: Final = 2


def _bgr_to_hex(color: BgrColor) -> str:
    blue, green, red = color
    return f"#{red:02x}{green:02x}{blue:02x}"


def _font_pixels(font_scale: float) -> int:
    return max(_MINIMUM_FONT_PIXELS, round(font_scale * _FONT_SCALE_TO_PIXELS))


class ScreenOverlay:
    """Рисует ROI и bbox поверх реального экрана, не перехватывая клики."""

    def __init__(
        self,
        region_provider: Callable[[], dict[str, int]],
        roi: ConvexPolygonRoi,
        settings: VisualizationConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self._region_provider = region_provider
        self._roi = roi
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._region: dict[str, int] | None = None

    def open(self) -> None:
        if self._root is not None:
            raise RuntimeError("Оверлей уже открыт")
        self._enable_dpi_awareness()
        region = self._region_provider()
        root = tk.Tk()
        root.overrideredirect(True)
        root.geometry(
            f"{region['width']}x{region['height']}"
            f"+{region['left']}+{region['top']}"
        )
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", _TRANSPARENT_COLOR)
        canvas = tk.Canvas(
            root,
            bg=_TRANSPARENT_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        root.update_idletasks()
        root.update()

        self._root = root
        self._canvas = canvas
        self._region = region
        self._apply_window_styles(root)
        self._logger.info("Оверлей открыт поверх региона %s", region)

    def draw(
        self,
        analysis: FrameAnalysis,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        """Перерисовать разметку; вернуть False, если окно закрыто."""
        canvas = self._canvas
        root = self._root
        if canvas is None or root is None or self._region is None:
            raise RuntimeError("Оверлей ещё не открыт")
        # Кадр и окно совпадают по размеру, но масштаб страхует от рассинхрона.
        scale_x = self._region["width"] / frame_width
        scale_y = self._region["height"] / frame_height
        try:
            canvas.delete("all")
            self._draw_roi(canvas, analysis, frame_width, frame_height, scale_x, scale_y)
            event_track_ids = {
                track_id
                for event in analysis.events
                for track_id in event.track_ids
            }
            for membership in analysis.memberships:
                self._draw_membership(
                    canvas,
                    membership,
                    event_track_ids,
                    scale_x,
                    scale_y,
                )
            root.update_idletasks()
            root.update()
        except tk.TclError:
            self._logger.info("Окно оверлея закрыто")
            return False
        return True

    def close(self) -> None:
        if self._root is not None:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
        self._root = None
        self._canvas = None
        self._region = None

    def _draw_roi(
        self,
        canvas: tk.Canvas,
        analysis: FrameAnalysis,
        frame_width: int,
        frame_height: int,
        scale_x: float,
        scale_y: float,
    ) -> None:
        color = _bgr_to_hex(self._settings.roi_color)
        points = [
            coordinate
            for x, y in self._roi.pixel_points(frame_width, frame_height)
            for coordinate in (x * scale_x, y * scale_y)
        ]
        canvas.create_polygon(
            points,
            outline=color,
            fill="",
            width=self._settings.roi_thickness,
        )
        canvas.create_text(
            points[0],
            points[1],
            text=self._settings.roi_label_template.format(
                people_count=analysis.people_count,
                capacity=analysis.capacity,
                queue_state=analysis.queue_state.value,
            ),
            fill=color,
            anchor="sw",
            font=(_FONT_FAMILY, -_font_pixels(self._settings.roi_font_scale), "bold"),
        )

    def _draw_membership(
        self,
        canvas: tk.Canvas,
        membership: RoiMembership,
        event_track_ids: set[int],
        scale_x: float,
        scale_y: float,
    ) -> None:
        detection = membership.detection
        bbox = detection.bbox
        track_id = detection.track_id
        color = _bgr_to_hex(
            self._settings.inside_color
            if membership.intersects_roi
            else self._settings.outside_color
        )
        thickness = (
            self._settings.event_bbox_thickness
            if track_id in event_track_ids
            else self._settings.bbox_thickness
        )
        x1, y1 = bbox.x1 * scale_x, bbox.y1 * scale_y
        canvas.create_rectangle(
            x1,
            y1,
            bbox.x2 * scale_x,
            bbox.y2 * scale_y,
            outline=color,
            width=thickness,
        )
        identity = (
            str(track_id)
            if track_id is not None
            else self._settings.unknown_track_label
        )
        label = self._settings.bbox_label_template.format(
            track_id=identity,
            roi_state=(
                self._settings.inside_state_label
                if membership.intersects_roi
                else self._settings.outside_state_label
            ),
        )
        canvas.create_text(
            x1,
            max(
                float(self._settings.minimum_label_y),
                y1 - self._settings.label_vertical_offset,
            ),
            text=label,
            fill=color,
            anchor="sw",
            font=(_FONT_FAMILY, -_font_pixels(self._settings.bbox_font_scale), "bold"),
        )

    def _enable_dpi_awareness(self) -> None:
        # Без этого Tk работает в логических пикселях и при масштабировании
        # экрана разметка уезжает относительно кадра от mss.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(
                _PROCESS_PER_MONITOR_DPI_AWARE
            )
        except (AttributeError, OSError):
            # Уже выставлено (например, самим mss) или ОС старее — не критично.
            pass

    def _apply_window_styles(self, root: tk.Tk) -> None:
        user32 = ctypes.windll.user32
        # У окна без рамки родителя нет, поэтому HWND берём напрямую.
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        styles = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        styles |= (
            _WS_EX_LAYERED
            | _WS_EX_TRANSPARENT
            | _WS_EX_TOOLWINDOW
            | _WS_EX_NOACTIVATE
        )
        user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, styles)
        if not user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE):
            self._logger.warning(
                "Не удалось исключить оверлей из захвата; "
                "разметка попадёт в кадр и в снимки событий"
            )
