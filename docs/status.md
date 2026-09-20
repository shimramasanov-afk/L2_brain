# Статус

Обзор для решения «куда дальше»:
[overview-2026-09-18.md](overview-2026-09-18.md).

## Ход 97 — скан стопки меню, без live — 2026-09-20

Код и unit-тесты. Live HID не было. Дефолтный `LEFT_PANEL`
не меняли. R1/R2 и F82/F85/F86 не переписывали. Канон R3/R4/R5
не писали.

Новый `scan_menu_stack`: синие HTML-ссылки по всему кадру,
клик `(x0+70, y0-14)` от верха стопки. CLI
`menu-click-debug --scan` (и `--from-png`) без HID.
`--go` требует dual flags; PASS только если меню изменилось.
Синие иконки могут дать ложную стопку. Это не «агент найдёт
что угодно».

```text
MENU_STACK_SCAN = UNIT-TESTED
LIVE_VALIDATION = NO
TASK_LAYER_STATUS = UNIT-TESTED
LiveRuntime execution path = LIVE-VALIDATED
Long-horizon Agent/Task layer = NOT YET LIVE-VALIDATED
```

Не PASS сдвинутого гида в клиенте. Проверка у оператора:
сдвинуть окно → `--scan` → «го» / `--go`.

## Ход 96 — Task layer v1, без live — 2026-09-18

Код и unit-тесты. Live HID не было. F82/F85/F86 и R1/R2 JSON
не переписывали. Combat/HUD/loot не трогали.

Появились `Task` / `TaskResult` / `TaskRunner` /
`GuideInteractionTask`. Задача ходит только в публичный
Skill/LiveRuntime API: `open_npc_dialog` + `close_dialog`.
FSM явная. Один retry. Trace JSON. `agent-live --task guide-open-close`
(`--repeat` default 1, cap 10). Без `--task` — observe-only.
Старые `s4-npc-dialog` / `s4-integrated-spot` на месте.

```text
TASK_LAYER_STATUS = UNIT-TESTED
LIVE_VALIDATION = NO
POST_TASK_LAYER_TESTS = 389 passed, 0 failed
LiveRuntime execution path = LIVE-VALIDATED
Long-horizon Agent/Task layer = NOT YET LIVE-VALIDATED
```

Не «agent LIVE-PROVEN». Не PASS гида в клиенте. Следующая
проверка (отдельная команда): GuideInteractionTask ×3 live.

## Ход 95 — увеличенный HUD + live R2 PASS — 2026-09-18

Live HID был. F82/F85/F86 не переписывали. Prompt 8 нет.

Оператор увеличил графики своего HP и HP моба. Кадр
`client-reference-hod95.png`: self HP 31,151,582,155.
ADR-0083 (F3 после слепого F2), ADR-0084 (новые ROI).

R2 (`R2-runtime-combat.json`): **PASS**, 113.0 с, окно 18733,
PID 68342. Киллов **3**. `f2_input_count=18`.
`loot_skill_runs=7`, `loot_actions_sent=21` (F3 и после килла,
и `via=after_f2`). Self HP 1.0 / 0.97 / 1.0.
`stuck_keys=0`, `focus_lost=false`, `release_all` да.
SHA1 `be12db2b…`. Предыдущий FAIL — attempt6.

Килл 2: `blind_engage` → `target_dead` за 0.03 с, HP 0→0 —
возможен кредит пустой пластины, не отдельное доказательство
удара. Киллы 1 и 3: lock HP 1.0 → 0.0 и F3.

R1 без изменений: PASS. Серия R1+R2 по флагу — оба PASS.

```text
LiveRuntime execution path = LIVE-VALIDATED
Long-horizon Agent/Task layer = NOT YET LIVE-VALIDATED
```

Не ярлык «agent LIVE-PROVEN». Q5 не закрыт. R1/R2 JSON не
переписывать.

Подробный снимок 7.5:
[live-runtime-after-prompt7.5.md](live-runtime-after-prompt7.5.md).

## Ход 94 — live R2 после blind_melee — 2026-09-18

Live HID был. F82/F85/F86 не переписывали. Prompt 8 нет.

R2 (`R2-runtime-combat.json`): **FAIL**, `self_hp_low`, 173.7 с,
окно 18733, PID 68342. Киллов 0. `f2_input_count=22`.
11× `blind_engage`: 10 `no_hud_lock` (~5 с), затем abort.
`blind_melee` не сработал. Self HP старт/мин/конец 0.99 / 0.0 / 0.0
(цифра парсера; в конце полоса = 0). roam 10, `stuck_keys=0`,
`release_all` да. SHA1 `0ceb099c…`.

R1 без изменений: PASS. Не `LIVE-PROVEN`. Q5 не закрыт.

## Ход 93 — килл без пластины HUD — 2026-09-18

Код, не новый live. F82/F85/F86 не переписывали. Prompt 8 нет.

Оператор видел много киллов в R2; JSON писал 0. Парсер держал
ложную мёртвую пластину (HP 0) на парковке F45 / земле: F2 шёл,
`_killed` ждал живой лок, 8× сидели 25 с, лута не было.

Код: плоское поле ≠ пластина; свой HP не цель; без живого лока
слепой F2 рвётся через 5 с; если за F2 своё HP упало — F3 и
+1 килл (`blind_melee`). Не обещает посчитать каждого волка.

