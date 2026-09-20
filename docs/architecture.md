# Архитектура

Снимок на 2026-09-20 (ADR-0086: скан стопки меню unit-only;
ADR-0085: Task layer v1 unit-only;
ADR-0080: R1/R2 LiveRuntime live-validated. ADR-0079: NPC/spot
оркеструют LiveRuntime. ADR-0078: каркас).
Ранее 2026-09-17 (F64, ADR-0062). Источник истины — код в этом
каталоге, воспроизводимые прогоны и `docs/`. Граф `graphify-out/` —
ориентир, не прогон.

Исследовательский сенсомоторный агент: кадр → признаки → контроллер →
моторное намерение → команда → эффект. Не скрипт по карте и не
готовый бот. MaleCNS не считается игровой политикой.

## Границы

Входит: локальный стенд, общие контракты, сравнение контроллеров,
легальный захват окна, короткие живые зонды с двойным флагом.

Не входит: прохождение квестов, торговля, инвентарь, автономный фарм,
разбор сетевого протокола, гостевой код в Windows-клиенте, обход
античита, инъекции, скрытие ввода, загрузчик полного MaleCNS.

Два стека не смешивать в одном отчёте и не подменять друг друга.

| Стек | Вход / выход | Петля | Живой клиент |
|---|---|---|---|
| Стенд S0 | `types.Observation` → `types.Action` | `ControlLoop` + `SyntheticEnv` | нет; `LiveClientEnv` / `LiveHIDActuator` бросают `NotImplementedError` |
| Контур | `contracts.Frame` → `Observation` → `MotorIntent` → `Command` → `Effect` | `circuit.Circuit` | mock по умолчанию; `build_sck_circuit` берёт SCK и **mock** ввод |
| Живой зонд | SCK `Frame` + `HUDParser` + CGEvent | `live.s4_probe`, `s4-npc-dialog`, `bench-h8`, `calibrate-*` | да, только с `--live --danger-confirmed`; не `Circuit.run` |
| LiveRuntime | `PerceptionHub` → `WorldState` → один `Skill` → CGEvent | `live.runtime.LiveRuntime`; probes оркеструют его | R1/R2 LIVE-VALIDATED; не «agent LIVE-PROVEN» |
| Task layer v1 | одна `Task` → Skills через Runtime | `live.tasks`; `GuideInteractionTask` | UNIT-TESTED; `LIVE_VALIDATION = NO` |
| Menu stack scan | синие HTML-ссылки по всему кадру | `vision.menu_stack_scan`; `menu-click-debug` | UNIT-TESTED; не дефолтный парсер; live нет |

Контроллер не захватывает экран, не читает пакеты, не жмёт клавиши и
не знает раскладку HUD. Настройки игры — в
`config/window_profiles/`, не в политике.

## Иерархия (цель продукта, не один runtime)

| Уровень | Роль | Частота (цель) | Сейчас |
|---|---|---|---|
| L1 | сенсомотор: поток, пеленг, уход, `MotorIntent` | 20–60 Гц | Frozen: `baseline_memory_v1` 52/60 (ADR-0030). Рядом: `snn_v1`, `gru_v1`, не Frozen 60 |
| L2 | тактика: FSM/BT, бой, выход из застревания | 2–10 Гц | синтетический `SpotAutonomousAgent` (ADR-0040); не клиент |
| L3 | стратегия: миникарта, макромаршрут | низкая | зонд окна NPC (ход 83), не раннер квестов |

L1 не строит глобальную карту. Живой край — пиксели окна и разрешённый
HID на хосте. Автономный агент в клиенте не открыт.

## Контуры

### Стенд (`l2_brain.loop.ControlLoop`)

```text
 FrameSource                Controller               Actuator
     |                          |                       |
     | types.Observation        | types.Action          |
     +---------> ControlLoop ---+-------> apply --------+
                     |                                  |
                     +----------- TickMetrics           |
                     v                                  v
                  EpisodeReport                    SyntheticEnv
```

На стенде источник кадра и актуатор — одна синтетическая среда.
Контроллер об этом не знает.

### Исполняемый контур (`l2_brain.circuit.Circuit`)

