from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from l2_brain import __version__
from l2_brain.accel import selected_backend
from l2_brain.circuit.config import CircuitConfig
from l2_brain.circuit.loop import build_mock_circuit
from l2_brain.circuit.replay import replay_recorded_observations
from l2_brain.experiment.identity import OFFLINE_REPLAY_LIMIT
from l2_brain.experiment.replay import SessionReplay, write_timing_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l2-brain", description="Biomimetic L2 Agent CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    mock = sub.add_parser("mock", help="полный контур на искусственных кадрах")
    _add_run_flags(mock)

    record = sub.add_parser("record", help="запись эксперимента: JSONL или каталог")
    _add_run_flags(record)
    record.add_argument("--out", type=Path, required=True, help="session.jsonl или каталог эксперимента")

    replay = sub.add_parser("replay", help="воспроизведение: offline / realtime / speed / step")
    replay.add_argument("session", type=Path)
    replay.add_argument("--now-ns", type=int, default=10**15)
    replay.add_argument("--mode", choices=("offline", "realtime", "speed", "step"), default="offline")
    replay.add_argument("--speed", type=float, default=1.0)
    replay.add_argument("--tick", type=int, default=None)
    replay.add_argument("--no-sleep", action="store_true")

    inspect = sub.add_parser("inspect", help="один тик: кадр, признаки, намерение, команда, задержки")
    inspect.add_argument("session", type=Path)
    inspect.add_argument("--tick", type=int, required=True)

    ev = sub.add_parser("eval", help="стендовая оценка контроллеров (синтетическая среда)")
    ev.add_argument("--controller", default="reactive")
    ev.add_argument("--scenario", default="open_field")
    ev.add_argument("--episodes", type=int, default=8)
    ev.add_argument("--seed", type=int, default=0)
    ev.add_argument("--all-controllers", action="store_true")
    ev.add_argument("--json-out", type=Path, default=None)

    sub.add_parser("doctor", help="диагностика окружения, без железа")

    sim = sub.add_parser("sim-eval", help="headless оценка навигационного стенда")
    sim.add_argument("--seed", type=int, default=0)
    sim.add_argument("--split", choices=("training", "validation", "held_out"), default=None)
    sim.add_argument("--max-steps", type=int, default=4)
    sim.add_argument("--out", type=Path, required=True)
    sim.add_argument("--scenario", action="append", default=None)

    cap = sub.add_parser("capture", help="ScreenCaptureKit: list / permission / record")
    cap.add_argument("action", choices=("permission", "list", "record"))
    cap.add_argument("--window-id", type=int, default=None)
    cap.add_argument("--self-test", action="store_true")
    cap.add_argument("--resize", action="store_true")
    cap.add_argument("--fps", type=int, default=30)
    cap.add_argument("--ticks", type=int, default=8)
    cap.add_argument("--duration", type=float, default=None, help="wall seconds for H7 probe; skips circuit record")
    cap.add_argument("--out", type=Path, default=None)
    cap.add_argument("--profile", type=Path, default=None)
    cap.add_argument("--log-level", default="ERROR")
    cap.add_argument("--helper", type=Path, default=None)

    vis = sub.add_parser("vision", help="эталонный VisualEncoder: бенч и диагностика")
    vis.add_argument("action", choices=("bench", "diag"))
    vis.add_argument("--out", type=Path, default=None)
    vis.add_argument("--repeats", type=int, default=8)

    base = sub.add_parser("baseline-eval", help="прозрачный базовый контроллер на всём навигационном каталоге")
    base.add_argument("--seed", type=int, default=0)
    base.add_argument("--split", choices=("training", "validation", "held_out"), default=None)
    base.add_argument("--max-steps", type=int, default=None)
    base.add_argument("--out", type=Path, required=True)
    base.add_argument("--scenario", action="append", default=None)
    base.add_argument("--no-recovery", action="store_true")
    base.add_argument("--compare", type=Path, default=None)
    base.add_argument("--suite", choices=("frozen", "integrity", "diagnostic"), default="frozen")
    base.add_argument("--encoder", choices=("color_blob", "navigation_v1"), default="navigation_v1")
    base.add_argument(
        "--channels",
        choices=("target", "target_flow", "target_expansion", "all"),
        default="all",
    )
    base.add_argument("--controller", choices=("baseline", "snn"), default="baseline")

    bench = sub.add_parser("bench", help="мини-сравнение контроллеров на одном эпизоде, не Frozen 60")
    bench.add_argument("--scenario", default="open_goal")
    bench.add_argument("--split", choices=("training", "validation", "held_out"), default="training")
    bench.add_argument("--variant", type=int, default=0)
    bench.add_argument("--seed", type=int, default=0)
    bench.add_argument("--out", type=Path, required=True)

    learn = sub.add_parser("learn", help="короткая серия R-STDP на одном эпизоде, не Frozen 60")
    learn.add_argument("--scenario", default="open_goal")
    learn.add_argument("--split", choices=("training", "validation", "held_out"), default="training")
    learn.add_argument("--variant", type=int, default=0)
    learn.add_argument("--seed", type=int, default=0)
    learn.add_argument("--episodes", type=int, default=8)
    learn.add_argument("--noise", type=float, default=0.35)
    learn.add_argument("--out", type=Path, required=True)

    dry = sub.add_parser("input-dry-run", help="лог MotorIntent→GameAction без HID")
    dry.add_argument("--out", type=Path, required=True)
    dry.add_argument("--move-mode", choices=("hold_forward", "ground_click"), default="hold_forward")

    focusb = sub.add_parser("focus-bench", help="замер нативной проверки фокуса, без HID")
    focusb.add_argument("--repeats", type=int, default=80)
    focusb.add_argument("--out", type=Path, default=Path("docs/evidence/hod38/focus-bench.json"))

    cal = sub.add_parser("calibrate-hud", help="снимок окна и оверлей ROI HUD, без ввода")
    cal.add_argument("--window-id", type=int, default=None)
    cal.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    cal.add_argument("--out-dir", type=Path, default=Path("docs/evidence/live-s4"))
    cal.add_argument("--tag", default=None, help="метка снимка, например interlude_active")
    cal.add_argument("--from-png", type=Path, default=None, help="офлайн кадр, без SCK и без HID")

    mot = sub.add_parser("calibrate-motion", help="один импульс стрелки и один шаг w, замер сдвига кадра")
    mot.add_argument("--window-id", type=int, default=None)
    mot.add_argument("--live", action="store_true")
    mot.add_argument("--danger-confirmed", action="store_true")
    mot.add_argument("--target-pid", type=int, default=None)
    mot.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    mot.add_argument("--out", type=Path, default=Path("docs/evidence/live-s4/motion-calibration.json"))
    mot.add_argument("--write-profile", action="store_true", help="записать motion в профиль только после живого замера")
    mot.add_argument("--horizon", action="store_true", help="кроп неба/горизонта 15–30%% × 25–75%%, без шага w")
    mot.add_argument("--band", choices=("center", "horizon"), default=None)
    mot.add_argument("--klt", action="store_true", help="yaw KLT+RANSAC, right+left 450 мс, без шага w")
    mot.add_argument("--rmb", action="store_true", help="yaw v3: RMB drag, fallback arrow pulse")
    mot.add_argument("--mouse-dx", type=float, default=150.0, help="RMB drag px, default 150")
    mot.add_argument("--mouse-dy", type=float, default=0.0, help="RMB vertical px, pitch")
    mot.add_argument("--rmb-steps", type=int, default=5)
    mot.add_argument("--rmb-step-ms", type=int, default=10)
    mot.add_argument("--arrow-taps", type=int, default=10)
    mot.add_argument("--arrow-hold-ms", type=int, default=0, help="если pulse не physical — удержать стрелку")
    mot.add_argument("--sync-diag", action="store_true", help="T0/T1 isolation: copy, 300ms, unique ts, PNG dump")

    live_mot = sub.add_parser("live-motion", help="непрерывный w + поток NavigationEncoder, затем упор, без фарма")
    live_mot.add_argument("--window-id", type=int, default=None)
    live_mot.add_argument("--live", action="store_true")
    live_mot.add_argument("--danger-confirmed", action="store_true")
    live_mot.add_argument("--target-pid", type=int, default=None)
    live_mot.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    live_mot.add_argument("--out", type=Path, default=Path("docs/evidence/live-s4/l1-flow-validation.json"))
    live_mot.add_argument("--free-ticks", type=int, default=10)
    live_mot.add_argument("--blocked-ticks", type=int, default=3)
    live_mot.add_argument("--hold-ms", type=int, default=600, help="период сэмпла при непрерывном w, не пульс")

    h8b = sub.add_parser("bench-h8", help="100 тиков observe+parse+infer+idle-act, без игровых клавиш")
    h8b.add_argument("--window-id", type=int, default=None)
    h8b.add_argument("--samples", type=int, default=100)
    h8b.add_argument("--warmup", type=int, default=8)
    h8b.add_argument("--live", action="store_true")
    h8b.add_argument("--danger-confirmed", action="store_true")
    h8b.add_argument("--target-pid", type=int, default=None)
    h8b.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    h8b.add_argument("--out", type=Path, default=Path("docs/evidence/live-s4/h8-latency-report.json"))

    probe = sub.add_parser("input-probe", help="CGEvent probe в Блокнот гостя, не клиент игры")
    probe.add_argument("--target-pid", type=int, required=True)
    probe.add_argument("--live", action="store_true")
    probe.add_argument("--live-confirmed", action="store_true")
    probe.add_argument("--vm-name", default="Windows 11")
    probe.add_argument("--out", type=Path, default=Path("docs/evidence/live-s3/notepad-probe.json"))

    combat = sub.add_parser("combat-dry-run", help="синтетический бой combat_dummy_v0, без клиента и HID")
    combat.add_argument("--out", type=Path, required=True)

    spot = sub.add_parser("spot-loop", help="непрерывный спот multi_dummy_arena_v0, dry-run, без клиента")
    spot.add_argument("--out", type=Path, required=True)
    spot.add_argument("--ticks", type=int, default=250)
    spot.add_argument("--seed", type=int, default=0)

    prof = sub.add_parser("profile", help="профиль стадий контура и read-only аудит MPS")
    prof.add_argument("--ticks", type=int, default=100)
    prof.add_argument("--warmup", type=int, default=10)
    prof.add_argument("--seed", type=int, default=0)
    prof.add_argument("--out", type=Path, required=True)

    male = sub.add_parser("malecns-eval", help="синтетический подграф MaleCNS vs snn_v1, не Frozen 60")
    male.add_argument("--seed", type=int, default=0)
    male.add_argument("--out", type=Path, required=True)

    suite = sub.add_parser("suite", help="мини-сводка 5 контроллеров × 5 сцен, не Frozen 60")
    suite.add_argument("--seed", type=int, default=0)
    suite.add_argument("--out", type=Path, required=True)

    s4 = sub.add_parser("s4-probe", help="один короткий боевой зонд S4, без фарма")
    s4.add_argument("--window-id", type=int, default=None)
    s4.add_argument("--live", action="store_true")
    s4.add_argument("--danger-confirmed", action="store_true")
    s4.add_argument("--clean-target", action="store_true", help="сброс Escape, новый моб HP>0.85, двойной F2")
    s4.add_argument("--engage-any", action="store_true", help="атака цели с HP>=0.15, двойной F2")
    s4.add_argument("--kill-and-loot", action="store_true", help="один моб до смерти и F3, без фарма")
    s4.add_argument(
        "--multi-kill",
        type=int,
        default=0,
        metavar="N",
        help="ровно N мобов (N<=3) или 45с, без фарма",
    )
    s4.add_argument(
        "--verify-search",
        action="store_true",
        help="пустой /targetnext, стрелка вправо + w, один килл, без фарма",
    )
    s4.add_argument("--target-pid", type=int, default=None)
    s4.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    s4.add_argument("--out", type=Path, default=None)

    integ = sub.add_parser(
        "s4-integrated-spot",
        help="L1 encoder + L2 spot FSM, до 10 фрагов, без фарма",
    )
    integ.add_argument("--window-id", type=int, default=None)
    integ.add_argument("--live", action="store_true")
    integ.add_argument("--danger-confirmed", action="store_true")
    integ.add_argument("--target-pid", type=int, default=None)
    integ.add_argument("--kills", type=int, default=10)
    integ.add_argument("--timeout", type=float, default=None)
    integ.add_argument("--no-timeout", action="store_true", help="серия только по капу фрагов")
    integ.add_argument("--no-heal", action="store_true", help="F4 не слать (уже по умолчанию)")
    integ.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    integ.add_argument("--out", type=Path, default=None)
    integ.add_argument(
        "--runtime-validation",
        action="store_true",
        help="R2: LiveRuntime combat evidence, не переписывает F82",
    )

    grid = sub.add_parser("layout-grid", help="оверлей слотов UI на кадре, без HID")
    grid.add_argument("--window-id", type=int, default=None)
    grid.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    grid.add_argument("--save", type=Path, default=Path("run/layout_guide.png"))
    grid.add_argument("--from-png", type=Path, default=None)

    overlay = sub.add_parser("layout-overlay", help="рамки поверх окна Parallels, клики навылет, без HID")
    overlay.add_argument("--window-id", type=int, default=None)
    overlay.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    overlay.add_argument("--seconds", type=float, default=180.0)
    overlay.add_argument("--no-show", action="store_true", help="только геометрия, окно не показывать")

    slots = sub.add_parser("layout-slots", help="живой Tab/Escape: занятость слота Б, без фарма")
    slots.add_argument("--window-id", type=int, default=None)
    slots.add_argument("--live", action="store_true")
    slots.add_argument("--danger-confirmed", action="store_true")
    slots.add_argument("--target-pid", type=int, default=None)
    slots.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    slots.add_argument("--out", type=Path, default=Path("docs/evidence/live-s4/layout-slots-validation.json"))

    npc = sub.add_parser("s4-npc-dialog", help="мирный зонд NPC: F5, диалог, клик, без фарма")
    npc.add_argument("--window-id", type=int, default=None)
    npc.add_argument("--live", action="store_true")
    npc.add_argument("--danger-confirmed", action="store_true")
    npc.add_argument("--target-pid", type=int, default=None)
    npc.add_argument("--slot", default="F5")
    npc.add_argument("--via-chat", action="store_true")
    npc.add_argument("--npc-name", default="Newbie Guide")
    npc.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))
    npc.add_argument("--out", type=Path, default=None)
    npc.add_argument("--png", type=Path, default=Path("run/npc_dialog_detected.png"))
    npc.add_argument(
        "--runtime-validation",
        action="store_true",
        help="R1: один пункт гида через LiveRuntime, не обходит 6 пунктов, не F85",
    )

    agent = sub.add_parser("agent-live", help="единый LiveRuntime: observe-only, один skill или одна Task, без фарма")
    from l2_brain.live.agent_cli import add_agent_live_arguments

    add_agent_live_arguments(agent)

    menu = sub.add_parser(
        "menu-click-debug",
        help="скан стопки синих HTML-ссылок по кадру; клик только с --go, не R3/R4/R5",
    )
    menu.add_argument("--scan", action="store_true", help="только скан, без HID (это же по умолчанию)")
    menu.add_argument("--go", action="store_true", help="один живой клик по найденному пункту")
    menu.add_argument("--live", action="store_true")
    menu.add_argument("--danger-confirmed", action="store_true")
    menu.add_argument("--window-id", type=int, default=None)
    menu.add_argument("--target-pid", type=int, default=None)
    menu.add_argument("--from-png", type=Path, default=None, help="офлайн кадр, только --scan")
    menu.add_argument("--out", type=Path, default=Path("run/menu-click-debug.json"))
    menu.add_argument("--overlay", type=Path, default=None, help="диагностический PNG: LEFT_PANEL, стопка, клик")
    menu.add_argument("--index", type=int, default=0, help="какой пункт стопки жать при --go")
    menu.add_argument("--profile", type=Path, default=Path("config/window_profiles/parallels_l2.json"))

    args = parser.parse_args(argv)
    if args.cmd == "mock":
        return _run_mock(args, record_path=args.record, default_frames="none")
    if args.cmd == "record":
        return _run_mock(args, record_path=args.out, default_frames="all")
    if args.cmd == "replay":
        return _run_replay(args)
    if args.cmd == "inspect":
        return _run_inspect(args.session, args.tick)
    if args.cmd == "eval":
        from l2_brain.evaluate import main as eval_main

        flags = [
            "--controller",
            args.controller,
            "--scenario",
            args.scenario,
            "--episodes",
            str(args.episodes),
            "--seed",
            str(args.seed),
        ]
        if args.all_controllers:
            flags.append("--all-controllers")
        if args.json_out is not None:
            flags.extend(["--json-out", str(args.json_out)])
        return eval_main(flags)
    if args.cmd == "doctor":
        return _doctor()
    if args.cmd == "sim-eval":
        return _run_sim_eval(args)
    if args.cmd == "capture":
        return _run_capture(args)
    if args.cmd == "vision":
        return _run_vision(args)
    if args.cmd == "baseline-eval":
        return _run_baseline_eval(args)
    if args.cmd == "bench":
        return _run_bench(args)
    if args.cmd == "learn":
        return _run_learn(args)
    if args.cmd == "input-dry-run":
        return _run_input_dry_run(args)
    if args.cmd == "input-probe":
        return _run_input_probe(args)
    if args.cmd == "focus-bench":
        return _run_focus_bench(args)
    if args.cmd == "calibrate-hud":
        return _run_calibrate_hud(args)
    if args.cmd == "calibrate-motion":
        return _run_calibrate_motion(args)
    if args.cmd == "live-motion":
        return _run_live_motion(args)
    if args.cmd == "bench-h8":
        return _run_bench_h8(args)
    if args.cmd == "combat-dry-run":
        return _run_combat_dry_run(args)
    if args.cmd == "spot-loop":
        return _run_spot_loop(args)
    if args.cmd == "profile":
        return _run_profile(args)
    if args.cmd == "malecns-eval":
        return _run_malecns_eval(args)
    if args.cmd == "suite":
        return _run_suite(args)
    if args.cmd == "s4-probe":
        return _run_s4_probe(args)
    if args.cmd == "s4-integrated-spot":
        return _run_s4_integrated_spot(args)
    if args.cmd == "s4-npc-dialog":
        return _run_s4_npc_dialog(args)
    if args.cmd == "layout-grid":
        return _run_layout_grid(args)
    if args.cmd == "layout-overlay":
        return _run_layout_overlay(args)
    if args.cmd == "layout-slots":
        return _run_layout_slots(args)
    if args.cmd == "agent-live":
        return _run_agent_live(args)
    if args.cmd == "menu-click-debug":
        return _run_menu_click_debug(args)
    raise AssertionError(args.cmd)