`pytest` зелёный. ADR-0082. Q5 не закрыт.

## Ход 92 — live R2 после слепого F2 — 2026-09-18

Live HID был. F82/F85/F86 не переписывали. Prompt 8 нет.

R2 (`R2-runtime-combat.json`): **FAIL**, `roam_limit`, 411.8 с,
окно 18733, PID 68342. Киллов 0. `f2_input_count=55` (раньше 0).
15× `blind_engage`: 8 `combat_timeout`, 7 `no_hud_lock`.
`attack_skill_success=0`, лута нет. Self HP старт/мин/конец
0.99 / 0.39 / 0.99 (цифра парсера). `stuck_keys=0`, `release_all` да,
focus/capture не теряли. SHA1 `fdf59084…`.

R1 без изменений: PASS. Серия не `LIVE-PROVEN`. Q5 не закрыт.

## Ход 91 — F2 без HUD-lock — 2026-09-18

Код, не новый live. F82/F85/F86 не переписывали. Prompt 8 нет.

После двух F1 без `target_locked` спот шлёт F2
(`AttackTarget(require_lock=False)`, 5 с). Ложная мёртвая пластина
не блокирует старт и не считается киллом. Килл только после живого
лока HUD.

Последний live R2 всё ещё FAIL: `R2-runtime-combat.json`,
`f2_input_count=0`, 0 киллов. Повторного HID после этого фикса нет.
`pytest`: 373 passed, 0 failed. ADR-0081. Q5 не закрыт.

## Ход 90 — live R1/R2, цель без удара — 2026-09-18

Live HID был. F82/F85/F86 не переписывали. Prompt 8 нет.

R1 (`R1-runtime-npc.json`): **PASS**. `/target` → F2 → диалог гида →
один пункт → Escape. Окно 18733, PID 68342. 14.67 с. SCK restart 6.

R2 (`R2-runtime-combat.json`): **FAIL**. HP старт 0.99 после recover
своих полос. F1 подсвечивал мобов, F2 не ушёл (`f2_input_count=0`),
14 roam, `capture_lost` на 147 с, 0 киллов.

Причина: окно цели не в парковке F45; `wait_lock` не видел
`target_locked` + HP≥0.15 и уходил в roam. В `hud_parser` — поиск
пластины сверху кадра (`recover_target_lock`). Повторного R2 после
этого фикса ещё нет. Полный `pytest` зелёный. Q5 не закрыт.

## Ход 89 — Prompt 7.5 prep, live ещё нет — 2026-09-18

Код: флаг `--runtime-validation` у `s4-npc-dialog` и
`s4-integrated-spot`. R1 кликает один пункт гида. R2 — `--kills 3`.
Новые пути: `docs/evidence/live-agent-runtime/`. F82/F85/F86 не
трогали. Prompt 8 нет. Live HID тогда не запускали. `pytest`: 363 passed,
0 failed. ADR-0080. Живые R1/R2 и снимок — Ход 95 /
[live-runtime-after-prompt7.5.md](live-runtime-after-prompt7.5.md).

## Ход 88 — Prompt 6–7, оба зонда на LiveRuntime — 2026-09-18

Код: `s4-npc-dialog` и `s4-integrated-spot` оркеструют один
`LiveRuntime` (`run_skill`). CLI те же. Prompt 8 не начинали.
Frozen L1 / `sim/` / MaleCNS не трогали. Live HID не запускали.
Evidence F82/F85/F86 не переписывали. `pytest`: 358 passed, 0 failed.
ADR-0079.

Снимок перед live validation vs Task layer:
[live-runtime-after-prompt7.md](live-runtime-after-prompt7.md).

## Ход 87 — LiveRuntime каркас, Prompt 0–5 — 2026-09-18

Код: `live/skills`, `WorldState`, `PerceptionHub`, `LiveRuntime`,
CLI `agent-live` (observe-only по умолчанию). Probes не мигрированы.
Frozen L1 / `sim/` / MaleCNS не трогали. Live HID не запускали.
`pytest`: 357 passed, 0 failed (было 336). ADR-0078.

Снимок для проверки «не rename»:
[live-runtime-after-prompt5.md](live-runtime-after-prompt5.md).

---

`docs/architecture.md` сведён с кодом на 2026-09-17 (два стека,
живые зонды, H8 / F57). Это документ, не новый прогон.

Сводка H17 (без нового прогона): [h17-report.md](evidence/h17-report.md).
Гипотеза открыта. ADR-0064 действует.

## Ход 86c — сетка 2560×1600 — 2026-09-18

Оператор: разрешение гостя 2560×1600. `ref_window` сменён.
Слот А `[60,140,400,520]`, слот Б `[2140,140,360,480]`.
Оверлей масштабирует на окно хоста 2056×1290. HID нет.
F86 не переписывали. Q5 не закрыт.

ADR-0077.

## Ход 86b — живой оверлей рамок — 2026-09-18

Оператор: рамки нужны поверх окна, не PNG. CLI `layout-overlay`,
клики навылет, без HID. Слоты снова цели: А `[60,140,400,520]`,
Б `[1636,140,360,480]`. Слой показан на окне 16372 (180 с).
F86 не переписывали. Q5 не закрыт. Frozen L1 / `sim/` не трогали.

ADR-0076.

## Ход 86 — сетка слотов UI — 2026-09-18

