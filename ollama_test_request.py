import requests
import os
import urllib3

# Отключаем предупреждения об отсутствии SSL-сертификата (для https:// с verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Базовые настройки
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "https://ollama.k2.iksi.edu").rstrip("/")
# Для локальных запросов SSL проверка обычно не нужна
VERIFY_SSL = False

def get_available_models():
    """Получает список установленных моделей из Ollama."""
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        response = requests.get(url, verify=VERIFY_SSL, timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [m["name"] for m in models]
        return []
    except Exception as e:
        print(f"Ошибка при получении списка моделей: {e}")
        return []

def send_test_request(model_name, prompt="Привет! Это тестовый запрос."):
    """Отправляет запрос к выбранной модели Ollama."""
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "think": False,
    }

    try:
        print(f"\nОтправка запроса к {url} (модель: {model_name})...")
        response = requests.post(
            url,
            json=payload,
            timeout=(10, 120),
            verify=VERIFY_SSL
        )

        if response.status_code == 200:
            result = response.json()
            answer = result.get("response", "")
            print("\nУспешный ответ от модели:")
            print("-" * 20)
            print(answer)
            print("-" * 20)
            return answer
        else:
            print(f"Ошибка API: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return None

if __name__ == "__main__":
    print(f"Подключение к Ollama по адресу: {OLLAMA_BASE_URL}")
    models = get_available_models()

    if not models:
        print("Доступные модели не найдены. Убедитесь, что Ollama запущена.")
    else:
        print("\nДоступные модели:")
        for i, m in enumerate(models, 1):
            print(f"{i}. {m}")

        try:
            choice = input(f"\nВыберите номер модели (1-{len(models)}) или введите название вручную: ")
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                selected_model = models[int(choice) - 1]
            else:
                selected_model = choice if choice else models[0]

            send_test_request(selected_model)
        except KeyboardInterrupt:
            print("\nОтменено.")