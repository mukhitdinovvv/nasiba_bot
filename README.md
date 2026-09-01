# Telegram-бот Насибы

Простой и стабильный бот на pyTelegramBotAPI: выдаёт бесплатные материалы
по deep-link, продаёт диагностику блога за 3 000 ₸, принимает чек об оплате,
после ручного подтверждения администратором собирает бриф и записывает
клиента в Google Calendar с автоматическими напоминаниями.

Никакой CRM, никакой веб-админки — вся админка прямо в Telegram (`/admin`).

## Содержание

1. Установка Python
2. Создание virtual environment
3. Установка зависимостей
4. Настройка .env
5. Получение Telegram Bot Token
6. ADMIN_TELEGRAM_ID
7. Подключение Google Calendar
8. Запуск локально
9. Запуск на VPS
10. Настройка systemd
11. Как добавить новый материал
12. Как создать deep-link
13. Структура проекта

---

## 1. Установка Python

Нужен Python 3.12 или новее.

```bash
python3 --version
```

Если версия ниже 3.12, установи актуальный Python (на Ubuntu 24.04 он уже
идёт в системе).

## 2. Создание virtual environment

```bash
cd nasiba_bot
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

## 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 4. Настройка .env

Скопируй пример и заполни своими значениями:

```bash
cp .env.example .env
```

Поля:

- `BOT_TOKEN` — токен бота от @BotFather.
- `ADMIN_TELEGRAM_ID` — твой Telegram ID (число). Узнать его можно у бота
  @userinfobot.
- `TELEGRAM_CHANNEL_USERNAME` — username канала, если используется (можно
  оставить пустым).
- `KASPI_PAYMENT_URL` — ссылка на оплату Kaspi Pay.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` —
  данные из Google Cloud Console (см. пункт 7). Для скрипта одноразовой
  авторизации (`google_auth.py`) достаточно файла `credentials.json`,
  эти переменные окружения дублируют его данные и не обязательны, если
  credentials.json уже на месте.
- `GOOGLE_CALENDAR_ID` — обычно `primary`, либо ID отдельного календаря.
- `TIMEZONE` — часовой пояс, по умолчанию `Asia/Almaty`.
- `WORK_START`, `WORK_END` — рабочие часы для записи.
- `APPOINTMENT_DURATION` — длительность диагностики в минутах (по умолчанию 40).

## 5. Получение Telegram Bot Token

1. Напиши @BotFather в Telegram.
2. Команда `/newbot`, следуй инструкциям.
3. Скопируй токен в `BOT_TOKEN` в `.env`.
4. Обязательно запомни username бота (например `@nasiba_blog_bot`) — он
   нужен для deep-link. Бот определит его сам при старте, но можно
   прописать вручную в `BOT_USERNAME` в `.env`.

## 6. ADMIN_TELEGRAM_ID

Права администратора проверяются строго по Telegram ID (число), а не по
username. Узнать свой ID можно, написав боту @userinfobot.

Указывается один ID — бот рассчитан на одного администратора (Насибу).

## 7. Подключение Google Calendar