Живой прогон, окно 16372. Чистый слот Б → Tab → занят → Escape →
свободен, **1.330 с**. Слот А `[60, 140, 400, 520]`. Слот Б
`[1592, 650, 342, 307]` (стоянка инвентаря, не трава y=140).
Фарм нет. Frozen L1 / `sim/` не трогали. Q5 не закрыт.

Отчёт: [hod86-s4.md](evidence/hod86-s4.md). F86. ADR-0075.

## Ход 85 — F2-подбег и обход меню гида — 2026-09-18

Живой прогон, окно 16372. `/target` → F2 → ЛКМ (0.50, 0.48).
HTML слева, **6/6** пунктов, `false_target_markers=0`, 36.67 с.
Фарм нет. Frozen L1 / `sim/` не трогали. Q5 не закрыт.

Отчёт: [hod85-s4.md](evidence/hod85-s4.md). F85. ADR-0074.

## Ход 84 — чат-таргет в коде, живой h нет — 2026-09-18

Код: `/target <Name>`, PID-only ЛКМ, `html_links` ≥2 синих.
`pytest` зелёный (весь `tests`). Frozen L1 / `sim/` не трогали.
Фарм и F2 нет.

Живой прогон h **не запускался**: окно 16372 после activate
осталось `on_screen=false`. Скрытый стол не источник. JSON
`npc-chat-target-h.json` нет. F84 нет.

Отчёт: [hod84-s4.md](evidence/hod84-s4.md). ADR-0073.

## Ход 83 — зонд диалога NPC, лок есть, окно нет — 2026-09-18

Два живых F5: лок есть, окно нет, `dialog_timeout` 8 с.
Повтор SHA1 `684b00cc…`. F2 не слали. Frozen L1 / `sim/` не трогали.

Отчёт: [hod83-s4.md](evidence/hod83-s4.md). F83. ADR-0071.

## Ход 82 — серия 10/10 за 150 с, агро 2 — 2026-09-18

Живой прогон, окно 16372. **10/10**, без таймера, abort нет.
Средний бой 3.35 с. L1 0, агро 2, разворот 2, roam 14,
stuck_keys 0. Frozen L1 / `sim/` не трогали.

Отчёт: [hod82-s4.md](evidence/hod82-s4.md). F82. ADR-0070.

## Ход 81 — агро + жёсткий L1, 5/5 за 94.6 с — 2026-09-18

Живой прогон, окно 16372. **5/5**, без таймера, abort нет.
L1 0 (было 60), разворот 1, агро 0, roam 11, stuck_keys 0.
Средний бой 3.36 с. Frozen L1 / `sim/` / `tactical.py` не трогали.

Отчёт: [hod81-s4.md](evidence/hod81-s4.md). F81. ADR-0069.

## Ход 80 — L1+L2 spot, 7/10, стоп по HP — 2026-09-18

Живой прогон 251.9 с, окно 16372. **7 фрагов**, abort `self_hp_low`.
roam 24, L1 60, stuck_keys 0, farm false. 10/10 нет. Frozen L1 /
`sim/` не трогали.

Отчёт: [hod80-s4.md](evidence/hod80-s4.md). F80. ADR-0068.

## Ход 74 — стрелка: klt_physical, профиля нет — 2026-09-18

89 живых JSON. Два раза `arrow_pulse`: KLT −42 / −40 px,
146 и 113 инлаеров, ratio 0.73 / 0.71. Код `q5_closed=true`.
Профиль не писали (`|dx|<50`). Дальше RMB с `pixel_diff≥12`
съедал fallback стрелки. Оператор: yaw и короткие `w`, нигде
не застревал. `stuck_detected` везде false. H17 не закрыта
(8 с не слали). Frozen L1 не трогали.

Отчёт: [hod74-s4.md](evidence/hod74-s4.md). F79. ADR-0067.

## Ход 73 — батарея калибровки, Q5 нет — 2026-09-18

67 живых JSON. RMB ≤120 на стене часто нулевой; с 150 —
скачок. `corner-m50`: coarse и KLT ≈54 px, 2 инлаера. На крыше
тот же +40 мыши даёт ~270 px. Шаг w 500 мс: 66 px, peak 0.018.
Профиль не писали. Frozen L1 не трогали.

Отчёт: [hod73-s4.md](evidence/hod73-s4.md). F78. ADR-0067.

## Ход 72 — сильнее RMB, coarse yaw — 2026-09-18

RMB +800. T0 стена, T1 площадь. coarse_dx **1313**, assumed ≈24°.
KLT 2 инлаера, Q5 нет. Стрелку не слали. Профиль не писали.
Frozen L1 не трогали.

Отчёт: [hod72-s4.md](evidence/hod72-s4.md). F77. ADR-0066.

## Ход 71 — coarse live, буфер SCK — 2026-09-18

RMB +480: T0≡T1, `grab()` без копии. physical=false. Q5 нет.
Frozen L1 не трогали.

Отчёт: [hod71-s4.md](evidence/hod71-s4.md). F76.

## Ход 70 — KLT врал про yaw — 2026-09-18

Оператор на F74 видел разворот ≈45°. KLT ±40 px это не ловит.
`coarse_shift` + PNG T0/T1 в v3. Q5 не закрыт. Профиль не писали.
Живой coarse-прогон ещё не делали. Frozen L1 не трогали.