```text
FrameSource -----> Frame
TelemetrySource -> TelemetryEvent[]
        \               /
         VisualEncoder
                |
        contracts.Observation
                |
        CircuitController --> MotorIntent
                |
          ActionDecoder --> Command
                |
          InputBackend --> Effect
                |
        Recorder / Evaluator (вне политики)
```

Жизненный цикл: `initialize` → `reset_episode` → `step`* → `close`.

Сбросы разделены:

- `reset_episode` — среда и источники, затем `controller.reset_state`;
- `reset_state` — кратковременная память;
- `reset_weights` — обученные параметры, не из `reset_episode`.

`select_target`, `attack`, `stop` — импульсы `idle|fire` на один тик.
`strafe` в mock равен `None`. Если
`now - timestamp_received_ns > stale_frame_ns`, наблюдение
`validity_mask.stale`, намерение `stop=fire`.

`build_mock_circuit` — искусственные кадры. `build_sck_circuit` —
живой `SCKFrameSource` и `MockInputBackend` (захват без HID).

### Живой зонд (не замкнутый Circuit)

```text
SCKGrabber.latest_image
        |
   HUDParser.parse          ---- ui_vision / TargetState / EntityDefeated
        |
   (опционально) NavigationEncoder + BaselineController.step
        |
   CGEventInputBackend      ---- dual live_confirmed + live_danger_confirmed
        |                         focus Parallels, F12, watchdog 250 мс
        v
   короткий сценарий: lock / F2 / F3 / стрелка / idle_act
```

Это не фарм и не `ControlLoop` на клиенте. Режимы: `s4-probe`,
`bench-h8`, `calibrate-hud`, `calibrate-motion`.

## Задержки

В отчёте всегда разделять стадии. `infer_ms` нельзя публиковать как
«латентность агента».

| Поле | Стенд / Circuit | Канон H8 (живой) |
|---|---|---|
| `observe_ms` | кадр + сбор наблюдения; в Circuit = `wait_frame + encode` | снятие последнего кадра SCK из очереди |
| `parse_ms` | нет | HUDParser; в формулу H8 не входит |
| `encode_ms` | часть observe в Circuit | NavigationEncoder; в формулу H8 не входит |
| `infer_ms` | только `Controller.step` / `CircuitController.step` | `BaselineController.step`, веса не меняются |
| `act_ms` | исполнить действие / продвинуть среду | `idle_act`: фокус, опрос F12, pump, пустой release |
| `loop_ms` | весь тик петли | не заменяет H8 |
| H8 | стендовый `loop_ms` **не** закрывает | p95(`observe + infer + act`) ≤ 100 мс |

H8 принята на F57: p95 = 2.19 мс, n=100. `observe` — копия из очереди
SCK, не фотон. encode p95 44.26 мс; даже observe+encode+infer+act
p95 45.65 мс. Отклонение — p95 > 150 мс.

Очередь кадра — latest-only: свежий кадр важнее устаревших. Локальные
интервалы — monotonic. Метка кадра — clock `event`. Возврат
асинхронного GPU не есть compute: нужен `gpu_synchronize`.

## Процессы и языки

| Часть | Язык | Почему |
|---|---|---|
| Стенд, контроллеры, оценка, зонды | Python | один протокол, тесты, CLI |
| Захват экрана | Swift `capture-probe` + ScreenCaptureKit | нативный путь macOS 12.3+ |
| Ускорение матриц | `numpy_cpu` | H6 отклонена (ADR-0037); MPS на B=1 не включать |

Python не импортирует ScreenCaptureKit. Транспорт v1 — stdout pipe
`L2F1`, rgb8, не shared memory (Q9). Профиль ROI/маски — отдельный
JSON. Захват скрытого окна не кормит контур. H7 принята на видимом
окне Parallels (F40).

Metal и MPS в v1 не слой архитектуры. Бэкенд — `l2_brain.accel`.

## Пакеты

