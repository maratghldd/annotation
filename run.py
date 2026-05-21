#!/usr/bin/env python3
"""
Запуск приложения: python run.py
Браузер откроется сам. Остановка: Ctrl+C
"""
import sys
import os
import webbrowser
import threading
import time

# ------------------------------------------------------------
# НАСТРОЙКА ПОДКЛЮЧЕНИЯ К OLLAMA (изменяемая часть)
# ------------------------------------------------------------
# Указываем базовый URL вашего сервера
os.environ.setdefault("OLLAMA_URL", "https://ollama.k2.iksi.edu")
# Отключаем проверку SSL (т.к. сертификат самоподписанный)
os.environ.setdefault("OLLAMA_VERIFY_SSL", "false")

# ------------------------------------------------------------
# ПРОВЕРКА ДОСТУПНОСТИ OLLAMA
# ------------------------------------------------------------
try:
    from core import OllamaClient
    client = OllamaClient()
    if not client.check_connection():
        print("⚠️  ВНИМАНИЕ: Сервер Ollama по адресу", os.environ["OLLAMA_URL"], "не отвечает.")
        print("   Проверьте доступность сервера.\n")
    else:
        print("✅ Подключение к Ollama установлено.")
        print(f"   Настроенные модели:")
        print(f"     - Перевод: {client.config.translate_model}")
        print(f"     - Аннотирование: {client.config.annotate_model}")
        print(f"     - Проверка: {client.config.review_model}")
except Exception as e:
    print(f"⚠️  Не удалось проверить подключение к Ollama: {e}")

# ------------------------------------------------------------
# ЗАПУСК ВЕБ-СЕРВЕРА
# ------------------------------------------------------------
try:
    import uvicorn
except ModuleNotFoundError:
    print("Нужен модуль uvicorn. Установите зависимости:")
    print("  pip install -r requirements.txt")
    print("или:  pip install uvicorn")
    sys.exit(1)


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000
    print("Сервер запускается...")
    print(f"  http://{HOST}:{PORT}")
    print("Остановка: Ctrl+C")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host=HOST, port=PORT)