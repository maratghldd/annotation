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
# Измените эту переменную для переключения:
#   "remote" — удалённый сервер (ollama.k2.iksi.edu)
#   "local"  — локальная Ollama на вашем компьютере
OLLAMA_MODE = "local"  # ← МЕНЯТЬ ЗДЕСЬ

# Устанавливаем переменную окружения для app.py
os.environ["OLLAMA_MODE"] = OLLAMA_MODE

if OLLAMA_MODE == "local":
    # Локальная Ollama
    os.environ.setdefault("OLLAMA_LOCAL_URL", "http://localhost:11434")
    print("📍 Режим: ЛОКАЛЬНАЯ OLLAMA (localhost:11434)")
    from core.ollama_local import OllamaLocalClient as OllamaClient
    from config_local import ollama_local_config as ollama_config
else:
    # Удалённая Ollama
    os.environ.setdefault("OLLAMA_URL", "https://ollama.k2.iksi.edu")
    os.environ.setdefault("OLLAMA_VERIFY_SSL", "false")
    print(f"📍 Режим: УДАЛЁННАЯ OLLAMA ({os.environ.get('OLLAMA_URL')})")
    from core.ollama_models import OllamaClient
    from config import ollama_config

# ------------------------------------------------------------
# ПРОВЕРКА ДОСТУПНОСТИ OLLAMA
# ------------------------------------------------------------
try:
    client = OllamaClient()
    if not client.check_connection():
        print("⚠️  ВНИМАНИЕ: Ollama не отвечает.")
        if OLLAMA_MODE == "local":
            print("   Запустите: ollama serve")
        else:
            print("   Проверьте доступность сервера.\n")
    else:
        print("✅ Подключение к Ollama установлено.")
        models = client.get_available_models()
        if models:
            print(f"   Доступно моделей: {len(models)}")
            print(f"   Модели: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
        else:
            print("   ⚠️ Не удалось получить список моделей")
            if OLLAMA_MODE == "local":
                print("   Скачайте модель: ollama pull qwen2.5:32b")
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