```text
src/l2_brain/
  types.py              стенд: Observation, Action, TickMetrics, StepInfo
  contracts.py          контур: Frame, Observation, MotorIntent, Command, Effect
  features.py           общая выжимка кадра для стендовых контроллеров
  loop.py               ControlLoop (стенд)
  evaluate.py           сравнение reactive / recurrent / snn на SyntheticEnv
  accel.py              выбранный бэкенд (numpy_cpu)
  config.py             параметры стенда
  safety.py             явный блок LiveClientEnv / LiveHIDActuator
  controllers/          reactive, recurrent, snn  → types.Action
  env/                  SyntheticEnv; LiveClientEnv — заглушка
  actuators/            протокол; LiveHIDActuator — заглушка (не CGEvent)
  circuit/              Circuit, протоколы, mock I/O, PulseDecoder
  capture/              SCKFrameSource, профили окна, build_sck_circuit
  vision/               NavigationEncoder, HUDParser, калибровка ROI, menu_stack_scan
  calibration/          KLT yaw ±40 px; coarse phase + pixel_diff (Q5 не закрыт)
  control/              BaselineController (заморожен, ADR-0030)
  control/snn/          snn_core_v1 (LIF CPU; не controllers/snn.py)
  control/gru/          gru_v1 (NumPy GRU H=16)
  control/malecns/      синтетический экстракт; не FlyEM dump
  control/tactical.py   L2 FSM боя на стенде
  control/spot_agent.py непрерывный спот; L1 = snn_v1
  learning/             RewardEngine (GT) и ES без автограда
  io/                   GameAction, DryRun, CGEvent (двойной флаг)
  live/                 s4_probe: короткие сценарии, не фарм
  telemetry/            шина; vision_bridge ui_vision; не pcap
  sim/                  SimulationEnvironment, combat_dummy, spot_arena
  experiment/           запись, replay, часы
  bench/                профиль тика, suite 5×5, h8_latency_bench
macos/CaptureProbe/     список окон и поток L2F1
config/window_profiles/ parallels_l2.json (HUD ROI, не yaw-константа)
```

## Интерфейсы

Канон. Код обязан совпадать с этими полями.

### Стенд: `types.Observation`

- `frame` — `uint8` RGB `(H, W, 3)`;
- `timestamp_ns` — монотонные наносекунды источника;
- `tick` — номер тика эпизода.

Нет координат агента, цели, HP, опкодов и карты.

### Стенд: `types.Action`

- `turn` ∈ [-1, 1], минус влево;
- `forward` ∈ [0, 1];
- `engage` ∈ [0, 1] — «взаимодействовать с тем, что в прицеле».

Клиппинг делает петля.

### Стенд: `StepInfo`

Только отчёт: `agent_xy`, `target_xy`, `distance`, `bearing`,
`blocked`, `success`, `stuck`, `truncated`, `stuck_reason`.
В контроллер не передаётся.

### Стендовый Controller

```text
name: str
reset(seed) -> None
step(observation: types.Observation) -> types.Action
```

Три реализации для любого сравнения на `SyntheticEnv`:

1. `reactive` — без памяти, пороги по красной массе;
2. `recurrent` — те же признаки плюс короткое скрытое состояние;
3. `snn` — слой LIF на тех же признаках.

Это не контурный L1. Песочницы `control/snn/`, `control/gru/`,
`control/malecns/` не подменяют пункты 2–3 и не закрывают H3/H4
без отдельного `evaluate`. Полный MaleCNS сюда не входит.

### Контур: `contracts.Frame`

Сырой кадр: `frame_id`, `timestamp_capture_ns`,
`timestamp_received_ns`, `width`, `height`, `pixel_format=rgb8`,
`source_id`, `image` или `buffer_ref`.

### Контур: `contracts.Observation`

Признаки политики, не пиксели и не GT:

- `visual_features` (`EncodedVisual`);
- `target_bearing` / `target_confidence`;
- `motion_estimate` / `motion_confidence`;
- `telemetry` — разрешённые события, не privileged pose;
- `validity_mask` (в том числе `stale`);
- `previous_action`;
- `navigation` — опциональные сектора / поток.

Поля из `PRIVILEGED_OBSERVATION_FIELDS` (`agent_xy`, `distance`,
`hp`, `walls`, …) в этом классе запрещены.

### Контур: `MotorIntent` → `Command` → `Effect`

- намерение: `turn`, `forward`, `stop|select_target|attack` как
  импульсы, `confidence`, `valid_until_ns`;
