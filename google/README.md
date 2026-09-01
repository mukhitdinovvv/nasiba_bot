# Папка для Google-ключей

Сюда нужно положить два файла (оба в .gitignore — в репозиторий не попадают):

1. `credentials.json` — OAuth-клиент, скачивается в Google Cloud Console
   (APIs & Services -> Credentials -> OAuth client ID -> Desktop app).
2. `token.json` — создаётся автоматически после запуска `python google_auth.py`
   (см. README.md в корне проекта, раздел про Google Calendar).

Без этих файлов бот будет работать, но раздел с записью на диагностику
(выбор времени, создание события) будет присылать сообщение о том, что
календарь недоступен.
