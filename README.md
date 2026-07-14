# Контроль заполненности очереди в ROI

Приложение в реальном времени детектирует людей в видеопотоке и отправляет
уведомление «Откройте вторую кассу», когда заданная зона ожидания достигает
настроенной вместимости.

В текущем тестовом режиме человек относится к ROI, если его `bbox` хотя бы
касается выпуклого полигона или пересекает его. Площадь пересечения и специальные
опорные точки не вычисляются. В подсчёт входят только уникальные `track_id`,
поэтому один человек не может быть посчитан дважды в одном кадре.

## Поток обработки

```text
camera / file / RTSP
        ↓
OpenCV → YOLO → ByteTrack
        ↓
bbox пересекает ConvexPolygonRoi?
        ↓
QueueOccupancyMonitor
        ├──→ JSONL + JPEG
        └──→ asyncio.Queue → Telegram Bot API через HTTP proxy
```

OpenCV, YOLO и ByteTrack обрабатываются последовательно в одном выделенном
потоке, чтобы сохранить порядок кадров и состояние трекера. Telegram работает
асинхронно и не блокирует видеоконвейер.

## Состояния очереди

```text
available
   ↓ достигнута вместимость
confirming_full
   ↓ нужное число кадров подряд
full → одно уведомление
   ↓ количество стало меньше вместимости
recovering
   ↓ устойчивое освобождение
available
```

Если ROI снова заполняется до завершения `recovering`, повторное уведомление не
создаётся. Дополнительный cooldown ограничивает частоту событий после полностью
завершённых циклов заполнения и освобождения.

## Конфигурация

Все настройки читаются через отдельные Pydantic Settings-секции из `.env` или
из файла, переданного через `--env-file`.

Подготовка локального файла:

```bash
cp .env.example .env
```

Минимальный тест с одним человеком:

```dotenv
CAMERA_SOURCE=test.mp4
CAMERA_SOURCE_KIND=file

ROI_POINTS=[[0.40,0.35],[0.60,0.35],[0.60,0.75],[0.40,0.75]]

EVENT_ROI_CAPACITY=1
EVENT_FULL_CONFIRM_FRAMES=5
EVENT_RECOVERY_CONFIRM_FRAMES=10
EVENT_COOLDOWN_SECONDS=60.0

NOTIFICATION_ALERT_MESSAGE="⚠️ Откройте вторую кассу"

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_PROXY_URL=http://login:password@proxy.example:3128
TELEGRAM_SEND_SNAPSHOT=true
```

`ROI_POINTS` — JSON-массив нормализованных координат `[x, y]` в диапазоне
`[0, 1]`. Поддерживается простой выпуклый полигон с вершинами по часовой или
против часовой стрелки. Касание bbox границы ROI считается пересечением.

Для рабочей кассы после теста достаточно заменить ROI и вместимость:

```dotenv
EVENT_ROI_CAPACITY=5
```

`TELEGRAM_BOT_TOKEN` и `TELEGRAM_PROXY_URL` хранятся как `SecretStr`. Файл `.env`
игнорируется Git. Токен и полный proxy URL удаляются из внутренних HTTPX-логов.

## Запуск

С реальным Telegram:

```bash
uv run python main.py
```

Без обращения к Telegram:

```bash
uv run python main.py --dry-run
```

Окно с детекцией в реальном времени (закрыть — клавиша `q`):

```bash
uv run python main.py --preview
```

Другой файл настроек:

```bash
uv run python main.py --env-file deployment/camera-1.env
```

## Переключение источника: камера или экран

Источник задаётся `CAMERA_SOURCE_KIND` в `.env`, но сценарий можно быстро
переопределить на запуске флагом `--source`, не редактируя файлы:

```bash
uv run python main.py --source camera --preview
uv run python main.py --source screen    # захват рабочего стола
uv run python main.py --source screen --overlay
uv run python main.py --source file      # видеофайл из CAMERA_SOURCE
```

Для захвата экрана (`screen`) используются `CAMERA_SCREEN_MONITOR` (номер
монитора, `1` — основной), необязательный `CAMERA_SCREEN_REGION=[left,top,width,height]`
и `CAMERA_SCREEN_FPS`. Флаг `--source` совместим с `--preview` и `--dry-run`,
например «посмотреть детекцию с экрана без Telegram»:

```bash
uv run python main.py --source screen --preview --dry-run
```

### Разметка поверх рабочего стола

Флаг `--overlay` рисует ROI и рамки прозрачным слоем прямо поверх экрана, без
отдельного окна:

```bash
uv run python main.py --source screen --overlay
```

Оверлей не перехватывает клики (мышь проходит насквозь) и исключён из захвата
(`WDA_EXCLUDEFROMCAPTURE`), поэтому собственная разметка не попадает обратно в
кадр, в снимки событий и не мешает детекции. Флаг доступен только вместе с
`--source screen` и требует Windows 10 версии 2004 или новее. Закрывается вместе
с приложением по `Ctrl+C`.

Процесс работает, пока открыт терминал и не получен `Ctrl+C`. Для постоянного
развёртывания следует запускать отдельный экземпляр приложения на камеру через
`systemd` или контейнер с политикой автоматического перезапуска.

## Первый end-to-end тест

1. Указать доступный видеофайл, устройство или RTSP-поток в `CAMERA_SOURCE`.
2. Оставить тестовую вместимость `1` и маленькую ROI.
3. Запустить приложение без `--dry-run`.
4. Войти в кадр так, чтобы `bbox` пересекал нарисованную ROI минимум пять
   обработанных кадров.
5. Проверить одно сообщение и JPEG в Telegram.
6. Остаться внутри и убедиться, что повторных сообщений нет.
7. Выйти минимум на десять кадров и войти снова: должно прийти новое сообщение.

## Проверки

Тесты покрывают пересечение bbox с ROI, уникальные track ID, подтверждение
заполнения, recovery, cooldown, разрывы кадров, конфигурацию, Telegram и
жизненный цикл асинхронной очереди.

```bash
uv run python -m unittest discover
```