- команда: клипнутые оси, `pulses`, срок, `dropped`;
- эффект: `accepted`, `reason`, `mock`.

Различать: намерение, отправленную команду, наблюдаемый эффект.

### Circuit-протоколы

```text
FrameSource.latest() -> Frame
TelemetrySource.poll() -> TelemetryEvent[]
VisualEncoder.encode(frame, telemetry, previous, now, stale) -> Observation
CircuitController.step(observation, now, ttl) -> MotorIntent
ActionDecoder.decode(intent, now) -> Command
InputBackend.apply(command) -> Effect
InputBackend.emergency_stop()
```

`l2_brain.io.InputBackend` (GameAction / HID) — другой тип. Не путать
с `circuit.protocols.InputBackend`.

### FrameSource на краях

| Реализация | Выход | Куда |
|---|---|---|
| `SyntheticEnv` | `types.Observation` | `ControlLoop` |
| `MockFrameSource` | `Frame` | mock `Circuit` |
| `SCKFrameSource` | `Frame` | `build_sck_circuit`, зонды |
| `SCKGrabber` | `ndarray` | `s4-probe`, `bench-h8`, калибровки |

Старый Observation-API `ScreenCaptureKitSource` контуром не
используется. `evaluate` по умолчанию SCK не включает.

### Actuator / ввод

| Реализация | Поведение |
|---|---|
| `SyntheticActuator` / шаг `SyntheticEnv` | сразу двигает стенд |
| `LiveHIDActuator` | `NotImplementedError` (стендовый тип `Action`) |
| `MockInputBackend` | эффект `mock=true`, без HID |
| `DryRunInputBackend` | лог `GameAction`, `hid_sent=false` |
| `CGEventInputBackend` | post to host PID; конструктор только при `live_confirmed` и `live_danger_confirmed` |

Аварийный стоп обязан существовать до длинного живого эпизода:
на стенде `env.close()` и нулевое действие; в CGEvent — F12,
потеря фокуса, watchdog 250 мс, `release_all`.

Камера в клиенте — клавиши стрелок (`left_arrow` / `right_arrow`),
не мышиный `CameraRotate` (ADR-0055). Мышиный драг Interlude
DirectInput игнорирует.

### Environment (стенд)

```text
reset(seed) -> Observation
step(action) -> (Observation, StepInfo)
close() -> None
```

Сцены `SyntheticEnv`:

| Имя | Смысл |
|---|---|
| `open_field` | цель впереди, без внутренних стен |
| `pursuit` | цель медленно уходит в сторону |
| `occluded` | между агентом и целью столб |
| `memory_probe` | цель видна слева, затем исчезает |

Успех `open_field` / `pursuit` / `occluded`: `engage > 0.5`,
дистанция и модуль пеленга меньше порога. Успех `memory_probe`:
цель видна слева 4 тика, затем исчезает; среднее `turn` на тиках
4–15 остаётся отрицательным.

Имена этих сцен не смешивать с каталогом nav-sim в одном отчёте.

## Петля стенда

`ControlLoop.run_episode`:

1. `env.reset`, `controller.reset`;
2. на каждом тике замерить `infer` и `step` среды;
3. стоп при `success`, `stuck` или исчерпании бюджета;
4. вернуть `EpisodeReport`.

Застревание в отчёте двух видов: `frozen` (почти нет сдвига xy/yaw)
и `no_progress` (дистанция не падает при высокой доле столкновений).
Это метрики, не запрет. «Не застревает» из них не выводится.

## Поток данных на стенде

1. Среда хранит позы агента и цели.
2. Рендер — 64×64 эгоцентрический луч-кастер: небо, земля, стены,
   цель как красная колонна.
3. `features.extract` считает левую / центральную / правую красную
   массу и центроид.
4. Три базовых контроллера делят одну выжимку.
5. Среда интегрирует `turn` и `forward`, режет столкновения,
   проверяет `engage`.

64×64 — параметр стенда, не обещание живого захвата.

## Навигационный стенд

`l2_brain.sim.SimulationEnvironment` — headless, без клиента.

