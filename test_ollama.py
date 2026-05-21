"""Тестовый скрипт для проверки подключения к Ollama - точная копия эталонного кода."""
import requests
import urllib3
import sys

# Отключаем предупреждения о самоподписанных сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Базовый URL
BASE_URL = "https://ollama.k2.iksi.edu"


def get_available_models():
    """Запрашивает список доступных моделей у Ollama"""
    try:
        # Эндпоинт для получения списка моделей
        response = requests.get(
            f"{BASE_URL}/api/tags",
            verify=False,
            timeout=(10, 30)
        )
        response.raise_for_status()
        data = response.json()

        models = data.get('models', [])
        if not models:
            print("Ошибка: Список моделей пуст.")
            return None

        return models
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при подключении к API сервера моделей: {e}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return None


def select_model(models):
    """Предлагает пользователю выбрать модель из списка"""
    print("\n--- Доступные модели ---")
    for idx, model in enumerate(models):
        # Ollama возвращает 'name' в объекте модели
        name = model.get('name', 'Неизвестное имя')
        print(f"{idx + 1}. {name}")

    print("------------------------")

    while True:
        try:
            choice = input(f"Выберите номер модели (1-{len(models)}): ").strip()
            index = int(choice)
            if 1 <= index <= len(models):
                selected_model = models[index - 1].get('name')
                print(f"Выбрана модель: {selected_model}\n")
                return selected_model
            else:
                print("Неверный номер. Попробуйте снова.")
        except ValueError:
            print("Пожалуйста, введите число.")
        except KeyboardInterrupt:
            print("\nВыбор отменен.")
            sys.exit(0)


if __name__ == "__main__":
    print("Инициализация соединения с Ollama...")

    # 1. Получаем список моделей
    models_list = get_available_models()

    if not models_list:
        print("Не удалось получить список моделей. Завершение работы.")
        sys.exit(1)

    # 2. Пользователь выбирает модель
    chosen_model = select_model(models_list)

    if chosen_model:
        print(f"Итоговый выбор: {chosen_model}")
