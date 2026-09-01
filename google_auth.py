"""
Одноразовая авторизация Google Calendar.

Запускается ОДИН РАЗ вручную (лучше на компьютере с браузером, не на VPS):

    python google_auth.py

Скрипт откроет браузер, попросит войти в Google-аккаунт администратора
и даст доступ к календарю. После этого будет создан файл google/token.json —
его нужно скопировать на сервер рядом с ботом (в папку google/).

Перед запуском нужно положить файл google/credentials.json — это файл
OAuth-клиента из Google Cloud Console (APIs & Services -> Credentials ->
OAuth client ID). Поддерживаются оба типа клиента:

- "Desktop app" — рекомендуется, работает без дополнительной настройки.
- "Web application" — тоже работает, но в Google Cloud Console у этого
  клиента обязательно должен быть добавлен redirect URI:

      http://localhost:8080/

  (Credentials -> твой OAuth client -> Authorized redirect URIs -> Add URI).
  Без этого шага Google вернёт ошибку "redirect_uri_mismatch".
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]
LOCAL_PORT = 8080  # фиксированный порт, чтобы redirect URI был предсказуемым


def _client_type(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "web" in data:
        return "web"
    if "installed" in data:
        return "installed"
    return "unknown"


def main():
    if not os.path.exists(config.GOOGLE_CREDENTIALS_PATH):
        raise SystemExit(
            f"Не найден файл {config.GOOGLE_CREDENTIALS_PATH}.\n"
            "Скачай его в Google Cloud Console (OAuth client ID) "
            "и положи в папку google/ под именем credentials.json."
        )

    client_type = _client_type(config.GOOGLE_CREDENTIALS_PATH)
    if client_type == "web":
        print(
            "Обнаружен клиент типа Web application.\n"
            f"Убедись, что в Google Cloud Console в этом OAuth-клиенте добавлен\n"
            f"Authorized redirect URI: http://localhost:{LOCAL_PORT}/\n"
            "Иначе авторизация завершится ошибкой redirect_uri_mismatch.\n"
        )

    flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=LOCAL_PORT)

    with open(config.GOOGLE_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"Готово! Токен сохранён в {config.GOOGLE_TOKEN_PATH}.")
    print("Скопируй этот файл на сервер, в папку google/, рядом с ботом.")


if __name__ == "__main__":
    main()