- Агент: только `AgentView` (`Frame` + `dropped` / `action_delayed`).
- Оценщик: `GroundTruth` (позы, дистанция, контакт, стены). В
  `AgentView` этих полей нет.
- Вход — тот же `MotorIntent`, что у контура.
- Успех — достижение цели по координатам среды, не импульс `attack`.
- Камера перспективная (pitch + yaw). Поворот камеры без смещения
  тела — `camera_spin`.
- Сплиты: `training` / `validation` / `held_out`.

Успех стенда не есть перенос в MMORPG. Каталог Frozen 60 не
пересчитывать и не подкручивать (ADR-0030).

Отдельно: `combat_dummy_v0` и `multi_dummy_arena_v0` — не строки
Frozen 60. Пятно на кадре не есть лок. Нажатие атаки не есть урон.

## VisualEncoder

`NavigationEncoder` заполняет `contracts.Observation` и опциональный
`navigation`: сектора яркости/контраста/Δ, поток HxV, расширение,
пеленг красного пятна, гипотеза `approach|camera_turn|uncertain|low_confidence`.
Два масштаба: весь кадр и низ (`near_y0`). Эталон потока — CPU SAD.
Статические наложения режет профиль окна.

Mock-контур по умолчанию — `ColorBlobEncoder`.

`HUDParser` читает Classic-полосы и рамку цели с пикселей. Победа —
HP=0 на рамке или пропажа при HP ≤ 0.08. Сброс живой рамки
(Escape) — `TargetLost`, не `EntityDefeated` (F46–F47). Это не
политика и не память процесса.

## Базовый контроллер

`BaselineController` — прозрачная сумма вкладов, без обучения.
Калибровка **заморожена** (ADR-0030, канон 52/60). Скаляры и
таймеры не крутить. Новая политика — соседний пакет, не правка
этого класса.

При `recovery=true` (`baseline_memory_v1`): недавний пеленг, сторона
обхода, накопитель отсутствия продвижения, попытки восстановления.
Отступление в v1 — разворот на месте: `forward` ∈ [0, 1]. Имена
сцен в политике запрещены.

## Компактный GRU и SNN

`GRUController` — GRU H=16 на тех же 6 признаках, что `snn_core_v1`.
Чистый NumPy. Не стендовый `controllers.recurrent`.

`snn_core_v1` — LIF на CPU, рефлекс Брайтенберга. R-STDP на `w_in`
выключен по умолчанию. Не закрывает H3/H4 без прогона `evaluate`.

Синтетический экстракт `control/malecns/` — не дамп FlyEM и не H11.

## Локальное обучение

Награда — `RewardEngine` по `GroundTruth`. Дистанция не входит в
`Observation`. GRU может идти тем же скаляром через `GaussianES`.
Обучение не доказывает перенос в игру.

## Игровой ввод

`IntentDecoder` переводит `MotorIntent` в `GameAction` по
`GameInputProfile`. Профиль S4: F1=`/targetnext`, F2=Attack,
F3=Pickup, kill switch=F12, hold ≤ 500 мс.

Живой post — только `CGEventInputBackend` на PID хоста (Parallels).
Нет `prlctl exec` во время live. Нет инъекций в `L2.exe`.

Q5 (метры и yaw) не закрыт. F78: мышь→px зависит от тангажа и
сцены. F79: один тап стрелки дал KLT ≈40 px при ≥30 инлаерах и
ratio ≥0.70; профиль не писали (`|dx|<50`). `SEARCH=80`.
`--mouse-dy` крутит pitch. `parallels_l2.json` → `motion` только
при KLT `|median_dx| ≥ 50` и ≥30 инлаерах.

## Живой стенд Interlude (факт, не обещание)

| Поле | Значение |
|---|---|
| Игра | Lineage 2 Interlude (чат F44). Сборка unknown (Q1) |
| Запуск | Parallels Desktop, окно `Windows 11` на хосте (Q2, F40) |
| Сервер | `LineageII Interlude Server`, персонаж BotEbaniy, Talking Island (Q6, F48) |
| Захват | SCK, окно 13944, 4112×2580 (scale 2) |
| Ввод | CGEvent на PID консоли Parallels, не в гостевой процесс |
| S4 | короткие зонды F49–F55; урон и килл зафиксированы; фарм не открыт. Ход 83: F5 лок есть, HTML-окно не детектировано |

