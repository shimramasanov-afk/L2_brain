"""Full-frame blue HTML-link stack. Diagnostic only.

Does not replace LEFT_PANEL / extract_menu_items. Blue icons can
yield a false stack. Click is origin + (70, -14), not a left-panel
pixel. No OCR. No packets.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np

from l2_brain.vision.dialog_parser import (
    BLUE_LINK,
    HTML_ITEMS_MIN,
    LEFT_PANEL,
    _as_rgb,
    _geom_limits,
    _link_boxes,
)

CLICK_DX = 70
CLICK_DY = -14
STACK_MIN = HTML_ITEMS_MIN


@dataclass(frozen=True, slots=True)
class MenuStack:
    origin: tuple[int, int]
    boxes: tuple[tuple[int, int, int, int], ...]
    items: tuple[tuple[int, int], ...]
    click_xy: tuple[int, int]
    confidence: float
    reason: str
    kind: str = "blue_stack"

    def fingerprint(self) -> tuple[int, tuple[tuple[int, int], ...]]:
        return (len(self.items), tuple((int(x) // 8, int(y) // 8) for x, y in self.items))

    def click_for_index(self, index: int, *, bounds: tuple[int, int] | None = None) -> tuple[int, int]:
        x0, y0, _x1, _y1 = self.boxes[int(index)]
        return _click_from_origin(x0, y0, bounds=bounds)


@dataclass(frozen=True, slots=True)
class MenuStackScan:
    found: bool
    stack: MenuStack | None
    n_boxes: int
    n_stacks: int
    scan_ms: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        stack = self.stack
        return {
            "found": self.found,
            "reason": self.reason,
            "n_boxes": self.n_boxes,
            "n_stacks": self.n_stacks,
            "scan_ms": round(self.scan_ms, 3),
            "click_dx": CLICK_DX,
            "click_dy": CLICK_DY,
            "origin": None if stack is None else [stack.origin[0], stack.origin[1]],
            "click_xy": None if stack is None else [stack.click_xy[0], stack.click_xy[1]],
            "items": [] if stack is None else [[int(x), int(y)] for x, y in stack.items],
            "boxes": [] if stack is None else [list(box) for box in stack.boxes],
            "confidence": None if stack is None else stack.confidence,
            "kind": None if stack is None else stack.kind,
            "fingerprint": None if stack is None else [stack.fingerprint()[0], [list(p) for p in stack.fingerprint()[1]]],
        }


def scan_menu_stack(frame: np.ndarray) -> MenuStackScan:
    """Find a vertical column of blue link boxes anywhere in the frame."""
    started = perf_counter()
    rgb = _as_rgb(frame)
    if rgb is None:
        return MenuStackScan(False, None, 0, 0, _ms(started), "too_small")
    height, width = rgb.shape[:2]
    if height < 16 or width < 16:
        return MenuStackScan(False, None, 0, 0, _ms(started), "too_small")
    min_w, min_h, max_h = _geom_limits(height)
    blue = np.all((rgb >= BLUE_LINK[0]) & (rgb <= BLUE_LINK[1]), axis=2)
    boxes = _link_boxes(blue, min_w, min_h, max_h)
    if not boxes:
        return MenuStackScan(False, None, 0, 0, _ms(started), "no_blue_box")
    x_tol = max(16, min_w // 3)
    columns = _cluster_columns(boxes, x_tol=x_tol)
    stacks = [col for col in columns if len(col) >= STACK_MIN]
    if not stacks:
        return MenuStackScan(False, None, len(boxes), len(columns), _ms(started), "no_column")
    chosen = max(stacks, key=lambda col: (len(col), -col[0][0], -_x_spread(col)))
    chosen = tuple(sorted(chosen, key=lambda box: box[1]))
    x0, y0, _x1, _y1 = chosen[0]
    bounds = (width, height)
    click = _click_from_origin(x0, y0, bounds=bounds)
    items = tuple(((bx0 + bx1) // 2, (by0 + by1) // 2) for bx0, by0, bx1, by1 in chosen)
    align = 1.0 - min(1.0, _x_spread(chosen) / 40.0)
    confidence = float(min(1.0, 0.35 + 0.12 * len(chosen) + 0.25 * align))
    stack = MenuStack(
        origin=(int(x0), int(y0)),
        boxes=chosen,
        items=items,
        click_xy=click,
        confidence=confidence,
        reason="blue_stack",
    )
    return MenuStackScan(True, stack, len(boxes), len(stacks), _ms(started), "blue_stack")


def left_panel_box(width: int, height: int) -> tuple[int, int, int, int]:
    return LEFT_PANEL.pixel_box(width, height)


def _click_from_origin(x0: int, y0: int, *, bounds: tuple[int, int] | None) -> tuple[int, int]:
    x = int(x0) + CLICK_DX
    y = int(y0) + CLICK_DY
    if bounds is not None:
        width, height = bounds
        x = min(max(0, x), max(0, width - 1))
        y = min(max(0, y), max(0, height - 1))
    return x, y


def _cluster_columns(
    boxes: list[tuple[int, int, int, int]],
    *,
    x_tol: int,
) -> list[list[tuple[int, int, int, int]]]:
    columns: list[list[tuple[int, int, int, int]]] = []
    for box in sorted(boxes, key=lambda row: (row[0], row[1])):
        cx = (box[0] + box[2]) // 2
        placed = False
        for column in columns:
            ref = column[0]
            ref_cx = (ref[0] + ref[2]) // 2
            if abs(box[0] - ref[0]) <= x_tol and abs(cx - ref_cx) <= x_tol:
                column.append(box)
                placed = True
                break
        if not placed:
            columns.append([box])
    return columns


def _x_spread(boxes: list[tuple[int, int, int, int]] | tuple[tuple[int, int, int, int], ...]) -> float:
    xs = [float(box[0]) for box in boxes]
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return float(var**0.5)


def _ms(started: float) -> float:
    return float((perf_counter() - started) * 1000.0)
