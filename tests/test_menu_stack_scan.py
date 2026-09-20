from pathlib import Path

import numpy as np

from l2_brain.cli import main
from l2_brain.io.cgevent_backend import CGEventInputBackend, RecordingPoster
from l2_brain.live.menu_click_debug import run_menu_click_debug
from l2_brain.live.s4_probe import ScriptedGrabber
from l2_brain.vision.calibrate_hud import write_png
from l2_brain.vision.dialog_parser import LEFT_PANEL, extract_menu_items, is_dialog_open, parse_dialog
from l2_brain.vision.menu_stack_scan import CLICK_DX, CLICK_DY, scan_menu_stack


class _Clock:
    def __init__(self) -> None:
        self.t = 10**12

    def __call__(self) -> int:
        return self.t

    def advance_ms(self, ms: int) -> None:
        self.t += ms * 1_000_000


def _stack_frame(
    width: int,
    height: int,
    x0: int,
    y0: int,
    *,
    n: int = 4,
    gap: int = 10,
    bar_w: int = 84,
    bar_h: int = 10,
) -> np.ndarray:
    image = np.full((height, width, 3), 28, dtype=np.uint8)
    image[:, :, 1] = 48
    pad = 8
    py0 = max(0, y0 - pad)
    py1 = min(height, y0 + n * (bar_h + gap) + pad)
    px0 = max(0, x0 - pad)
    px1 = min(width, x0 + bar_w + pad)
    image[py0:py1, px0:px1] = (28, 26, 24)
    for i in range(n):
        y = y0 + i * (bar_h + gap)
        image[y : y + bar_h, x0 : x0 + bar_w] = (60, 90, 210)
    return image


def _drop_first(image: np.ndarray, x0: int, y0: int, *, bar_w: int = 84, bar_h: int = 10) -> np.ndarray:
    out = image.copy()
    out[y0 : y0 + bar_h, x0 : x0 + bar_w] = (28, 26, 24)
    return out


def test_default_parser_still_left_only() -> None:
    left = _stack_frame(400, 300, 26, 70)
    right = _stack_frame(400, 300, 220, 70)
    assert is_dialog_open(left) is True
    assert len(extract_menu_items(left)) >= 3
    assert parse_dialog(left).reason == "html_links"
    assert extract_menu_items(right) == []
    assert is_dialog_open(right) is False


def test_scan_follows_shifted_stack() -> None:
    left = _stack_frame(400, 300, 26, 70)
    dx, dy = 194, 40
    right = _stack_frame(400, 300, 26 + dx, 70 + dy)
    found_left = scan_menu_stack(left)
    found_right = scan_menu_stack(right)
    assert found_left.found is True
    assert found_right.found is True
    assert found_left.stack is not None
    assert found_right.stack is not None
    assert found_right.stack.origin[0] - found_left.stack.origin[0] == dx
    assert found_right.stack.origin[1] - found_left.stack.origin[1] == dy
    assert found_right.stack.click_xy[0] - found_left.stack.click_xy[0] == dx
    assert found_right.stack.click_xy[1] - found_left.stack.click_xy[1] == dy
    assert found_left.stack.click_xy == (
        found_left.stack.origin[0] + CLICK_DX,
        found_left.stack.origin[1] + CLICK_DY,
    )
    assert extract_menu_items(right) == []


def test_scan_rejects_lone_blue_icon() -> None:
    image = np.full((300, 400, 3), 40, dtype=np.uint8)
    image[80:96, 200:216] = (60, 90, 210)
    scanned = scan_menu_stack(image)
    assert scanned.found is False
    assert extract_menu_items(image) == []


def test_click_is_not_left_panel_pixel() -> None:
    image = _stack_frame(400, 300, 220, 90)
    scanned = scan_menu_stack(image)
    assert scanned.found is True
    assert scanned.stack is not None
    px0, py0, px1, py1 = LEFT_PANEL.pixel_box(400, 300)
    cx, cy = scanned.stack.click_xy
    assert not (px0 <= cx < px1 and py0 <= cy < py1)