`on_screen=false` — стол не тот; в контур не кормить. Скрытый стол
гостя не источник.

## CLI

`python -m l2_brain <команда>` (скрипт `l2-brain` может быть не
установлен; пакет резолвится из `src/`).

| Команда | Назначение |
|---|---|
| `mock` / `record` / `replay` / `inspect` | контур на искусственных кадрах и сессии |
| `eval` | стенд `SyntheticEnv`, не Frozen 60 |
| `sim-eval` / `baseline-eval` | nav-sim; baseline-eval не крутить веса |
| `bench` / `suite` / `learn` / `malecns-eval` | мини-сравнения, не канон 52/60 |
| `capture` | list / permission / record SCK |
| `vision` | бенч энкодера |
| `input-dry-run` / `input-probe` / `focus-bench` | ввод без игры или Notepad |
| `calibrate-hud` / `calibrate-motion` | ROI; `--klt`; `--rmb`; `--sync-diag` T0/T1 |
| `bench-h8` | 100 тиков H8, без игровых клавиш |
| `live-motion` | один непрерывный `w`, 10+3 сэмпла потока, без фарма |
| `s4-probe` | один короткий боевой сценарий |
| `s4-integrated-spot` | L1 encoder + L2 FSM, до 10 фрагов; `--runtime-validation --kills 3` = R2, не F82; без фарма |
| `s4-npc-dialog` | мирный зонд: `--via-chat /target` → F2-подбег → ЛКМ (0.50, 0.48), HTML только слева, обход меню; `--runtime-validation` = R1 один пункт, не F85; без фарма |
| `layout-grid` / `layout-overlay` / `layout-slots` | PNG-снимок; живые рамки поверх Parallels (клики навылет); Tab/Escape слота Б после посадки. Сетка гостя 2560×1600: слот А `[60,140,400,520]`, слот Б `[2140,140,360,480]`; без фарма |
| `agent-live` | `LiveRuntime`: по умолчанию observe-only. `--skill` или `--task guide-open-close` только с dual flags. `--repeat` 1…10. Не фарм, не quest. Канон live Runtime — R1/R2; Task live нет |
| `combat-dry-run` / `spot-loop` | синтетический бой / спот |
| `profile` / `doctor` | стадии тика и окружение |

Живые команды требуют `--live --danger-confirmed`.

## Эксперименты и запись

`l2_brain.experiment` пишет сессию без блокировки политики (bounded
async writer). На тике отдельно: ожидание кадра, возраст, encode,
infer, decode, act, ожидание эффекта. Отчёт — p50/p95/p99 и `n`.

Воспроизведение: `offline`, `realtime` / `speed`, `step` / `inspect`.
Offline replay не доказывает успех другой политики: её действия
изменили бы будущие кадры.

Цифры в `docs/` — только после фактического прогона. `graphify-out/`
и `GRAPH_REPORT.md` не evidence.

## Что намеренно отсутствует

- планировщик квестов и таблица маршрутов;
- инвентарь и торговый автомат;
- разбор сетевого протокола и pcap;
- гостевой код внутри Windows-клиента;
- загрузчик полного MaleCNS / FlyEM;
- автовыбор Metal;
- замкнутый `Circuit` с SCK **и** CGEvent (нет такого builder);
- автономный фарм-цикл.

Слои можно добавить позже, не ломая стендовые `types.Observation` /
`Action` и контурные `contracts.Observation` / `MotorIntent`.

## Где ещё смотреть

| Документ | Роль |
|---|---|
| [project-brief.md](project-brief.md) | цель и границы v1 |
| [vision.md](vision.md) | критерий успеха v1 |
| [roadmap.md](roadmap.md) | этапы S0–S4 |
| [assumptions.md](assumptions.md) | факты F* и гипотезы H* |
| [decisions.md](decisions.md) | ADR |
| [open-questions.md](open-questions.md) | Q1–Q11 |
| [status.md](status.md) | текущий ход |
| `.cursor/rules/10-architecture.mdc` | запрет смешивать сенсор, политику и ввод |