1. Зайди в [Google Cloud Console](https://console.cloud.google.com/).
2. Создай проект (или используй существующий).
3. Включи **Google Calendar API** (APIs & Services -> Library).
4. Создай OAuth-клиент: APIs & Services -> Credentials -> Create Credentials
   -> OAuth client ID. Есть два варианта типа клиента:

   - **Desktop app** — рекомендуется, ничего дополнительно настраивать не
     нужно.
   - **Web application** — тоже подходит, но тогда обязательно добавь в
     этом клиенте (Credentials -> клиент -> Authorized redirect URIs)
     значение:

     ```
     http://localhost:8080/
     ```

     Без этого шага при авторизации Google вернёт ошибку
     `redirect_uri_mismatch`.

5. Скачай JSON-файл, переименуй в `credentials.json` и положи в папку
   `google/`. Скрипт авторизации сам определит, какой у тебя тип клиента.
6. Запусти одноразовую авторизацию (лучше на компьютере с браузером):

   ```bash
   python google_auth.py
   ```

   Откроется браузер, войди в Google-аккаунт, который ведёт нужный
   календарь, и разреши доступ. Появится файл `google/token.json`.

7. Если бот работает на VPS без браузера — выполни шаг 6 локально, а
   потом скопируй `google/token.json` на сервер:

   ```bash
   scp google/token.json user@your-server:/path/to/nasiba_bot/google/
   ```

8. Узнать `GOOGLE_CALENDAR_ID`: Google Calendar -> Настройки календаря ->
   «Интеграция» -> Идентификатор календаря. Для личного календаря обычно
   подходит `primary`.

Токен обновляется автоматически (`refresh_token`), повторную авторизацию
делать не нужно, пока доступ не будет отозван вручную.

## 8. Запуск локально

```bash
python main.py
```

Бот начнёт отвечать в Telegram. Логи пишутся в консоль и в файл `bot.log`.

## 9. Запуск на VPS

Минимальные требования: Ubuntu 24.04, 1 CPU, 1 GB RAM, 20 GB SSD.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone <ссылка на репозиторий> nasiba_bot
cd nasiba_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # и заполнить
```

Положи `google/credentials.json` и `google/token.json` (см. пункт 7).

## 10. Настройка systemd

Создай файл `/etc/systemd/system/nasiba-bot.service`:

```ini
[Unit]
Description=Nasiba Telegram Bot
After=network.target

[Service]
Type=simple
User=<твой пользователь>
WorkingDirectory=/path/to/nasiba_bot
ExecStart=/path/to/nasiba_bot/venv/bin/python /path/to/nasiba_bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Дальше:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nasiba-bot
sudo systemctl start nasiba-bot
sudo systemctl status nasiba-bot
```

Логи:

```bash
journalctl -u nasiba-bot -f
```

После перезагрузки сервера бот запустится автоматически благодаря
`WantedBy=multi-user.target` и `enable`.

## 11. Как добавить новый материал

Всё делается внутри Telegram, без доступа к коду и без загрузки файлов на
сервер (используется Telegram file_id).

1. Напиши боту `/admin`.
2. Нажми **📚 Материалы**.
3. Нажми **➕ Добавить материал**.
4. Введи название, например: `200+ идей лид-магнитов`.
5. Введи slug (латиницей, без пробелов), например: `ideas`.
6. Введи короткое описание.
7. Отправь файл (PDF, документ или фото).

Бот пришлёт готовую ссылку:

```
https://t.me/BOT_USERNAME?start=ideas
```

## 12. Как создать deep-link

Deep-link создаётся автоматически на основе slug материала — ничего
прописывать в коде не нужно. Формат:

```
https://t.me/BOT_USERNAME?start=<slug>
```

Примеры:

- `https://t.me/BOT_USERNAME?start=ideas`
- `https://t.me/BOT_USERNAME?start=questions`
- `https://t.me/BOT_USERNAME?start=checklist`

Эти ссылки можно размещать в Instagram (шапка профиля, сторис, посты),
TikTok, рекламе, на сайте — где угодно. Сама автоматизация Instagram
Direct в этот проект не входит: Telegram-бот просто принимает
`/start <slug>` и отдаёт нужный материал.

## 13. Структура проекта

```
project/
    main.py                 — точка входа, запуск бота
    config.py                — все настройки из .env
    database/                — доступ к SQLite (database/__init__.py) + схема (models.py)
    requirements.txt
    .env / .env.example
    google_auth.py           — одноразовая OAuth-авторизация Google Calendar

    bot/
        handlers/             — обработчики Telegram-команд и кнопок
            start.py            /start, deep-link, согласие, главное меню
            materials.py        выдача бесплатных материалов
            diagnostics.py      меню диагностики
            payment.py          оплата, приём чека, подтверждение/отклонение
            brief.py            анкета (бриф) перед диагностикой
            calendar.py         выбор даты/времени, создание события
            products.py         каталог продуктов
            admin.py            админка внутри Telegram
        keyboards/            — инлайн-клавиатуры
        messages/texts.py     — все тексты сообщений

    services/
        calendar_service.py   — Google Calendar API
        payment_service.py    — вспомогательная логика оплаты
        material_service.py   — вспомогательная логика материалов

    utils/
        helpers.py             мелкие утилиты (проверка админа, форматирование)
        scheduler.py            APScheduler-напоминания за 24ч и за 1ч

    google/
        credentials.json (не в репозитории)
        token.json (не в репозитории)
```

> Примечание: по ТЗ база данных называется `database.py`, но так как в
> проекте также требовалась папка `database/` со схемой (`models.py`),
> они объединены в один пакет `database/` — `database/__init__.py`
> содержит весь код доступа к БД, а импортируется он точно так же:
> `import database`. Ничего в поведении не меняется.

## Что бот не делает (сознательно)

- Не проверяет оплату Kaspi автоматически — только вручную, через кнопки
  администратора «✅ Подтвердить» / «❌ Отклонить».
- Не хранит файлы материалов на сервере — только Telegram file_id.
- Не имеет отдельной веб-админки — вся админка в Telegram (`/admin`).
- Не имеет сложной системы ролей — один администратор по `ADMIN_TELEGRAM_ID`.
