# LiveRuntime validation — серия R1/R2

Не F82/F85/F86. Не Prompt 8. Не `LIVE-PROVEN`.

Подробный снимок Prompt 7.5:
[live-runtime-after-prompt7.5.md](live-runtime-after-prompt7.5.md).

Источник: JSON в `docs/evidence/live-agent-runtime/`.

## R1 NPC

Файл: `R1-runtime-npc.json`.

**PASS.** `/target` → F2 → диалог гида → один пункт → Escape.
Окно 18733, PID 68342. 14.67 с. SCK restart 6.
Первая попытка (`R1-runtime-npc-attempt1.json`) — `chat_target_failed`.

## R2 combat

Канон серии: `R2-runtime-combat.json` — «го» после Хода 95
(увеличенный HUD + F3 после F2).

**PASS.** 113.0 с, киллов 3, `f2_input_count=18`,
`loot_skill_runs=7`, `stuck_keys=0`, `focus_lost=false`,
`release_all_called=true`. Self HP 1.0 / 0.97 / 1.0.
SHA1 `be12db2b…`.

Килл 2 — `target_dead` за 0.03 с с HP 0→0; киллы 1 и 3
с живым lock 1.0→0.0 и F3.

Предыдущие попытки той же серии:

- `R2-runtime-combat-attempt1.json` — `self_hp_low`, 0.8 с, F2=0
- `R2-runtime-combat-attempt2.json` — `SourceLost`, 4.0 с, F2=0
- `R2-runtime-combat-attempt3.json` — `capture_lost`, 147.4 с, roam 14, F2=0
- `R2-runtime-combat-attempt4.json` — `capture_lost`, 105.3 с, roam 9, F2=0
- `R2-runtime-combat-attempt5.json` — `roam_limit`, 411.8 с, F2=55, киллов 0
- `R2-runtime-combat-attempt6.json` — `self_hp_low`, 173.7 с, F2=22, киллов 0

## Вердикт серии

R1 PASS, R2 PASS по критерию `runtime_validation`.
Не объявляем `LIVE-PROVEN` на весь агент.
Task layer v1 есть в коде: `TASK_LAYER_STATUS = UNIT-TESTED`,
`LIVE_VALIDATION = NO`. Канон R1/R2 не переписывался.
R3/R4/R5 не создавались (ход 97, скан стопки — unit-only).