Отчёт: [hod70-s4.md](evidence/hod70-s4.md). F75. ADR-0065.

## Ход 69 — сильный yaw, Q5 нет — 2026-09-18

RMB +480 за ~0.6 с, 24 тапа и hold стрелки 800 мс. KLT держит
точки, median_dx ≈ 0. Профиль не писали. Frozen L1 не трогали.

Отчёт: [hod69-s4.md](evidence/hod69-s4.md). F74.

## Ход 68 — yaw у стены, Q5 нет — 2026-09-18

RMB +150 и пульс стрелки. KLT сошёлся (39 инлаеров), median_dx = 0.
Профиль не писали. Frozen L1 не трогали.

Отчёт: [hod68-s4.md](evidence/hod68-s4.md). F73.

## Ход 67 — основной live-motion — 2026-09-18

8.39 с. flow 0.014, пик **0.136**, duplicate нет. stuck false.
Боевой зонд не в этой линейке. Frozen L1 не трогали.

Отчёт: [hod67-s4.md](evidence/hod67-s4.md). F72.

## Ход 66 — 8 с после коротких — 2026-09-18

8.66 с. flow 0.014, пик 0.095. С free[7] кадр замер. stuck false.
H17 ждёт: ходишь ли ты после этого. Frozen L1 не трогали.

Отчёт: [hod66-s4.md](evidence/hod66-s4.md). F71.

## Ход 65 — второй короткий `w` — 2026-09-18

2.19 с. HID ушёл, duplicate нет, flow 0. Кадр не замер.
8 с не слали. Frozen L1 не трогали.

Отчёт: [hod65-s4.md](evidence/hod65-s4.md). F70.

## Ход 64 — короткий `w` после релога — 2026-09-18

1.93 с, 3 сэмпла. HID ушёл, кадр менялся, duplicate нет, flow 0.034.
H17 не закрыта: длинный прогон не слали. Frozen L1 не трогали.

Отчёт: [hod64-s4.md](evidence/hod64-s4.md). F69.

## Ход 63 — повторный срыв после прогона — 2026-09-18

Два срыва сразу после непрерывного `w` ≥8 с (F65, F66). H17 открыта.
Длинный прогон не слать, пока сам не походишь после входа.
Frozen L1 не трогали.

Отчёт: [hod63-s4.md](evidence/hod63-s4.md). F68. ADR-0064.

## Ход 62 — короткий `w`, кадр не двинулся — 2026-09-18

3 сэмпла по 500 мс. HID ушёл, ключ отпущен. Все тики `duplicate`,
flow 0. Сеть не измеряли. Frozen L1 не трогали.

Отчёт: [hod62-s4.md](evidence/hod62-s4.md). F67.

## Ход 61 — рестарт, окно 16372, L1 stuck нет — 2026-09-18

Непрерывный `w` 8.32 с. `flow_magnitude` **0.044** / 0, пик **0.231**.
Один тик `approach`. blocked[1..2] duplicate. encode p95 48.8 мс.
`stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod61-s4.md](evidence/hod61-s4.md). F66.

## Ход 60 — линейка live-motion закрыта — 2026-09-17

F61–F65: ввод есть, `FLOW_FREE_MIN` 0.25 нет, Q5 открыт, L1 stuck
не готов. Клиент завис. Окно 13944 / PID 68342 списать.
HID не слать до нового `capture list`. Frozen L1 не трогали.

Отчёт: [hod60-s4.md](evidence/hod60-s4.md). ADR-0063.

## Ход 59 — непрерывный `w` в клиенте, L1 stuck нет — 2026-09-17

Один `w` на 8.34 с, 2 HoldKey, stuck_keys=0. `flow_magnitude` 0.0048 / 0,
пик 0.048. С free[6] кадр замер. encode p95 48.4 мс.
`stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod59-s4.md](evidence/hod59-s4.md). F65. ADR-0062.

## Ход 58 — непрерывный `w` — 2026-09-17

Зонд больше не пульсирует `w`. Одна клавиша на всю сессию,
`--hold-ms` = период сэмпла. Тесты 4 зелёных. Живого прогона нет.
Frozen L1 не трогали.

ADR-0062.

## Ход 57 — подход к стене, L1 stuck нет — 2026-09-17

13 тиков `w` 600 мс. `flow_magnitude` 0.0139 / 0, пик free **0.095**.
С free[5] кадр замер (`duplicate`, confidence 0). encode p95 47.7 мс.
`stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod57-s4.md](evidence/hod57-s4.md). F64. Протокол ADR-0061.

## Ход 56 — поток у стены, L1 stuck нет — 2026-09-17

13 тиков `w` 600 мс. `flow_magnitude` 0.0137 / 0, `expansion` = 0,
`motion_confidence` ≈ 0.45 / 0.16. Два последних blocked-тика:
`duplicate=true`, confidence 0. encode p95 48.4 мс.
`stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod56-s4.md](evidence/hod56-s4.md). F63. Протокол ADR-0061.

## Ход 55 — поток у ворот деревни, L1 stuck нет — 2026-09-17

