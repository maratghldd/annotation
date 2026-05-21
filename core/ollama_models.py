"""Оllama клиент с поддержкой конфигурируемых моделей для разных задач."""
import os
import urllib3
import requests
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OllamaModelConfig:
    """Конфигурация моделей для разных задач."""
    
    def __init__(
        self,
        translate_model: str = "glm-4.7-flash:latest",
        annotate_model: str = "qwen3:235b",
        review_model: str = "deepseek-r1:32b"
    ):
        self.translate_model = translate_model
        self.annotate_model = annotate_model
        self.review_model = review_model


class OllamaClient:
    """Клиент для работы с Ollama API с поддержкой разных моделей."""
    
    def __init__(self, base_url: Optional[str] = None, config: Optional[OllamaModelConfig] = None):
        raw_url = base_url or os.environ.get("OLLAMA_URL", "https://ollama.k2.iksi.edu")
        self.base_url = raw_url.rstrip("/")
        self.generate_url = f"{self.base_url}/api/generate"
        self.config = config or OllamaModelConfig()
        self.verify = False
    
    def _call_model(self, model: str, prompt: str, timeout: tuple = (10, 300)) -> str:
        """Вызов конкретной модели с обработкой ошибок."""
        payload = {
            "model": model,
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
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            return ""
        except Exception as e:
            print(f"Ошибка Ollama ({model}): {e}")
            return ""
    
    def translate_text(self, text: str) -> str:
        """Переводит текст на русский, если он на украинском."""
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
        prompt = f"""Проанализируй текст документа и придумай развёрнутое, понятное название (8-15 слов) на РУССКОМ языке.
Название должно отражать суть документа.

Имя файла: {filename}
Текст:
{text[:3000]}

Название:"""
        return self._call_model(self.config.annotate_model, prompt)

    def review_annotation(self, text: str, initial_annotation: str) -> str:
        """Проверяет первичную аннотацию и выбирает самый достоверный вариант."""
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
        """Получить список доступных моделей из Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5, verify=self.verify)
            if response.status_code == 200:
                data = response.json()
                return [model.get("name", "") for model in data.get("models", [])]
        except Exception:
            pass
        return []

    def check_connection(self) -> bool:
        """Проверить подключение к Ollama."""
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=5, verify=self.verify)
            return True
        except:
            return False
