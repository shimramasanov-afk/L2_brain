"""Scan a moved HTML dialog. Click only on --go with dual flags.

Not R3/R4/R5. Not the default LEFT_PANEL parser. Live HID is not
started by --scan. Blue icons may false-trigger a stack.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from l2_brain.experiment.clocks import mono_ns
from l2_brain.io.actions import GroundClick, MouseButton
from l2_brain.io.cgevent_backend import CGEventInputBackend
from l2_brain.io.focus import frontmost_app, is_allowed_frontmost
from l2_brain.live.s4_probe import SCKGrabber, _ms, s4_input_profile
from l2_brain.vision.calibrate_hud import draw_rect, grab_window_frame, read_png, write_png
from l2_brain.vision.dialog_parser import extract_menu_items
from l2_brain.vision.menu_stack_scan import MenuStackScan, left_panel_box, scan_menu_stack

DEFAULT_OUT = Path("run/menu-click-debug.json")
GO_WAIT_S = 0.45


def run_menu_click_debug(
    *,
    scan: bool = True,
    go: bool = False,
    live: bool = False,
    danger_confirmed: bool = False,
    window_id: int | None = None,
    target_pid: int | None = None,
    from_png: Path | None = None,
    out_path: Path | None = DEFAULT_OUT,
    overlay_path: Path | None = None,
    index: int = 0,
    grabber: Any | None = None,
    backend: CGEventInputBackend | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now_ns: Callable[[], int] | None = None,
    focus_probe: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    clock = now_ns or mono_ns
    started = clock()
    payload: dict[str, Any] = {
        "ok": False,
        "mode": "go" if go else "scan",
        "scan": bool(scan or not go),
        "go": bool(go),
        "live": False,
        "hid_sent": False,
        "farm": False,
        "aborted": None,
        "window_id": window_id,
        "target_pid": target_pid,
        "from_png": None if from_png is None else str(from_png),
        "default_parser": "LEFT_PANEL_untouched",
        "canon": None,
        "validation_result": None,
        "stack": None,
        "default_items": [],
        "click_xy": None,
        "click_index": int(index),
        "before": None,
        "after": None,
        "menu_changed": None,
        "steps": [],
    }
    if _is_canon_path(out_path):
        payload["aborted"] = "canon_path_forbidden"
        return _finish(payload, None, clock, started, None)

    if go and from_png is not None and grabber is None:
        payload["aborted"] = "png_not_for_go"
        return _finish(payload, out_path, clock, started, None)

    if go:
        if not live or not danger_confirmed:
            payload["aborted"] = "live_flags_required"
            return _finish(payload, out_path, clock, started, None)
        payload["live"] = True
        return _run_go(
            payload,
            window_id=window_id,
            target_pid=target_pid,
            out_path=out_path,
            overlay_path=overlay_path,
            index=int(index),
            grabber=grabber,
            backend=backend,
            sleeper=sleeper,
            clock=clock,
            started=started,
            focus_probe=focus_probe,
        )

    image, reason = _load_frame(from_png=from_png, window_id=window_id, grabber=grabber)
    if image is None:
        payload["aborted"] = reason
        return _finish(payload, out_path, clock, started, None)
    _fill_scan(payload, image, index=int(index), overlay_path=overlay_path)
    payload["ok"] = True
    payload["validation_result"] = "SCAN_ONLY"
    return _finish(payload, out_path, clock, started, None)


def _run_go(
    payload: dict[str, Any],
    *,
    window_id: int | None,
    target_pid: int | None,
    out_path: Path | None,
    overlay_path: Path | None,
    index: int,
    grabber: Any | None,
    backend: CGEventInputBackend | None,
    sleeper: Callable[[float], None],
    clock: Callable[[], int],
    started: int,
    focus_probe: Callable[[], bool] | None,
) -> dict[str, Any]:
    own_grabber = grabber is None
    own_backend = backend is None
    if grabber is None:
        if window_id is None or int(window_id) < 1:
            payload["aborted"] = "window_id_required"
            return _finish(payload, out_path, clock, started, None)
        grabber = SCKGrabber(int(window_id), latest_timeout_s=4.0)
    if own_backend:
        pid = int(target_pid or 0)
        if pid < 1:
            info = frontmost_app()
            pid = int(info.pid) if info is not None else 0
        if pid < 1:
            payload["aborted"] = "no_target_pid"
            return _finish(payload, out_path, clock, started, None)
        payload["target_pid"] = pid
        backend = CGEventInputBackend(
            pid,
            live_confirmed=True,
            live_danger_confirmed=True,
            profile=s4_input_profile(),
            focus_probe=focus_probe or is_allowed_frontmost,
        )
    assert backend is not None
    focus = focus_probe or backend.check_window_focus
    try:
        if own_grabber:
            grabber.start()
        if not focus():
            payload["aborted"] = "focus_lost"
            return _finish(payload, out_path, clock, started, backend)
        before = np.ascontiguousarray(grabber.latest_image())
        _fill_scan(payload, before, index=index, overlay_path=overlay_path)
        payload["before"] = payload.get("stack")
        if not payload.get("stack", {}).get("found"):
            payload["aborted"] = "no_stack"
            payload["validation_result"] = "FAIL"
            return _finish(payload, out_path, clock, started, backend)
        click = payload.get("click_xy")
        if click is None:
            payload["aborted"] = "no_click"
            payload["validation_result"] = "FAIL"
            return _finish(payload, out_path, clock, started, backend)
        event = backend.send_action(GroundClick(x=int(click[0]), y=int(click[1]), button=MouseButton.LEFT))
        payload["hid_sent"] = bool(event.hid_sent)
        payload["steps"].append(
            {"step": "click", "x": int(click[0]), "y": int(click[1]), "accepted": event.accepted, "hid_sent": event.hid_sent}
        )
        if not event.accepted:
            payload["aborted"] = event.reason or "click_rejected"
            payload["validation_result"] = "FAIL"
            return _finish(payload, out_path, clock, started, backend)
        sleeper(GO_WAIT_S)
        backend.pump()
        after = np.ascontiguousarray(grabber.latest_image())
        after_scan = scan_menu_stack(after)
        payload["after"] = after_scan.to_dict()
        payload["after"]["default_items"] = [[int(x), int(y)] for x, y in extract_menu_items(after)]
        changed = _menu_changed(payload.get("before"), payload.get("after"))
        payload["menu_changed"] = changed
        if changed:
            payload["ok"] = True
            payload["validation_result"] = "PASS"
        else:
            payload["ok"] = False
            payload["validation_result"] = "FAIL"
            payload["aborted"] = "menu_unchanged"
        payload["steps"].append({"step": "after", "changed": changed})
        return _finish(payload, out_path, clock, started, backend)
    finally:
        if own_grabber:
            grabber.close()


def _load_frame(
    *,
    from_png: Path | None,
    window_id: int | None,
    grabber: Any | None,
) -> tuple[np.ndarray | None, str | None]:
    if from_png is not None:
        return read_png(Path(from_png)), None
    if grabber is not None:
        return np.ascontiguousarray(grabber.latest_image()), None
    if window_id is None or int(window_id) < 1:
        return None, "window_id_required"
    return grab_window_frame(int(window_id)), None


def _fill_scan(
    payload: dict[str, Any],
    image: np.ndarray,
    *,
    index: int,
    overlay_path: Path | None,
) -> None:
    height, width = image.shape[:2]
    payload["width"] = int(width)
    payload["height"] = int(height)
    scanned = scan_menu_stack(image)
    row = scanned.to_dict()
    default_items = [[int(x), int(y)] for x, y in extract_menu_items(image)]
    row["default_items"] = default_items
    row["left_panel"] = list(left_panel_box(width, height))
    payload["stack"] = row
    payload["default_items"] = default_items
    payload["scan_ms"] = row["scan_ms"]
    click = None
    if scanned.found and scanned.stack is not None:
        if 0 <= int(index) < len(scanned.stack.boxes):
            click = list(scanned.stack.click_for_index(index, bounds=(width, height)))
        else:
            click = list(scanned.stack.click_xy)
    payload["click_xy"] = click
    if overlay_path is not None:
        write_png(Path(overlay_path), _draw_overlay(image, scanned, click))
        payload["overlay"] = str(overlay_path)


def _draw_overlay(image: np.ndarray, scanned: MenuStackScan, click: list[int] | None) -> np.ndarray:
    out = np.ascontiguousarray(image.copy())
    height, width = out.shape[:2]
    draw_rect(out, left_panel_box(width, height), (90, 90, 90), width=2)
    if scanned.stack is not None:
        for box in scanned.stack.boxes:
            draw_rect(out, box, (20, 220, 220), width=2)
    if click is not None:
        cx, cy = int(click[0]), int(click[1])
        draw_rect(out, (cx - 6, cy - 6, cx + 7, cy + 7), (240, 40, 40), width=2)
    return out


def _menu_changed(before: dict[str, Any] | None, after: dict[str, Any] | None) -> bool:
    if not before or not after:
        return False
    return before.get("fingerprint") != after.get("fingerprint") or before.get("items") != after.get("items")


def _is_canon_path(path: Path | None) -> bool:
    if path is None:
        return False
    resolved = Path(path)
    name = resolved.name
    if name.startswith("R3-") or name.startswith("R4-") or name.startswith("R5-"):
        return True
    return False


def _finish(
    payload: dict[str, Any],
    out_path: Path | None,
    clock: Callable[[], int],
    started: int,
    backend: CGEventInputBackend | None,
) -> dict[str, Any]:
    payload["elapsed_time_sec"] = _ms(clock(), started) / 1000.0
    if backend is not None:
        backend.release_all()
        payload["hid_sent"] = bool(payload.get("hid_sent") or any(row.hid_sent for row in backend.log))
        payload["events"] = [row.to_dict() for row in backend.log]
    payload.pop("_image", None)
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        writable = {key: value for key, value in payload.items() if not str(key).startswith("_")}
        out_path.write_text(json.dumps(writable, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["out"] = str(out_path)
    return payload