13 тиков `w` 600 мс перед воротами. `flow_magnitude` 0.0089 / 0
(два тика ≈ 0.045), `expansion` = 0, `motion_confidence` ≈ 0.51 / 0.53.
encode p95 50.1 мс. `stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod55-s4.md](evidence/hod55-s4.md). F62. Протокол ADR-0061.

## Ход 54 — живой поток на `w`, L1 stuck нет — 2026-09-17

13 тиков `w` 600 мс. `flow_magnitude`/`expansion` = 0,
`motion_confidence` ≈ 0.40 на беге и на «упоре». encode p95 48 мс.
`stuck_detected=false`. Frozen L1 не трогали.

Отчёт: [hod54-s4.md](evidence/hod54-s4.md). ADR-0061. F61.

## Ход 53 — sync T0/T1, Q5 нет — 2026-09-17

Кадры изолированы: `diff_mean` 7.05, Δt 371 мс, не один буфер.
KLT median_dx ≈ 0. Рассинхрон SCK не подтверждён. Профиль не писали.

Отчёт: [hod53-s4.md](evidence/hod53-s4.md). ADR-0060. F60.

## Ход 52 — RMB Drag, Q5 нет — 2026-09-17

KLT сошёлся (inliers 39 ≥ 30, ratio 0.83), median_dx ≈ 0 на
RMB +150 px и на 10 тапах стрелки. Профиль не писали.
Автономный агент не открыт.

Отчёт: [hod52-s4.md](evidence/hod52-s4.md). ADR-0059. F59.

## Ход 51 — KLT yaw, Q5 нет — 2026-09-17

`goodFeaturesToTrack` + PyrLK, right/left 450 мс. Инлаеры 22 и 25
(< 30), median_dx ≈ 0. Профиль не писали. Автономный агент не открыт.

Отчёт: [hod51-s4.md](evidence/hod51-s4.md). ADR-0058. F58.

## Ход 50 — H8 закрыта, Q5 горизонт нет — 2026-09-17

100 тиков SCK→HUD→L1→idle CGEvent: p95 H8 **2.19** мс, pipeline
**16.33** мс, encode p95 44.26 мс, hid_sent=false. Горизонт 15–30%:
peak **0.013** < 0.15, профиль не писали. Автономный агент не открыт.

Отчёт: [hod50-s4.md](evidence/hod50-s4.md). ADR-0057. F57.

## Ход 49 — замер сдвига кадра — 2026-09-17

Один `right_arrow` и один `w` по 500 мс. Сдвиг посчитан, пик низкий
(0.023 / 0.034). H8 и Q5 не закрыты. Автономный агент не открыт.

Отчёт: [hod49-s4.md](evidence/hod49-s4.md). ADR-0056. F56.

## Ход 48 — камера стрелкой — 2026-09-17

`--verify-search`: F1 lock 0.444, `right_arrow` 450 мс, килл 0.444→0.0,
F3, 9.26 с, stuck=0. Мышиный драг не слали. Yaw глазами не видели.

Отчёт: [hod48-s4.md](evidence/hod48-s4.md). ADR-0055. F55.

## Ход 47 — поиск при пустом /targetnext — 2026-09-17

`--verify-search`: F1×2 miss → CameraRotate 150 → `w` 400 мс → F1.
Лока нет, Escape, stuck=0, watchdog=false. Килла нет.

Отчёт: [hod47-s4.md](evidence/hod47-s4.md). ADR-0054. F54.

## Ход 46 — три цикла на споте — 2026-09-17

`--multi-kill 3`: три фрага, три F3, 27.33 с, stuck=0, watchdog=false.
Сессия сама остановилась. Фарм не открывали.

Отчёт: [hod46-s4.md](evidence/hod46-s4.md). ADR-0053. F53.

## Ход 45 — смерть цели и F3 — 2026-09-17

Один моб: 0.444 → 0.0 за 6685 мс, `EntityDefeated`, F3 отправлен.
9.14 с, stuck=0. Подбор в инвентаре не проверяли.

Отчёт: [hod45-s4.md](evidence/hod45-s4.md). ADR-0052. F52.

## Ход 44 — первый зафиксированный урон — 2026-09-17

`--engage-any`: цель 0.444 принята. F2×2. Полоска **0.444 → 0.366**
за 1031 мс. 2.58 с, stuck=0. Не килл.

Отчёт: [hod44-s4.md](evidence/hod44-s4.md). ADR-0051. F51.

## Ход 43 — clean-target, урона нет — 2026-09-17

Escape снял живую рамку (пустая подложка). F1 трижды вернул HP **0.444**.
F2 не слали. `damage_detected=false`. 4.61 с, stuck=0.

Отчёт: [hod43-s4.md](evidence/hod43-s4.md). ADR-0050. F50.

## Ход 42 — первый S4-зонд — 2026-09-17

Один цикл на окне 13944: F1 → lock 0.444 за 116 мс → F2 → HP без
дельты → Escape. 5.43 с, 76 тиков, hid_sent=true, stuck=0.
Урона нет. Фарма нет.

Отчёт: [hod42-s4.md](evidence/hod42-s4.md). ADR-0049. F49.

## Ход 41 — TargetLost и слоты F1–F3 — 2026-09-17

Сброс при HP 0.44 больше не `EntityDefeated`. Победа — только HP=0
на рамке или пропажа при HP ≤ 0.08. Слоты F1–F3 на кадре F45 ready.
HID нет. S4 не открыт.

Отчёт: [hod41-hud.md](evidence/hod41-hud.md). ADR-0047. F47.

## Ход 40 — смерть цели ≠ нет цели — 2026-09-17

Рамка по подложке Classic, HP отдельно. F45: locked, hp 0.444, не dead.
F44: locked=false, hp=None. Пустая подложка → locked + hp 0.0.
`EntityDefeated` с `ui_vision`. HID нет. S4 не открыт.

Отчёт: [hod40-hud.md](evidence/hod40-hud.md). ADR-0046. F46.

## Ход 39 — измеренные ROI HUD Interlude — 2026-09-17

Офлайн по кадру с целью Gremlin. Плейсхолдеры F44 сняты.
Свои полосы **0.943 / 0.952 / 0.962** при тексте 126/126, 38/38, 50/50.
Цель залочена, `target_hp` **0.444** (текста нет). HID нет.

Отчёт: [hod39-hud.md](evidence/hod39-hud.md). ADR-0045. F45.

## Ход 38 — нативный фокус / кадр Interlude — 2026-09-17

Фокус: NSWorkspace, osascript снят. p50 **0.0047 мс**.
`act_ms` на RecordingPoster **0.016 мс**. Живой HID не слали.

SCK кадра окна `Windows 11` id 13944: клиент Interlude **оконный**.
Плейсхолдеры HUD не попали в полосы. `self_*` не переписывали.
S4 / H8 не открыты.

Отчёт: [hod38-prep.md](evidence/hod38-prep.md). ADR-0044. F44.

## Ход 37 — live-probe в Блокнот — 2026-09-17

`L2.exe` не было. `hid_sent=true`, stuck=0, watchdog отпустил `w`.
act_ms p50/p95 215.6/244.1 мс. В кадре Notepad строка начинается с `123`.
S4 / H8 не открыты.

Отчёт: [hod37-notepad.md](evidence/hod37-notepad.md). F43.

## Ход 36 — CGEvent backend / S3 — 2026-09-17

Двойной флаг `live_confirmed` + `live_danger_confirmed`. Фокус Parallels,
watchdog 250 мс → keyUp. Live-probe **не слал HID**: в госте `l2.exe`.
Блокнот не подтверждён. S4 / H8 не открыты.

Отчёт: [hod36-cgevent.md](evidence/hod36-cgevent.md). ADR-0043. F42.

## Ход 35 — парсер HUD / ui_vision — 2026-09-17

Синтетические полосы ±2%. События `HealthUpdate` / `TargetState` с
`source="ui_vision"`. Чёрный кадр не публикуется. ROI в профиле окна.
Живой Classic UI не размечали. `sim_ground_truth` на стенде остаётся.
HID нет.

Отчёт: [hod35-hud.md](evidence/hod35-hud.md). ADR-0042. F41.

## Ход 34 — H7 на видимом окне Parallels — 2026-09-17

30.13 с окна `Windows 11` (id 13745): медиана **33.76 мс**,
**29.62 FPS**, drops 0, black 0, latency p50/p95 10.97/12.73 мс.
H7 **принята**. HID нет. HUD и live-ввод не открыты.

Отчёт: [hod34-h7.md](evidence/hod34-h7.md). ADR-0041. F40.

## План живого края — Parallels / Lineage 2 — 2026-09-17

Синтетический L1/L2 закрыт. Этап 1–3 как раньше (F40–F43). Ход 38:
нативный фокус и кадр оконного Interlude (F44). Ход 39: ROI полос
на одном layout с целью (F45). S4 не открыт.

План: [live-parallels-plan.md](live-parallels-plan.md).

## Ход 33 — спот-цикл L2 — 2026-09-17

`multi_dummy_arena_v0` + `SpotAutonomousAgent`. Клиент / HID нет.
Baseline не трогали. GT не в Observation.

250 тиков, seed=0: **4 фрага, 4 лута**, серия 4, watchdog 0.
FSM: SCAN→TARGET→APPROACH→COMBAT→LOOT→RESET.

Отчёт: [hod33-spot-loop.md](evidence/hod33-spot-loop.md). ADR-0040.

## Ход 32 — мини-сводка контроллеров — 2026-09-17

Пять политик на пяти сценах `training:v0:s0`. Веса не крутили.
Frozen 60 не гоняли. `snn_rstdp` = замороженный `w_in` хода 27.

baseline **5/5**, snn / rstdp / malecns **4/5**, GRU **3/5**.
Нейронное ядро для L2 — `snn_v1`. Frozen L1 не снят.

Отчёт: [hod32-suite.md](evidence/hod32-suite.md). ADR-0039.

## Ход 31 — синтетический подграф MaleCNS — 2026-09-17

Изолированный экстракт `synthetic_visuomotor_extract_v0` (N=208, E=616),
не полный коннектом. LIF как у `snn_v1`; `W_rec` из топологии. Контроли:
shuffle и ER. `snn_v1` / baseline / GRU не меняли. Frozen 60 не гоняли.

`open_goal:training:v0:s0`, n=1: snn **61**, bio **178**, shuffle **191**,
ER timeout 200. Bio быстрее shuffle, хуже Брайтенберга. H11 не принята.

Отчёт: [hod31-malecns.md](evidence/hod31-malecns.md). ADR-0038.

## Ход 30 — профиль и MPS — 2026-09-17

100 тиков, три контроллера. Encode ~3.8 мс, SNN infer p95 **1.70** мс.
MPS на N=64 B=1 медленнее CPU (0.156 vs 0.003 мс). H6 отклонена.
`numpy_cpu` оставлен. Модели не меняли.

Отчёт: [hod30-profiling.md](evidence/hod30-profiling.md). ADR-0037.

## Ход 29 — синтетический бой — 2026-09-17

`TelemetryHub` + арена `combat_dummy_v0` + FSM тактики. Клиент и HID нет.
Baseline / Frozen 60 не трогали.

Эпизод: **combat_success 80** тиков, урон 100, SEEK→VICTORY.
Отчёт: [hod29-combat.md](evidence/hod29-combat.md). ADR-0036.

## Ход 28 — InputBackend dry-run — 2026-09-17

Пакет `src/l2_brain/io/`: декодер `MotorIntent`→действия, watchdog 250 мс,
лог без HID. Живой ввод закрыт. S2/S3 не открыты. Контракты не меняли.

`pytest tests/test_input_backend.py` — 6 passed.
Отчёт: [hod28-input-dry-run.md](evidence/hod28-input-dry-run.md). ADR-0035.

## Ход 27 — R-STDP — 2026-09-17

Привилегированный `RewardEngine` и трёхфакторная пластичность на `w_in`.
Baseline не трогали. Frozen 60 не гоняли. Дистанция в `Observation` не
попадает.

Контроль (шум, freeze) 59 тиков; после 8 эпизодов R-STDP eval **58**.
Δ=1, n=1 — не рейтинг. Отчёт: [hod27-rstdp.md](evidence/hod27-rstdp.md).
ADR-0034.

## Ход 26 — GRU + мини-бенч — 2026-09-17

Компактный `gru_v1` (NumPy, H=16) и CLI `l2-brain bench`. Baseline и SNN
не ломали. Frozen 60 не гоняли.

`open_goal:training:v0:s0`, n=1: baseline 72 / GRU 162 / SNN 61, все success,
col=0. Отчёт: [hod26-gru-bench.md](evidence/hod26-gru-bench.md). ADR-0033.

Это не H3/H4 и не рейтинг каталога.

## Ход 25 — Braitenberg — 2026-09-17

Жёсткий сенсомоторный рефлекс в `snn_core_v1`. STDP нет.
`open_goal:training:v0`: **success 61**, col=0, infer_ms_p50=1.704.
Отчёт: [hod25-braitenberg.md](evidence/hod25-braitenberg.md). ADR-0032.

Frozen 60 не гоняли. Baseline не трогали.

## Ход 24 — SNN sandbox — 2026-09-17

Пакет `src/l2_brain/control/snn/` (`snn_core_v1`). Baseline не трогали.
`pytest tests/test_snn_dynamics.py` зелёный. Один эпизод `open_goal:training:v0`:
timeout 200, **infer_ms_p50=1.653** мс, частота 52.2 Гц.
Отчёт: [hod24-snn-sandbox.md](evidence/hod24-snn-sandbox.md). ADR-0031.

Frozen 60 не гоняли. H3/H4 не закрыты. F14/F15/post-h22/hod23 не трогали.

## Milestone — L1 заморожен — 2026-09-17

Калибровка `baseline_memory_v1` **завершена и заморожена**. Канон Frozen 60
seed=0, 200 тиков: **52/60** ([frozen-hod23.json](evidence/hod23/frozen-hod23.json)).
Дальше не крутить скаляры и таймеры. Восемь эпизодов законсервированы (забор
ADR-0028; box v2/v3; moving held_out v4).

Следующий код — изолированный `src/l2_brain/control/snn/` (песочница LIF), не
замена baseline, не Frozen 60, не H3/H4. Каркас готов:
[hod23-l1-freeze.md](evidence/hod23-l1-freeze.md). ADR-0030.

F14/F15, post-h22 и hod23 JSON не трогать. S2 не открыт. L2/L3 нет.

## Ход 23 — курс vs обход — 2026-09-17

Потеря цели после `had_target` держит курс; Probe/Peel не стартуют без looming.
Живая цель на lock слегка доворачивает (`course_lock_track=0.16`). Забор не трогали.

Frozen 60 seed=0: **52/60** ([frozen-hod23.json](evidence/hod23/frozen-hod23.json)).
post-h22 было 46/60. Отчёт: [hod23-course-hold.md](evidence/hod23-course-hold.md). ADR-0029.

F14/F15 и post-h22 JSON не трогали. S2 не открыт.

## Кинематический срез — 2026-09-17

Контроллер не меняли. `long_fence` training v0 при 250 тиках: **success 244**, col=0.
Frozen 60 seed=0: **46/60** ([frozen-post-h22.json](evidence/post-h22/frozen-post-h22.json)).
post-h14 было 44/60. Отчёт: [post-h22/report.md](evidence/post-h22/report.md). ADR-0028.

F14/F15 не трогали. S2 не открыт.

## Budget trim — 2026-09-17

Вынос после кромки 35→32; после wrap — 8 тиков курса и спринт 1.0. Разгон Probe
0.75 отвергнут: ломает бокс. `dead_end` **147**. `single_obstacle` **193**.
`weak_texture` **190**. `long_fence`: LOS **182**, захват **183**, timeout 200,
dist=4.47. Отчёт: [hod22-budget-trim.md](evidence/hod22-budget-trim.md). ADR-0027.

F14/F15 не трогали. S2 не открыт.

## Post-Edge Wrap — 2026-09-17

После дополнительного Slide по `edge_seen` — короткий доворот на восток, вынос, доворот
на северо-восток. `dead_end` **147**. `single_obstacle` **193**. `weak_texture` **190**.
`long_fence`: LOS **185**, захват **186**, timeout 200, col=0, dist=5.12.
Отчёт: [hod21-post-edge-wrap.md](evidence/hod21-post-edge-wrap.md). ADR-0026.

F14/F15 не трогали. S2 не открыт.

## Edge-loss Slide — 2026-09-17

Slide больше не режется на 22-м тике. Hook abort, если после 26 тиков доворота фронт занят —
кромка ещё есть: align и ещё 40 тиков Slide. `dead_end` **147**. `single_obstacle` **193**.
`weak_texture` **190**. `long_fence`: кромка подтверждена, торец пройден (`min_y=3.11`), LOS нет,
stuck 200. Отчёт: [hod20-edge-loss.md](evidence/hod20-edge-loss.md). ADR-0025.

F14/F15 не трогали. S2 не открыт.

## Corner Hook — 2026-09-17

После глубокого Peel Slide ограничен 22 тиками, затем доворот `-sign` за угол. На пятне —
короткий пробег вдоль курса и пол скорости seek, чтобы не клинить в AABB и не ползти.
`dead_end` **147**. `single_obstacle` **190** (LOS 118). `weak_texture` **191**. `long_fence`
timeout, LOS нет. Отчёт: [hod19-corner-hook.md](evidence/hod19-corner-hook.md). ADR-0024.

F14/F15 не трогали. S2 не открыт.

## Probe Gate — 2026-09-17

Слепой ход начинается с поступательного Probe (`forward=0.45`, `turn=0`). Первый фронт
классифицирует глубину: `<14` тиков — разворот на месте (`CLOSE_TRAP`), иначе Peel ~120° и Slide
(`OBSTACLE_BYPASS`). Имён сцен нет. Порог 0.12 не снижали.

`dead_end` **147** ≤150 (probe=9, shallow). `u_trap` 52. `open_goal` 72, `narrow_gate` 84,
`corridor` 94, `latency_drops` 76. Стена/забор/weak: stuck 200, LOS нет (probe 46 / 36 / 55, deep).
Отчёт: [hod18-probe-gate.md](evidence/hod18-probe-gate.md). ADR-0023.

F14/F15 не трогали. S2 не открыт.

## Ход 15 — 2026-09-17

Канон после хода 14 зафиксирован: [post-h14/frozen-baseline.json](evidence/post-h14/frozen-baseline.json) **44/60**.
Обход без пеленга: осцилляция снята, финиша у стены нет. Отчёт: [hod15-report.md](evidence/hod15-report.md).

F14/F15 не трогали. S2 не открыт.

## Текущий этап

Живой край: захват H7, HUD, Notepad, фокус (F40–F44). ROI / TargetLost /
F1–F3 (F45–F47). Q6 (F48). S4: F51 урон; F52 смерть 0.444→0.0 и F3.
H8 принята (F57). Q5 / H14 не закрыты. Frozen L1 не крутить.

## Что реально работает

- Канон 52/60: vanish 5/5; пеленговые 35/35 (`open_goal`, `narrow_gate`,
  `corridor`, `latency_drops`, `u_trap`, `dead_end`, `camera_spin`).
- `weak_texture` 5/5. `single_obstacle` 3/5. Осцилляций 0 (было 11 на post-h14).
- Протокол `CircuitController` готов принять изолированный SNN рядом с baseline.
- `snn_core_v1`: LIF + рефлекс Брайтенберга. `open_goal` v0 **success 61**,
  infer p50 1.704 мс. Не сравнение с baseline на каталоге.

Клиент: короткие S4-зонды F49–F52. Один моб добит, F3 послан (F52).

## Ограничения

- `long_fence` v0 на 200 — timeout, на 250 — success 244. v2/v4 — stuck с коллизиями. Стены 8/15.
- Held-out F14 не независим. `moving_target` held_out v4 на freeze — stuck.
- H15/H16 этим срезом не закрыты: это не абляция каналов и не тест recovery.

## Peel & Slide — 2026-09-17

Две фазы слепого хода: Peel 40 тиков (0.45 / 0.20), затем Slide (0.05 / 0.55).  
`dead_end` 140 success. Стена/забор/weak: цель не появляется — Slide после ~180° идёт от барьера.  
Отчёт: [hod16-peel-slide.md](evidence/hod16-peel-slide.md).

## Front-clear — 2026-09-17

`front_blocked` по steer/expansion, не по `brake_risk`. Нет фронта → Peel на месте до 40. Контакт после подхода.  
`dead_end` **134** ≤150. `open_goal` 72, `narrow_gate` 84. Стена/забор/weak: stuck, LOS нет.  
Отчёт: [hod17-front-clear.md](evidence/hod17-front-clear.md). ADR-0022.

## Следующий шаг

S4 только короткими зондами. Не фармить. Не крутить baseline.
Статический ROI ломается, если сдвинуть окно Classic. Q5 / yaw: фаза
и KLT не сошлись (peak < 0.15; inliers < 30). Живого кадра с
кулдауном-спиралью нет.
