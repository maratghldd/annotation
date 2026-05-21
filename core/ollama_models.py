"""Ollama клиент с поддержкой конфигурируемых моделей для разных задач."""
import os
import urllib3
import requests
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OllamaModelConfig:
    """Конфигурация моделей для разных задач."""

    def __init__(self, translate_model: str, annotate_model: str, review_model: str):
        if not translate_model or not translate_model.strip():
            raise ValueError("Модель для перевода обязательна")
        if not annotate_model or not annotate_model.strip():
            raise ValueError("Модель для аннотирования обязательна")
        if not review_model or not review_model.strip():
            raise ValueError("Модель для проверки обязательна")
            
        self.translate_model = translate_model.strip()
        self.annotate_model = annotate_model.strip()
        self.review_model = review_model.strip()


class OllamaClient:
    """Клиент для работы с Ollama API."""

    def __init__(self, base_url: Optional[str] = None, config: Optional[OllamaModelConfig] = None):
        raw_url = base_url or os.environ.get("OLLAMA_URL", "https://ollama.k2.iksi.edu")
        self.base_url = raw_url.rstrip("/")
        self.generate_url = f"{self.base_url}/api/generate"
        self.config = config
        self.verify = False
    
    def _call_model(self, model: str, prompt: str, timeout: tuple = (10, 300)) -> str:
        """Вызов конкретной модели."""
        if not model or not model.strip():
            raise ValueError("Модель не указана для вызова")

        payload = {
            "model": model.strip(),
            "prompt": prompt,
            "stream": False,
            "think": False,
        }
        try:
            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=timeout,
                verify=self.verify,
            )
            response.raise_for_status()
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            return ""
        except Exception as e:
            print(f"Ошибка Ollama ({model}): {e}")
            return ""
    
    def translate_text(self, text: str) -> str:
        """Переводит текст на русский, если он на украинском."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
        if not text or len(text.strip()) < 20:
            return text

        prompt = f"""Определи язык текста. Если текст на УКРАИНСКОМ языке, ПЕРЕВЕДИ его на РУССКИЙ. 
Если текст уже на РУССКОМ, просто верни его БЕЗ ИЗМЕНЕНИЙ.
Не добавляй никаких пояснений, только результат.

Текст:
{text[:2000]}"""
        
        translated = self._call_model(self.config.translate_model, prompt)
        return translated if translated else text

    def generate_annotation(self, text: str, filename: str) -> str:
        """Создает первичную подробную аннотацию (заголовок)."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
            
        prompt = f"""Проанализируй текст документа и придумай развёрнутое, понятное название (8-15 слов) на РУССКОМ языке.
Название должно отражать суть документа.

Имя файла: {filename}
Текст:
{text[:3000]}

Название:"""
        return self._call_model(self.config.annotate_model, prompt)

    def review_annotation(self, text: str, initial_annotation: str) -> str:
        """Проверяет первичную аннотацию."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
            
        prompt = f"""Ты — эксперт-редактор. Проверь предложенный заголовок на соответствие тексту документа.
Если заголовок точный, верни его. Если он содержит ошибки или неточности, исправь его, сделав максимально достоверным.

Текст документа (отрывок):
{text[:2000]}

Предложенный заголовок:
{initial_annotation}

Итоговый, самый достоверный заголовок (только текст):"""
        
        final_title = self._call_model(self.config.review_model, prompt)
        return final_title if final_title else initial_annotation

    def get_available_models(self) -> list:
        """Получить список доступных моделей из Ollama - точно как в тестовом коде."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                verify=False,
                timeout=(10, 30)
            )
            response.raise_for_status()
            data = response.json()

            models = data.get('models', [])
            if not models:
                print("Список моделей пуст.")
                return []

            return [model.get("name", "") for model in models if model.get("name")]
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при подключении к API сервера моделей: {e}")
            return []
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            return []

    def check_connection(self) -> bool:
        """Проверить подключение к Ollama."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                verify=False,
                timeout=(10, 30)
            )
            response.raise_for_status()
            return True
        except:
            return False
