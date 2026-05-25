#!/usr/bin/python3
"""
Запуск приложения: python3 run.py
Браузер откроется сам. Остановка: Ctrl+C
"""
import sys
import os
import webbrowser
import threading
import time

# Проверяем, что используем правильный Python
if sys.version_info >= (3, 14):
    print("⚠️  ОБНАРУЖЕН СЛОМАННЫЙ Python 3.14 из Homebrew")
    print("   Используйте системный Python: /usr/bin/python3 run.py")
    sys.exit(1)

# ------------------------------------------------------------
# НАСТРОЙКА ПОДКЛЮЧЕНИЯ К OLLAMA
# ------------------------------------------------------------
os.environ.setdefault("OLLAMA_URL", "https://ollama.k2.iksi.edu")
os.environ.setdefault("OLLAMA_VERIFY_SSL", "false")

# ------------------------------------------------------------
# ПРОВЕРКА ДОСТУПНОСТИ OLLAMA
# ------------------------------------------------------------
try:
    from core import OllamaClient
    client = OllamaClient()
    if not client.check_connection():
        print("⚠️  ВНИМАНИЕ: Сервер Ollama не отвечает.")
        print("   Проверьте доступность сервера.\n")
    else:
        print("✅ Подключение к Ollama установлено.")
        models = client.get_available_models()
        if models:
            print(f"   Доступно моделей: {len(models)}")
        else:
            print("   ⚠️ Не удалось получить список моделей")
except Exception as e:
    print(f"⚠️  Не удалось проверить подключение: {e}")

# ------------------------------------------------------------
# ЗАПУСК ВЕБ-СЕРВЕРА
# ------------------------------------------------------------
try:
    import uvicorn
except ModuleNotFoundError:
    print("Нужен модуль uvicorn. Установите:")
    print("  /usr/bin/python3 -m pip install -r requirements.txt")
    sys.exit(1)


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000
    print("\nСервер запускается...")
    print(f"  http://{HOST}:{PORT}")
    print("Остановка: Ctrl+C\n")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host=HOST, port=PORT)