def _add_run_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ticks", type=int, default=32)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--record", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--frames", choices=("none", "all", "every"), default=None)
    parser.add_argument("--frame-every", type=int, default=1)
    parser.add_argument("--writer-bound", type=int, default=128)
    parser.add_argument("--model-version", default="feature_reactive:default")


def _config_from_args(
    args: argparse.Namespace,
    record_path: Path | None,
    *,
    default_frames: str,
) -> CircuitConfig:
    base = CircuitConfig.from_json_path(args.config) if args.config else CircuitConfig()
    keep = args.frames if args.frames is not None else default_frames
    return CircuitConfig(
        seed=args.seed,
        ticks=args.ticks,
        tick_hz=base.tick_hz,
        frame_h=base.frame_h,
        frame_w=base.frame_w,
        max_intent_age_ns=base.max_intent_age_ns,
        stale_frame_ns=base.stale_frame_ns,
        source_id=base.source_id,
        record_path=record_path,
        log_level=args.log_level,
        strafe_supported=base.strafe_supported,
        keep_frames=keep,
        frame_every=args.frame_every,
        writer_bound=args.writer_bound,
        model_version=args.model_version,
    )


def _run_mock(args: argparse.Namespace, record_path: Path | None, *, default_frames: str) -> int:
    config = _config_from_args(args, record_path, default_frames=default_frames)
    circuit = build_mock_circuit(config)
    records = circuit.run()
    timing = circuit.evaluator.summary()["timing"]
    if record_path is not None:
        if record_path.suffix == ".jsonl":
            write_timing_report(record_path.with_suffix(".timing.json"), timing)
        else:
            write_timing_report(record_path / "timing.json", timing)
    summary = {
        "ticks": len(records),
        "intents": len(records),
        "mock": True,
        "seed": config.seed,
        "record": str(record_path) if record_path else None,
        "pulses": sum(len(r.command.pulses) for r in records),
        "dropped": sum(int(r.command.dropped) for r in records),
        "timing": timing,
        "frame_queue_drops": circuit.evaluator.summary()["frame_queue_drops"],
        "writer_drops": circuit.evaluator.summary()["writer_drops"],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    if args.mode == "offline":
        pairs = replay_recorded_observations(args.session, now_ns=args.now_ns)
        print(
            json.dumps(
                {
                    "ticks": len(pairs),
                    "offline_replay": True,
                    "closed_loop": False,
                    "limitation": OFFLINE_REPLAY_LIMIT,
                    "intents": [
                        {"turn": intent.turn, "forward": intent.forward, "pulses": list(intent.pulses)}
                        for intent, _command in pairs
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    replay = SessionReplay(args.session)
    if args.mode == "step" or args.tick is not None:
        tick = 0 if args.tick is None else args.tick
        print(json.dumps(replay.inspect(tick).to_dict(), ensure_ascii=False))
        return 0
    views = list(replay.play(speed=args.speed, sleep=not args.no_sleep, mode=args.mode))
    print(
        json.dumps(
            {
                "ticks": len(views),
                "mode": args.mode,
                "speed": args.speed,
                "offline_replay": False,
                "closed_loop": False,
                "limitation": OFFLINE_REPLAY_LIMIT,
                "last": views[-1].to_dict() if views else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_inspect(session: Path, tick: int) -> int:
    view = SessionReplay(session).inspect(tick)
    print(json.dumps(view.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _run_capture(args: argparse.Namespace) -> int:
    from l2_brain.capture.helper import diagnose_permission, list_windows, resolve_helper
    from l2_brain.capture.errors import CaptureError, PermissionDenied

    try:
        helper = resolve_helper(args.helper, build=True)
    except CaptureError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    if args.action == "permission":
        try:
            print(json.dumps(diagnose_permission(helper), ensure_ascii=False, indent=2))
            return 0
        except PermissionDenied as exc:
            print(json.dumps({"kind": "permission", "status": "denied", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2
        except CaptureError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    if args.action == "list":
        try:
            print(json.dumps(list_windows(helper), ensure_ascii=False, indent=2))
            return 0
        except CaptureError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    if args.out is None:
        print(json.dumps({"ok": False, "error": "record requires --out"}, ensure_ascii=False))
        return 1
    if not args.self_test and args.window_id is None:
        print(json.dumps({"ok": False, "error": "record requires --window-id or --self-test"}, ensure_ascii=False))
        return 1
    if args.duration is not None:
        return _run_h7_record(args, helper)
    return _record_sck(args, helper)


def _run_h7_record(args: argparse.Namespace, helper: Path) -> int:
    from l2_brain.capture.h7 import run_h7_probe, write_h7_report

    if args.window_id is None:
        print(json.dumps({"ok": False, "error": "H7 probe requires --window-id"}, ensure_ascii=False))
        return 1
    payload = run_h7_probe(
        window_id=int(args.window_id),
        duration_s=float(args.duration),
        fps=int(args.fps),
        profile_path=args.profile,
        helper_path=helper,
    )
    write_h7_report(args.out, payload)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "window_id": payload["window_id"],
                "frames": payload["frames"],
                "median_interval_ms": payload["median_interval_ms"],
                "achieved_fps": payload["achieved_fps"],
                "drops_ratio": payload["drops_ratio"],
                "black_frames_ratio": payload["black_frames_ratio"],
                "capture_latency_ms_p50": payload["capture_latency_ms_p50"],
                "capture_latency_ms_p95": payload["capture_latency_ms_p95"],
                "h7_status": payload["h7_status"],
                "h7_accepted": payload["h7_accepted"],
                "hid_sent": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _record_sck(args: argparse.Namespace, helper: Path) -> int:
    from l2_brain.capture.circuit import build_sck_circuit
    from l2_brain.capture.sck import SCKConfig, SCKFrameSource, capture_metrics

    frames_src = SCKFrameSource(
        SCKConfig(
            helper_path=helper,
            window_id=args.window_id,
            self_test=args.self_test,
            fps=args.fps,
            max_frames=max(args.ticks + 4, args.ticks),
            resize=args.resize,
            profile_path=args.profile,
        )
    )
    config = CircuitConfig(
        seed=0,
        ticks=args.ticks,
        record_path=args.out,
        keep_frames="all",
        log_level=args.log_level,
        source_id="sck.window",
        model_version="feature_reactive:sck",
    )
    circuit = build_sck_circuit(config, frames_src)
    records = circuit.run()
    measured = capture_metrics(
        frames_src,
        [record.observation.timestamp_ns for record in records],
    )
    metrics = {
        "ticks": len(records),
        "mock": False,
        "source": "sck",
        "out": str(args.out),
        "transfer_claim": False,
        **measured,
    }
    if args.out.suffix != ".jsonl":
        write_timing_report(args.out / "timing.json", circuit.evaluator.summary()["timing"])
        (args.out / "capture-metrics.json").write_text(
            json.dumps({**metrics, **measured}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


def _doctor() -> int:
    from l2_brain.capture.helper import default_helper_path

    helper = default_helper_path()
    report = {
        "l2_brain": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": _numpy_version(),
        "accel": selected_backend(),
        "game_client": "not_connected",
        "screencapturekit_in_loop": False,
        "screencapturekit_helper": str(helper) if helper.is_file() else None,
        "sck_minimum": "12.3",
        "note": "doctor не захватывает экран и не открывает клиент; permission — l2-brain capture permission",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _run_sim_eval(args: argparse.Namespace) -> int:
    from l2_brain.sim.suite import idle_policy, run_catalog, write_results

    scenarios = tuple(args.scenario) if args.scenario else None
    results = run_catalog(
        args.seed,
        idle_policy,
        split=args.split,
        scenarios=scenarios,
        max_steps=args.max_steps,
    )
    write_results(
        args.out,
        results,
        extras={"policy": "idle", "max_steps": args.max_steps, "headless": True},
    )
    print(
        json.dumps(
            {
                "episodes": len(results),
                "successes": sum(int(item.success) for item in results),
                "out": str(args.out),
                "transfer_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_baseline_eval(args: argparse.Namespace) -> int:
    from l2_brain.control.config import BaselineConfig
    from l2_brain.control.eval import compare_rows, run_catalog, write_report

    if args.controller == "snn" and not args.scenario:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "snn sandbox requires --scenario; Frozen 60 is not this step",
                },
                ensure_ascii=False,
            )
        )
        return 2
    config = BaselineConfig(recovery=not args.no_recovery, channels=args.channels)
    encoder_name = args.encoder
    channel_label = "blob" if encoder_name == "color_blob" else args.channels
    policy = None
    controller_name = "baseline_v1" if args.no_recovery else "baseline_memory_v1"
    if args.controller == "snn":
        from l2_brain.control.snn import LIFConfig, SNNController

        policy = SNNController(LIFConfig(seed=args.seed))
        controller_name = "snn_core_v1"
    rows = run_catalog(
        args.seed,
        config=config,
        split=args.split,
        scenarios=tuple(args.scenario) if args.scenario else None,
        max_steps=args.max_steps,
        suite=args.suite,
        encoder_name=encoder_name,
        controller=policy,
    )
    extras: dict = {
        "config": config.to_dict(),
        "snn": policy.config.to_dict() if policy is not None else None,
        "max_steps": args.max_steps,
        "suite": args.suite,
        "split": args.split,
        "held_out_used_for_tuning": False,
        "held_out_independent": False,
        "controller": controller_name,
        "encoder_name": encoder_name,
        "channels": channel_label,
        "biological_claim": False,
        "learned": False,
    }
    if args.compare is not None:
        prior = json.loads(args.compare.read_text(encoding="utf-8"))
        extras["compare"] = compare_rows(prior.get("episodes", []), rows)
    payload = write_report(
        args.out,
        rows,
        extras=extras,
    )
    print(
        json.dumps(
            {
                "episodes": payload["summary"]["n"],
                "successes": payload["summary"]["successes"],
                "outcomes": payload["summary"]["outcomes"],
                "causes": payload["summary"]["causes"],
                "recovery": payload["summary"].get("recovery"),
                "compare": extras.get("compare"),
                "out": str(args.out),
                "transfer_claim": False,
                "learned": False,
                "biological_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_bench(args: argparse.Namespace) -> int:
    from l2_brain.control.bench import format_table, run_bench, write_bench

    rows = run_bench(scenario=args.scenario, split=args.split, variant=args.variant, seed=args.seed)
    payload = write_bench(
        args.out,
        rows,
        extras={
            "seed": args.seed,
            "scenario": args.scenario,
            "split": args.split,
            "variant": args.variant,
            "accounting": {
                "baseline_n_params": "numeric BaselineConfig fields, not network weights",
                "gru_n_params": "dense GRU + linear head; W_out is zero when residual_scale=0",
                "snn_n_params": "dense stored w_rec + w_in; conceptual sparsity not subtracted",
                "snn_state_floats": "V and I_syn only (2*n); traces not counted",
                "k_substeps": "GRU and baseline K=1; SNN K=steps_per_tick",
            },
            "not_a_claim": "n=1 open_goal. Not Frozen 60. Not H3/H4. Not catalog ranking.",
        },
    )
    print(format_table(rows))
    print(json.dumps({"out": str(args.out), "n": len(payload["rows"]), "transfer_claim": False}, ensure_ascii=False))
    return 0


def _run_learn(args: argparse.Namespace) -> int:
    from l2_brain.learning.train import run_rstdp_series, write_learn_report

    payload = run_rstdp_series(
        scenario=args.scenario,
        split=args.split,
        variant=args.variant,
        seed=args.seed,
        episodes=args.episodes,
        noise=args.noise,
    )
    write_learn_report(args.out, payload)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "control_ticks": payload["control"]["ticks"],
                "eval_ticks": payload["eval_frozen"]["ticks"],
                "train_ticks": [row["ticks"] for row in payload["train"]],
                "improved": payload["improved"],
                "transfer_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_focus_bench(args: argparse.Namespace) -> int:
    from l2_brain.io.cgevent_backend import CGEventInputBackend, RecordingPoster
    from l2_brain.io.focus import bench_focus, is_allowed_frontmost
    from l2_brain.io.actions import HoldKey
    from l2_brain.experiment.clocks import mono_ns

    focus = bench_focus(repeats=int(args.repeats))
    poster = RecordingPoster()
    backend = CGEventInputBackend(
        1,
        live_confirmed=True,
        live_danger_confirmed=True,
        poster=poster,
        focus_probe=is_allowed_frontmost,
    )
    act: list[float] = []
    for _ in range(20):
        t0 = mono_ns()
        backend.send_action(HoldKey(key="1", state="down"))
        backend.send_action(HoldKey(key="1", state="up"))
        act.append((mono_ns() - t0) / 1_000_000.0)
    ordered = sorted(act)
    payload = {
        "hid_sent": False,
        "focus": focus,
        "act_ms_p50": ordered[len(ordered) // 2],
        "act_ms_p95": ordered[int(round(0.95 * (len(ordered) - 1)))],
        "osascript": False,
        "live_input": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), **payload}, ensure_ascii=False))
    return 0


def _run_calibrate_motion(args: argparse.Namespace) -> int:
    from l2_brain.calibration.motion_calibrator import (
        DEFAULT_OUT_KLT,
        DEFAULT_OUT_V2,
        DEFAULT_OUT_SYNC,
        DEFAULT_OUT_V3,
        run_klt_yaw_calibration,
        run_motion_calibration,
        run_sync_diag_calibration,
        run_v3_yaw_calibration,
    )

    if args.sync_diag:
        out = args.out
        if Path(out) == Path("docs/evidence/live-s4/motion-calibration.json"):
            out = DEFAULT_OUT_SYNC
        payload = run_sync_diag_calibration(
            live=bool(args.live),
            danger_confirmed=bool(args.danger_confirmed),
            window_id=args.window_id,
            target_pid=args.target_pid,
            profile_path=args.profile,
            out_path=out,
            write_profile=bool(args.write_profile),
        )
        print(
            json.dumps(
                {
                    "out": str(out),
                    "ok": payload.get("ok"),
                    "aborted": payload.get("aborted"),
                    "mechanism": payload.get("mechanism"),
                    "diff_mean": payload.get("diff_mean"),
                    "time_delta_ms": payload.get("time_delta_ms"),
                    "klt_median_dx": payload.get("klt_median_dx"),
                    "unique_frame": payload.get("unique_frame"),
                    "shares_memory": payload.get("shares_memory"),
                    "identical_frames_error": payload.get("identical_frames_error"),
                    "sck_desync": payload.get("sck_desync"),
                    "physical": payload.get("physical"),
                    "q5_closed": payload.get("q5_closed"),
                    "dumps": payload.get("dumps"),
                    "profile_written": payload.get("profile_written"),
                    "stuck_keys_count": payload.get("stuck_keys_count"),
                    "session_ms": payload.get("session_ms"),
                },
                ensure_ascii=False,
            )
        )
        if payload.get("aborted") == "live_flags_required":
            return 2
        if payload.get("ok") and payload.get("physical"):
            return 0
        return 3

    if args.rmb:
        out = args.out
        if Path(out) == Path("docs/evidence/live-s4/motion-calibration.json"):
            out = DEFAULT_OUT_V3
        payload = run_v3_yaw_calibration(
            live=bool(args.live),
            danger_confirmed=bool(args.danger_confirmed),
            window_id=args.window_id,
            target_pid=args.target_pid,
            profile_path=args.profile,
            out_path=out,
            write_profile=bool(args.write_profile),
            mouse_dx=float(args.mouse_dx),
            mouse_dy=float(args.mouse_dy),
            rmb_steps=int(args.rmb_steps),
            rmb_step_s=max(int(args.rmb_step_ms), 1) / 1000.0,
            arrow_taps=int(args.arrow_taps),
            arrow_hold_ms=int(args.arrow_hold_ms),
        )
        print(
            json.dumps(
                {
                    "out": str(out),
                    "ok": payload.get("ok"),
                    "aborted": payload.get("aborted"),
                    "algorithm": "klt_ransac",
                    "mechanism": payload.get("mechanism"),
                    "median_dx": payload.get("median_dx"),
                    "total_features": payload.get("total_features"),
                    "valid_inliers": payload.get("valid_inliers"),
                    "inlier_ratio": payload.get("inlier_ratio"),
                    "px_cam_per_px_mouse": payload.get("px_cam_per_px_mouse"),
                    "deg_per_mouse_px": payload.get("deg_per_mouse_px"),
                    "physical": payload.get("physical"),
                    "reliable": payload.get("reliable"),
                    "q5_closed": payload.get("q5_closed"),
                    "profile_written": payload.get("profile_written"),
                    "stuck_keys_count": payload.get("stuck_keys_count"),
                    "watchdog_tripped": payload.get("watchdog_tripped"),
                    "session_ms": payload.get("session_ms"),
                },
                ensure_ascii=False,
            )
        )
        if payload.get("aborted") == "live_flags_required":
            return 2
        if payload.get("ok") and payload.get("physical"):
            return 0
        return 3

    if args.klt:
        out = args.out
        if Path(out) == Path("docs/evidence/live-s4/motion-calibration.json"):
            out = DEFAULT_OUT_KLT
        payload = run_klt_yaw_calibration(
            live=bool(args.live),
            danger_confirmed=bool(args.danger_confirmed),
            window_id=args.window_id,
            target_pid=args.target_pid,
            profile_path=args.profile,
            out_path=out,
            write_profile=bool(args.write_profile),
        )
        print(
            json.dumps(
                {
                    "out": str(out),
                    "ok": payload.get("ok"),
                    "aborted": payload.get("aborted"),
                    "algorithm": "klt_ransac",
                    "right": payload.get("right"),
                    "left": payload.get("left"),
                    "deg_per_sec_right": payload.get("deg_per_sec_right"),
                    "deg_per_sec_left": payload.get("deg_per_sec_left"),
                    "symmetry_ok": payload.get("symmetry_ok"),
                    "reliable": payload.get("reliable"),
                    "q5_closed": payload.get("q5_closed"),
                    "profile_written": payload.get("profile_written"),
                    "stuck_keys_count": payload.get("stuck_keys_count"),
                    "watchdog_tripped": payload.get("watchdog_tripped"),
                    "session_ms": payload.get("session_ms"),
                },
                ensure_ascii=False,
            )
        )
        if payload.get("aborted") == "live_flags_required":
            return 2
        if payload.get("ok") and payload.get("reliable"):
            return 0
        return 3

    band = args.band or ("horizon" if args.horizon else "center")
    horizon = band == "horizon"
    out = args.out
    if horizon and Path(out) == Path("docs/evidence/live-s4/motion-calibration.json"):
        out = DEFAULT_OUT_V2
    payload = run_motion_calibration(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        profile_path=args.profile,
        out_path=out,
        write_profile=False if horizon else bool(args.write_profile or (args.live and args.danger_confirmed)),
        band=band,
        skip_walk=True if horizon else None,
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "crop_band": payload.get("crop_band"),
                "yaw_shift_px": payload.get("yaw_shift_px"),
                "yaw_peak": payload.get("yaw_peak"),
                "deg_per_sec": payload.get("deg_per_sec"),
                "peak_reliable": payload.get("peak_reliable"),
                "q5_horizon_ok": payload.get("q5_horizon_ok"),
                "q5_closed": False,
                "step_px_per_sec": payload.get("step_px_per_sec"),
                "motion_detected": payload.get("motion_detected"),
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "watchdog_tripped": payload.get("watchdog_tripped"),
                "h8_closed": False,
                "session_ms": payload.get("session_ms"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if horizon:
        if payload.get("ok") and payload.get("peak_reliable"):
            return 0
        return 3
    if payload.get("ok") and payload.get("motion_detected"):
        return 0
    return 3


def _run_live_motion(args: argparse.Namespace) -> int:
    from l2_brain.bench.live_motion_probe import run_live_motion_probe

    payload = run_live_motion_probe(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        profile_path=args.profile,
        out_path=args.out,
        free_ticks=int(args.free_ticks),
        blocked_ticks=int(args.blocked_ticks),
        hold_ms=int(args.hold_ms),
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "flow_free_motion": payload.get("flow_free_motion"),
                "flow_blocked": payload.get("flow_blocked"),
                "flow_ratio": payload.get("flow_ratio"),
                "expansion_free": payload.get("expansion_free"),
                "expansion_blocked": payload.get("expansion_blocked"),
                "stuck_detected": payload.get("stuck_detected"),
                "l1_collision_signal_ready": payload.get("l1_collision_signal_ready"),
                "encode": payload.get("encode"),
                "profile_written": None,
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "session_ms": payload.get("session_ms"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if payload.get("ok") and payload.get("stuck_detected"):
        return 0
    return 3


def _run_bench_h8(args: argparse.Namespace) -> int:
    from l2_brain.bench.h8_latency_bench import run_h8_bench

    payload = run_h8_bench(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        samples=int(args.samples),
        warmup=int(args.warmup),
        profile_path=args.profile,
        out_path=args.out,
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "h8": payload.get("h8"),
                "pipeline": payload.get("pipeline"),
                "observe": payload.get("observe"),
                "parse": payload.get("parse"),
                "encode": payload.get("encode"),
                "infer": payload.get("infer"),
                "act": payload.get("act"),
                "h8_p95_ms": payload.get("h8_p95_ms"),
                "h8_accepted": payload.get("h8_accepted"),
                "h8_closed": payload.get("h8_closed"),
                "hid_sent": payload.get("hid_sent"),
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "watchdog_tripped": payload.get("watchdog_tripped"),
                "session_ms": payload.get("session_ms"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if payload.get("ok") and payload.get("h8_closed"):
        return 0
    return 3


def _run_calibrate_hud(args: argparse.Namespace) -> int:
    from l2_brain.vision.calibrate_hud import run_calibrate_hud

    payload = run_calibrate_hud(
        window_id=args.window_id,
        profile_path=args.profile,
        out_dir=args.out_dir,
        tag=args.tag,
        image_path=args.from_png,
    )
    tag = (getattr(args, "tag", None) or "").strip()
    if args.from_png is not None:
        report_name = f"calibrate-hud-{tag}.json" if tag else "calibrate-hud-offline.json"
    elif tag == "interlude_active":
        report_name = "calibrate-hud-interlude.json"
    else:
        report_name = "calibrate-hud.json"
    report = args.out_dir / report_name
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(report), **{k: payload.get(k) for k in ("ok", "window_id", "width", "height", "hid_sent", "reason")}}, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


def _run_input_probe(args: argparse.Namespace) -> int:
    from l2_brain.io.cgevent_backend import CGEventInputBackend, LiveInputNotConfirmed, RecordingPoster
    from l2_brain.io.focus import is_allowed_frontmost
    from l2_brain.io.notepad_probe import activate_parallels, ensure_notepad, guest_tasklist, game_process_present, run_notepad_scenario

    args.out.parent.mkdir(parents=True, exist_ok=True)
    guest = ensure_notepad(args.vm_name)
    live = bool(args.live and args.live_confirmed)
    if args.live and not args.live_confirmed:
        payload = {
            "hid_sent": False,
            "aborted": "live_confirmed_required",
            "guest": guest,
            "transfer_claim": False,
        }
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"out": str(args.out), **payload}, ensure_ascii=False))
        return 2
    if live and not guest.get("ok"):
        payload = {
            "hid_sent": False,
            "aborted": guest.get("reason"),
            "guest": guest,
            "live": True,
            "transfer_claim": False,
        }
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"out": str(args.out), "aborted": payload["aborted"], "hid_sent": False}, ensure_ascii=False))
        return 2
    if live:
        listing = guest_tasklist(args.vm_name)
        if game_process_present(listing):
            payload = {
                "hid_sent": False,
                "aborted": "game_process_present",
                "guest": guest,
                "live": True,
                "transfer_claim": False,
            }
            args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"out": str(args.out), "aborted": "game_process_present", "hid_sent": False}, ensure_ascii=False))
            return 2
        activate_parallels()
    try:
        backend = CGEventInputBackend(
            int(args.target_pid),
            live_confirmed=True,
            live_danger_confirmed=True,
            poster=None if live else RecordingPoster(),
            focus_probe=(lambda: is_allowed_frontmost()) if live else (lambda: True),
        )
    except LiveInputNotConfirmed as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    result = run_notepad_scenario(backend)
    payload = {
        "live": live,
        "target_pid": int(args.target_pid),
        "guest": guest,
        "game_client": False,
        "transfer_claim": False,
        **result,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "live": live,
                "hid_sent": payload.get("hid_sent"),
                "aborted": payload.get("aborted"),
                "act_ms_p50": payload.get("act_ms_p50"),
                "act_ms_p95": payload.get("act_ms_p95"),
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "watchdog_tripped": payload.get("watchdog_tripped"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload.get("aborted") is None else 3


def _run_s4_probe(args: argparse.Namespace) -> int:
    from l2_brain.live.s4_probe import (
        CLEAN_OUT,
        DEFAULT_OUT,
        ENGAGE_OUT,
        KILL_OUT,
        MULTI_OUT,
        SEARCH_OUT,
        run_s4_probe,
    )

    out = args.out
    if out is None:
        if args.verify_search:
            out = SEARCH_OUT
        elif int(args.multi_kill or 0) > 0:
            out = MULTI_OUT
        elif args.kill_and_loot:
            out = KILL_OUT
        elif args.engage_any:
            out = ENGAGE_OUT
        elif args.clean_target:
            out = CLEAN_OUT
        else:
            out = DEFAULT_OUT
    payload = run_s4_probe(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        profile_path=args.profile,
        out_path=out,
        clean_target=bool(args.clean_target),
        engage_any=bool(args.engage_any),
        kill_and_loot=bool(args.kill_and_loot),
        multi_kill=int(args.multi_kill or 0),
        verify_search=bool(args.verify_search),
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "hid_sent": payload.get("hid_sent"),
                "target_locked": payload.get("target_locked"),
                "damage_detected": payload.get("damage_detected"),
                "start_self_hp": payload.get("start_self_hp"),
                "initial_target_hp": payload.get("initial_target_hp"),
                "final_target_hp": payload.get("final_target_hp"),
                "f1_to_lock_ms": payload.get("f1_to_lock_ms"),
                "f2_to_hp_drop_ms": payload.get("f2_to_hp_drop_ms"),
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "watchdog_tripped": payload.get("watchdog_tripped"),
                "ticks": payload.get("ticks"),
                "session_ms": payload.get("session_ms"),
                "clean_target": payload.get("clean_target"),
                "engage_any": payload.get("engage_any"),
                "kill_and_loot": payload.get("kill_and_loot"),
                "multi_kill": payload.get("multi_kill"),
                "kills_completed": payload.get("kills_completed"),
                "loot_actions_sent": payload.get("loot_actions_sent"),
                "target_killed": payload.get("target_killed"),
                "loot_pickup_sent": payload.get("loot_pickup_sent"),
                "time_to_kill_ms": payload.get("time_to_kill_ms"),
                "f2_pulses": payload.get("f2_pulses"),
                "total_session_ms": payload.get("total_session_ms"),
                "verify_search": payload.get("verify_search"),
                "search_maneuver_executed": payload.get("search_maneuver_executed"),
                "rotation_sent": payload.get("rotation_sent"),
                "walk_step_sent": payload.get("walk_step_sent"),
                "target_acquired_after_search": payload.get("target_acquired_after_search"),
                "rotation_type": payload.get("rotation_type"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if args.verify_search:
        ok = bool(
            payload.get("ok")
            and payload.get("rotation_sent")
            and payload.get("target_killed")
            and payload.get("loot_pickup_sent")
        )
    elif int(args.multi_kill or 0) > 0:
        wanted = min(max(int(args.multi_kill), 0), 3)
        ok = bool(payload.get("ok") and payload.get("kills_completed") == wanted)
    elif args.kill_and_loot:
        ok = bool(payload.get("ok") and payload.get("target_killed") and payload.get("loot_pickup_sent"))
    else:
        needs_damage = bool(args.clean_target or args.engage_any)
        ok = bool(payload.get("ok") and (not needs_damage or payload.get("damage_detected")))
    if ok:
        return 0
    return 3


def _run_layout_grid(args: argparse.Namespace) -> int:
    from l2_brain.tools.layout_calibrator import run_layout_grid

    payload = run_layout_grid(
        save_path=args.save,
        window_id=args.window_id,
        profile_path=args.profile,
        image_path=args.from_png,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


def _run_layout_overlay(args: argparse.Namespace) -> int:
    from l2_brain.tools.layout_overlay import run_layout_overlay

    payload = run_layout_overlay(
        window_id=args.window_id,
        profile_path=args.profile,
        seconds=float(args.seconds),
        show=not bool(args.no_show),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


def _run_layout_slots(args: argparse.Namespace) -> int:
    from l2_brain.live.layout_slots_probe import run_layout_slots_probe

    payload = run_layout_slots_probe(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        profile_path=args.profile,
        out_path=args.out,
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "slot_a": payload.get("slot_a"),
                "slot_b": payload.get("slot_b"),
                "clean_free": payload.get("clean_free"),
                "after_tab_occupied": payload.get("after_tab_occupied"),
                "after_escape_free": payload.get("after_escape_free"),
                "escapes_sent": payload.get("escapes_sent"),
                "farm": payload.get("farm"),
                "elapsed_time_sec": payload.get("elapsed_time_sec"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    return 0 if payload.get("ok") else 3


def _run_s4_npc_dialog(args: argparse.Namespace) -> int:
    from l2_brain.live.npc_dialog_probe import DEFAULT_OUT, run_npc_dialog_probe
    from l2_brain.live.runtime_validation import NPC_OUT, print_banner

    validation = bool(getattr(args, "runtime_validation", False))
    out = args.out or (NPC_OUT if validation else DEFAULT_OUT)
    if validation:
        print_banner(
            mode="NPC",
            window_id=args.window_id,
            target_pid=args.target_pid,
            kill_cap=None,
            live=bool(args.live),
            danger_confirmed=bool(args.danger_confirmed),
        )
    payload = run_npc_dialog_probe(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        slot=str(args.slot),
        via_chat=bool(args.via_chat),
        runtime_validation=validation,
        npc_name=str(args.npc_name),
        profile_path=args.profile,
        out_path=out,
        png_path=args.png,
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "target_acquired": payload.get("target_acquired"),
                "approach_time_sec": payload.get("approach_time_sec"),
                "dialog_detected": payload.get("dialog_detected"),
                "dialog_confidence": payload.get("dialog_confidence"),
                "click_dispatched": payload.get("click_dispatched"),
                "talk_clicks": payload.get("talk_clicks"),
                "quest_link_clicks": payload.get("quest_link_clicks"),
                "guide_link_count": payload.get("guide_link_count"),
                "guide_items_opened": payload.get("guide_items_opened"),
                "total_items_found": payload.get("total_items_found"),
                "items_clicked": payload.get("items_clicked"),
                "menu_item_xy": payload.get("menu_item_xy"),
                "false_target_markers": payload.get("false_target_markers"),
                "f2_approach": payload.get("f2_approach"),
                "chat_target_success": payload.get("chat_target_success"),
                "dialog_opened_from_closed": payload.get("dialog_opened_from_closed"),
                "sck_crashes": payload.get("sck_crashes"),
                "elapsed_time_sec": payload.get("elapsed_time_sec"),
                "capture_restarts": payload.get("capture_restarts"),
                "capture_error": payload.get("capture_error"),
                "farm": payload.get("farm"),
                "parse_dialog": payload.get("parse_dialog"),
                "architecture": payload.get("architecture"),
                "runtime_used": payload.get("runtime_used"),
                "validation_result": payload.get("validation_result"),
                "dialog_closed": payload.get("dialog_closed"),
                "capture_recovery_used": payload.get("capture_recovery_used"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if payload.get("ok"):
        return 0
    return 3


def _run_s4_integrated_spot(args: argparse.Namespace) -> int:
    from l2_brain.live.spot_loop import DEFAULT_OUT, KILL_CAP, run_integrated_spot
    from l2_brain.live.runtime_validation import COMBAT_OUT, print_banner

    validation = bool(getattr(args, "runtime_validation", False))
    out = args.out or (COMBAT_OUT if validation else DEFAULT_OUT)
    timeout_s = None if args.no_timeout or args.timeout is None else float(args.timeout)
    if validation:
        print_banner(
            mode="Combat",
            window_id=args.window_id,
            target_pid=args.target_pid,
            kill_cap=int(args.kills),
            live=bool(args.live),
            danger_confirmed=bool(args.danger_confirmed),
        )
    payload = run_integrated_spot(
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        profile_path=args.profile,
        out_path=out,
        kills=int(args.kills),
        timeout_s=timeout_s,
        runtime_validation=validation,
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "ok": payload.get("ok"),
                "aborted": payload.get("aborted"),
                "total_kills": payload.get("total_kills"),
                "kills_completed": payload.get("kills_completed"),
                "roam_cycles": payload.get("roam_cycles"),
                "l1_triggers": payload.get("l1_triggers"),
                "l1_stuck_triggers": payload.get("l1_stuck_triggers"),
                "aggro_interrupts": payload.get("aggro_interrupts"),
                "aggro_triggers": payload.get("aggro_triggers"),
                "u_turns_executed": payload.get("u_turns_executed"),
                "u_turns": payload.get("u_turns"),
                "elapsed_time_sec": payload.get("elapsed_time_sec"),
                "total_time_sec": payload.get("total_time_sec"),
                "avg_combat_sec": payload.get("avg_combat_sec"),
                "stuck_keys_count": payload.get("stuck_keys_count"),
                "stuck_keys": payload.get("stuck_keys"),
                "watchdog_tripped": payload.get("watchdog_tripped"),
                "farm": payload.get("farm"),
                "e2e_p95_ms": payload.get("e2e_p95_ms"),
                "architecture": payload.get("architecture"),
                "runtime_used": payload.get("runtime_used"),
                "validation_result": payload.get("validation_result"),
                "f2_input_count": payload.get("f2_input_count"),
                "attack_skill_success": payload.get("attack_skill_success"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if validation and payload.get("validation_result") == "PASS":
        return 0
    wanted = min(max(int(args.kills), 1), KILL_CAP)
    if payload.get("ok") and int(payload.get("kills_completed") or 0) == wanted:
        return 0
    return 3


def _run_input_dry_run(args: argparse.Namespace) -> int:
    from l2_brain.contracts import MotorIntent
    from l2_brain.io import DryRunInputBackend, GameInputProfile, IntentDecoder

    profile = GameInputProfile(move_mode=args.move_mode)
    backend = DryRunInputBackend(profile)
    decoder = IntentDecoder(profile)
    intents = (
        MotorIntent(0.25, 0.8, "idle", "idle", "idle", 0.6, 10**12),
        MotorIntent(-0.40, 0.2, "idle", "idle", "idle", 0.6, 10**12),
        MotorIntent(0.0, 0.0, "idle", "fire", "idle", 0.6, 10**12),
        MotorIntent(0.0, 0.0, "idle", "idle", "fire", 0.6, 10**12),
        MotorIntent(0.0, 0.0, "fire", "idle", "idle", 0.6, 10**12),
    )
    for intent in intents:
        for action in decoder.decode(intent):
            backend.send_action(action)
    payload = {
        "dry_run": True,
        "hid_sent": False,
        "live_input": False,
        "profile": profile.to_dict(),
        "events": backend.events(),
        "transfer_claim": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "n": len(backend.log), "hid_sent": False}, ensure_ascii=False))
    return 0


def _run_spot_loop(args: argparse.Namespace) -> int:
    from l2_brain.sim.spot_arena import run_spot_loop

    payload = run_spot_loop(ticks=args.ticks, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "scenario": payload["scenario"],
                "outcome": payload["outcome"],
                "ticks": payload["ticks"],
                "kills": payload["kills"],
                "loot_collected": payload["loot_collected"],
                "max_kill_streak": payload["max_kill_streak"],
                "phases": payload["phases"],
                "watchdog_resets": payload["watchdog_resets"],
                "hid_sent": False,
                "transfer_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_combat_dry_run(args: argparse.Namespace) -> int:
    from l2_brain.sim.combat import run_combat_episode

    payload = run_combat_episode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "outcome": payload["outcome"],
                "ticks": payload["ticks"],
                "phases": payload["phases"],
                "dummy_killed": payload["dummy_killed"],
                "hid_sent": False,
                "transfer_claim": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_suite(args: argparse.Namespace) -> int:
    from l2_brain.bench.suite_runner import main as suite_main

    return suite_main(["--seed", str(args.seed), "--out", str(args.out)])


def _run_malecns_eval(args: argparse.Namespace) -> int:
    from l2_brain.control.malecns.compare import format_table, run_malecns_compare, write_comparison

    rows = run_malecns_compare(seed=args.seed)
    payload = write_comparison(args.out, rows)
    print(format_table(rows))
    print(
        json.dumps(
            {
                "out": str(args.out),
                "episode_id": payload["episode_id"],
                "extract": payload["extract"],
                "bio_ticks_lt_shuffled": payload["bio_ticks_lt_shuffled"],
                "h11_claim": False,
                "full_connectome_loaded": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_profile(args: argparse.Namespace) -> int:
    from l2_brain.bench.mps_audit import run_audit
    from l2_brain.bench.profiler import run_profile, write_profile

    payload = run_profile(ticks=args.ticks, warmup=args.warmup, seed=args.seed)
    payload["mps_audit"] = run_audit(steps=200)
    snn = next(row for row in payload["rows"] if row["controller"] == "snn_v1")
    infer_p95 = float(snn["stages"]["t_infer"]["p95_ms"])
    mps_b1 = bool(payload["mps_audit"]["mps_faster_at_n64_b1"])
    payload["verdict"] = {
        "keep_numpy_cpu": True,
        "h6_accepted": False,
        "reason": (
            "H6 needs infer p95 CPU >= 2 ms and MPS p50 < CPU p50 at B=1. "
            f"measured infer_p95_snn={infer_p95:.3f} mps_faster_n64_b1={mps_b1}"
        ),
        "optimized": False,
    }
    write_profile(args.out, payload)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "controllers": [row["controller"] for row in payload["rows"]],
                "snn_infer_p95_ms": infer_p95,
                "mps_faster_n64_b1": mps_b1,
                "keep_numpy_cpu": True,
                "optimized": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_vision(args: argparse.Namespace) -> int:
    from l2_brain.vision.bench import checker, encode_pair, measure_configs, pick_starter, shift
    from l2_brain.vision.config import STARTER, VisionConfig
    from l2_brain.vision.diagnose import write_ppm
    from l2_brain.vision.encoder import NavigationEncoder

    if args.action == "bench":
        rows = measure_configs(repeats=args.repeats)
        chosen = pick_starter(rows)
        payload = {
            "candidates": rows,
            "picked": chosen,
            "starter": {"width": STARTER.width, "height": STARTER.height, "sectors_x": STARTER.sectors_x},
            "no_object_model": True,
            "limitation": "synthetic discrimination; not MMORPG transfer",
        }
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    enc = NavigationEncoder(VisionConfig(diagnose=True))
    enc.initialize()
    image = checker()
    enc.encode(_vision_frame(image, 1), (), None, 1, False)
    enc.encode(_vision_frame(shift(image, 4), 2), (), None, 2, False)
    dest = args.out or Path("run/vision-diag.ppm")
    assert enc.last_diag is not None
    write_ppm(dest, enc.last_diag)
    print(
        json.dumps(
            {
                "out": str(dest),
                "label": enc.last_channels.hypothesis.label if enc.last_channels else None,
                "expansion": enc.last_channels.expansion if enc.last_channels else None,
                "motion_confidence": enc.last_channels.motion_confidence if enc.last_channels else None,
            },
            ensure_ascii=False,
        )
    )
    enc.close()
    return 0


def _run_menu_click_debug(args: argparse.Namespace) -> int:
    from l2_brain.live.menu_click_debug import run_menu_click_debug

    payload = run_menu_click_debug(
        scan=bool(args.scan) or not bool(args.go),
        go=bool(args.go),
        live=bool(args.live),
        danger_confirmed=bool(args.danger_confirmed),
        window_id=args.window_id,
        target_pid=args.target_pid,
        from_png=args.from_png,
        out_path=args.out,
        overlay_path=args.overlay,
        index=int(args.index),
    )
    print(
        json.dumps(
            {
                "out": payload.get("out"),
                "ok": payload.get("ok"),
                "mode": payload.get("mode"),
                "aborted": payload.get("aborted"),
                "hid_sent": payload.get("hid_sent"),
                "validation_result": payload.get("validation_result"),
                "found": (payload.get("stack") or {}).get("found"),
                "click_xy": payload.get("click_xy"),
                "default_items": payload.get("default_items"),
                "menu_changed": payload.get("menu_changed"),
                "farm": payload.get("farm"),
                "canon": payload.get("canon"),
            },
            ensure_ascii=False,
        )
    )
    if payload.get("aborted") == "live_flags_required":
        return 2
    if payload.get("aborted") in {"canon_path_forbidden", "png_not_for_go"}:
        return 2
    return 0 if payload.get("ok") else 3


def _run_agent_live(args: argparse.Namespace) -> int:
    from l2_brain.live.agent_cli import run_agent_live

    return run_agent_live(args)


def _vision_frame(image, frame_id: int):
    from l2_brain.vision.bench import make_frame

    return make_frame(image, frame_id)


def _numpy_version() -> str:
    import numpy as np

    return np.__version__


if __name__ == "__main__":
    raise SystemExit(main())
