#!/usr/bin/python3
"""
Запуск приложения: python3 run.py
Браузер откроется сам. Остановка: Ctrl+C
"""
import sys
import os
import json
import webbrowser
import threading
import time
import subprocess

# Проверяем, что используем правильный Python
if sys.version_info >= (3, 14):
    print("⚠️  ОБНАРУЖЕН СЛОМАННЫЙ Python 3.14 из Homebrew")
    print("   Используйте системный Python: /usr/bin/python3 run.py")
    sys.exit(1)

# ------------------------------------------------------------
# НАСТРОЙКА ПОДКЛЮЧЕНИЯ К OLLAMA
# ------------------------------------------------------------
# Режим теперь хранится в файле mode_config.json и меняется через веб-интерфейс
# Можно временно переопределить здесь для отладки:
OLLAMA_MODE_OVERRIDE = None  # "local" или "remote" или None (читать из файла)

MODE_CONFIG_FILE = "mode_config.json"

def load_ollama_mode():
    """Загружает режим из файла конфигурации."""
    if OLLAMA_MODE_OVERRIDE:
        return OLLAMA_MODE_OVERRIDE
    
    try:
        with open(MODE_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("ollama_mode", "remote")
    except FileNotFoundError:
        # Если файла нет — создаем с режимом по умолчанию
        save_ollama_mode("remote")
        return "remote"
    except Exception as e:
        print(f"⚠️  Ошибка чтения режима: {e}, используем remote")
        return "remote"

def save_ollama_mode(mode: str):
    """Сохраняет режим в файл конфигурации."""
    try:
        with open(MODE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"ollama_mode": mode}, f, indent=4)
    except Exception as e:
        print(f"⚠️  Ошибка сохранения режима: {e}")

OLLAMA_MODE = load_ollama_mode()

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


def run_server():
    """Запускает сервер uvicorn как subprocess и перезапускает при необходимости."""
    HOST = "127.0.0.1"
    PORT = 8000

    print("\n🚀 Запуск сервера...")
    print(f"  http://{HOST}:{PORT}")
    print("Остановка: Ctrl+C\n")
    
    uvicorn_process = None
    
    try:
        while True:
            # Читаем текущий режим
            current_mode = load_ollama_mode()
            print(f"📍 Режим: {current_mode.upper()}")
            
            # Запускаем uvicorn как subprocess
            uvicorn_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(PORT)],
                env=os.environ
            )
            
            # Ждём завершения subprocess
            uvicorn_process.wait()
            
            # Проверяем код выхода
            exit_code = uvicorn_process.returncode
            
            if exit_code == 3:  # Код 3 означает перезапуск
                print("\n🔄 Получен сигнал перезапуска (код 3)")
                print("   Перезапуск через 1 секунду...")
                time.sleep(1)
                continue  # Перезапускаем цикл
            else:
                print(f"\n🛑 Сервер остановлен (код {exit_code})")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Остановка пользователем (Ctrl+C)...")
    finally:
        # Убиваем процесс если ещё жив
        if uvicorn_process and uvicorn_process.poll() is None:
            uvicorn_process.terminate()
            uvicorn_process.wait()
        print("   Готово.")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    run_server()