def test_cli_scan_from_png_no_hid(tmp_path: Path) -> None:
    png = tmp_path / "moved.png"
    write_png(png, _stack_frame(400, 300, 220, 80))
    out = tmp_path / "scan.json"
    overlay = tmp_path / "overlay.png"
    code = main(
        [
            "menu-click-debug",
            "--scan",
            "--from-png",
            str(png),
            "--out",
            str(out),
            "--overlay",
            str(overlay),
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert '"found": true' in text
    assert '"hid_sent": false' in text
    assert '"validation_result": "SCAN_ONLY"' in text
    assert "R3" not in text
    assert overlay.is_file()


def test_cli_go_without_flags(tmp_path: Path) -> None:
    out = tmp_path / "go.json"
    code = main(["menu-click-debug", "--go", "--out", str(out)])
    assert code == 2
    assert "live_flags_required" in out.read_text(encoding="utf-8")


def test_cli_go_rejects_png(tmp_path: Path) -> None:
    png = tmp_path / "x.png"
    write_png(png, _stack_frame(400, 300, 220, 80))
    out = tmp_path / "go.json"
    code = main(
        [
            "menu-click-debug",
            "--go",
            "--live",
            "--danger-confirmed",
            "--from-png",
            str(png),
            "--out",
            str(out),
        ]
    )
    assert code == 2
    assert "png_not_for_go" in out.read_text(encoding="utf-8")


def test_cli_rejects_r3_path(tmp_path: Path) -> None:
    png = tmp_path / "x.png"
    write_png(png, _stack_frame(400, 300, 26, 70))
    out = tmp_path / "R3-runtime-menu.json"
    code = main(["menu-click-debug", "--scan", "--from-png", str(png), "--out", str(out)])
    assert code == 2
    assert not out.exists()


def test_go_pass_when_menu_changes(tmp_path: Path) -> None:
    clock = _Clock()
    before = _stack_frame(400, 300, 220, 80)
    after = _drop_first(before, 220, 80)
    backend = CGEventInputBackend(
        4242,
        live_confirmed=True,
        live_danger_confirmed=True,
        poster=RecordingPoster(),
        focus_probe=lambda: True,
        now_ns=clock,
    )
    payload = run_menu_click_debug(
        go=True,
        live=True,
        danger_confirmed=True,
        grabber=ScriptedGrabber([before, after]),
        backend=backend,
        sleeper=lambda s: clock.advance_ms(int(s * 1000)),
        now_ns=clock,
        out_path=tmp_path / "go.json",
        focus_probe=lambda: True,
    )
    assert payload["validation_result"] == "PASS"
    assert payload["ok"] is True
    assert payload["menu_changed"] is True
    assert payload["click_xy"] == [220 + CLICK_DX, 80 + CLICK_DY]
    assert any(row.action_type == "GroundClick" for row in backend.log)
    assert payload["hid_sent"] is False


def test_go_fail_when_menu_stays(tmp_path: Path) -> None:
    clock = _Clock()
    frame = _stack_frame(400, 300, 220, 80)
    backend = CGEventInputBackend(
        4242,
        live_confirmed=True,
        live_danger_confirmed=True,
        poster=RecordingPoster(),
        focus_probe=lambda: True,
        now_ns=clock,
    )
    payload = run_menu_click_debug(
        go=True,
        live=True,
        danger_confirmed=True,
        grabber=ScriptedGrabber([frame, frame]),
        backend=backend,
        sleeper=lambda s: clock.advance_ms(int(s * 1000)),
        now_ns=clock,
        out_path=tmp_path / "go.json",
        focus_probe=lambda: True,
    )
    assert payload["validation_result"] == "FAIL"
    assert payload["ok"] is False
    assert payload["aborted"] == "menu_unchanged"
    assert payload["click_xy"][0] > 200
