# Контроль выхода людей из ROI

Приложение детектирует и отслеживает людей в видеопотоке. Для каждого bbox
вычисляется точная площадь пересечения с выпуклым ROI. Бизнес-правило не
настраивается произвольным порогом:

```text
outside_area > inside_area  → выход
outside_area = inside_area  → нейтральная граница
outside_area < inside_area  → внутри
```

Равенство не создаёт событие и не подтверждает нахождение внутри.

## Архитектура

```text
camera/file/RTSP
       ↓
single-thread vision executor: OpenCV + YOLO + ByteTrack
       ↓
ConvexPolygonRoi → RoiAreaRelation enum
       ↓
BboxExitMonitor (state machine на каждый track_id)
       ├──→ JSONL + JPEG
       └──→ asyncio.Queue → async Telegram Bot API
```

Основной CV-конвейер оставлен синхронным внутри каждого кадра: ByteTrack зависит
от порядка кадров. Блокирующие `VideoCapture.read()` и `YOLO.track()` выполняются
в отдельном executor ровно с одним потоком, поэтому порядок и thread affinity не
нарушаются. Модель лениво загружается там же при первом кадре, а event loop
остаётся свободным для Telegram, retry и shutdown.

Основные пакеты:

```text
people_monitor/
├── config/            # отдельные BaseSettings-секции и корневой AppConfig
├── domain/            # immutable dataclass, enum и тип Frame
├── detection/         # контракт трекера и адаптер Ultralytics
├── geometry/          # валидация и clipping выпуклого ROI
├── events/            # автомат состояний track_id
├── notifications/     # async Telegram, logging и bounded queue
├── pipeline/          # упорядоченная обработка кадров
├── storage/           # потокобезопасный JSONL
├── video/             # протокол FrameSource и OpenCV-адаптер
└── visualization/     # ROI, bbox, состояния и track_id
```

## Настройки

TOML и ручной парсер не используются. Каждая секция в
`people_monitor/config/` является самостоятельным `BaseSettings`-классом со
своим коротким env-префиксом:

| Секция | Префикс |
|---|---|
| `CameraConfig` | `CAMERA_` |
| `ModelConfig` | `MODEL_` |
| `RoiConfig` | `ROI_` |
| `EventConfig` | `EVENT_` |
| `NotificationConfig` | `NOTIFICATION_` |
| `TelegramConfig` | `TELEGRAM_` |
| `OutputConfig` | `OUTPUT_` |
| `VisualizationConfig` | `VISUALIZATION_` |
| `RuntimeConfig` | `RUNTIME_` |

Поля секций задаются плоскими именами без общего префикса.
`AppConfig.from_env()` собирает готовую конфигурацию приложения из этих секций.
Способы загрузки:

```python
from people_monitor.config import AppConfig

AppConfig.from_env()                       # прочитать .env
AppConfig.from_env("camera-1.env")         # прочитать указанный файл
AppConfig.from_env(None)                   # не читать dotenv
```

Значения из environment имеют приоритет над env-файлом.

Подготовка локального файла:

```bash
cp .env.example .env
```

Примеры:

```dotenv
CAMERA_SOURCE=test.mp4
MODEL_CONFIDENCE=0.35
EVENT_OUTSIDE_CONFIRM_FRAMES=5
TELEGRAM_ENABLED=false
```

ROI передаётся как JSON-массив нормализованных координат:

```dotenv
ROI_POINTS=[[0.10,0.20],[0.90,0.20],[0.90,0.90],[0.10,0.90]]
```

Поддерживается только простой выпуклый полигон. Повторяющиеся вершины,
самопересечение, нулевая площадь и координаты вне диапазона `[0, 1]`
отклоняются при старте.

Секрет Telegram хранится как `SecretStr`:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Он не сериализуется и не попадает в сообщения об HTTP-ошибках.
Размер очереди и правила graceful shutdown не привязаны к Telegram и находятся
в секции `NOTIFICATION_*`. Поэтому канал доставки можно заменить
без изменения видеоконвейера. Для drain очереди и закрытия notifier предусмотрены
раздельные timeout, чтобы зависшая отправка не лишала HTTP-клиент cleanup.

## Подтверждение события

Для каждого `track_id` используется закрытое состояние:

1. `OBSERVING` — трек ещё не подтверждён внутри.
2. `ARMED` — внутренняя площадь преобладала нужное число кадров.
3. `NOTIFIED` — выход отправлен; повтор возможен после подтверждённого возврата.

`OUTSIDE_CONFIRM_FRAMES` фильтрует дрожание bbox. Пропуск кадра сбрасывает
текущий streak. Дубликаты одного `track_id` в кадре объединяются по максимальной
уверенности. Cooldown использует монотонные часы, а время видео хранится отдельно.

## Запуск

Локальная проверка без Telegram:

```bash
python main.py --dry-run
```

В этом режиме используется `LoggingNotifier`; Telegram credentials не нужны,
даже если `TELEGRAM_ENABLED=true`.

Другой env-файл:

```bash
python main.py --env-file deployment/camera-1.env
```

CLI передаёт этот путь в `AppConfig.from_env(...)`; без `--env-file` вызывается
`AppConfig.from_env()` и загружается `.env`.

Обычный режим использует `.env`:

```bash
python main.py
```

`CAMERA_SOURCE` принимает путь, RTSP URL или строковый индекс камеры.
Интерпретацию можно зафиксировать через
`CAMERA_SOURCE_KIND=file|stream|device|auto`. Для live-источника
настраиваются backend timeout и ограниченный exponential reconnect:

```dotenv
CAMERA_STREAM_OPEN_TIMEOUT_MILLISECONDS=10000
CAMERA_STREAM_READ_TIMEOUT_MILLISECONDS=10000
CAMERA_RECONNECT_ATTEMPTS=5
CAMERA_RECONNECT_BACKOFF_SECONDS=1.0
CAMERA_RECONNECT_MAX_BACKOFF_SECONDS=30.0
```

Для файла `read() == false` означает EOF. Для камеры или сетевого потока это
считается сбоем и запускает переподключение; после исчерпания попыток приложение
завершается с явной ошибкой. Backoff прерывается сразу при shutdown. После
успешного reconnect сбрасываются ByteTrack и состояния событий, поэтому старый
streak не может породить ложное уведомление на новом участке потока.

OpenCV timeout зависит от выбранного video backend. Если native-вызов
`VideoCapture.open/read` игнорирует timeout, Python не может безопасно прервать
уже выполняющийся вызов в потоке. Для жёсткой гарантии остановки такой capture
нужно изолировать отдельным процессом; текущая реализация сохраняет event loop
отзывчивым и гарантированно прерывает только Python-level retry/backoff.

## Проверки

В `tests/` описаны сценарии геометрии, равенства площадей, пропусков кадров,
duplicate track ID, cooldown, env precedence, жизненного цикла async worker и
безопасной обработки ошибок Telegram, а также EOF/reconnect источника OpenCV.

```bash
python -m unittest discover
```
