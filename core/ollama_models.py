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
        """Создает краткий пересказ содержимого документа (несколько абзацев)."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
            
        prompt = f"""Проанализируй текст документа и составь краткий пересказ его содержимого на РУССКОМ языке.
Пересказ должен быть структурированным, состоять из 2-4 абзацев и отражать основную суть документа.
Каждый абзац посвящён отдельному аспекту: о чём документ, какие ключевые моменты, выводы.
Не используй маркированные списки, только связный текст с абзацами.

Имя файла: {filename}
Текст:
{text[:5000]}

Краткий пересказ:"""
        return self._call_model(self.config.annotate_model, prompt)

    def review_annotation(self, text: str, initial_annotation: str) -> tuple:
        """Проверяет и улучшает краткий пересказ. Возвращает (аннотация, статус_проверки, отчет)."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
            
        prompt = f"""Ты — эксперт-редактор. Проверь предложенный пересказ документа на соответствие тексту.

Твоя задача:
1. Проверь, что в пересказе нет вымышленных фактов, не указанных в тексте
2. Проверь, что пересказ точно отражает содержание
3. Если есть неточности — исправь их
4. В конце укажи результат проверки

Текст документа (отрывок):
{text[:4000]}

Предложенный пересказ:
{initial_annotation}

Выполни проверку и верни ответ в формате:
===РЕЗУЛЬТАТ ПРОВЕРКИ===
[Здесь напиши краткий отчет о проверке: что проверено, есть ли проблемы]
===ФИНАЛЬНЫЙ ПЕРЕСКАЗ===
[Здесь напиши итоговый пересказ, исправленный если нужно]
===КОНЕЦ==="""

        response = self._call_model(self.config.review_model, prompt)
        
        # Парсим ответ
        annotation = initial_annotation
        status = "passed"
        report = "Проверка пройдена без замечаний"
        
        if "===РЕЗУЛЬТАТ ПРОВЕРКИ===" in response and "===ФИНАЛЬНЫЙ ПЕРЕСКАЗ===" in response:
            parts = response.split("===ФИНАЛЬНЫЙ ПЕРЕСКАЗ===")
            if len(parts) >= 2:
                report_part = parts[0].replace("===РЕЗУЛЬТАТ ПРОВЕРКИ===", "").strip()
                annotation_part = parts[1].split("===КОНЕЦ===")[0].strip() if "===КОНЕЦ===" in parts[1] else parts[1].strip()
                
                annotation = annotation_part if annotation_part else annotation
                report = report_part
                
                # Определяем статус по ключевым словам
                if "проблем" in report.lower() or "ошибка" in report.lower() or "неточно" in report.lower():
                    status = "warnings"
                elif "вымышлен" in report.lower() or "не соответствует" in report.lower():
                    status = "failed"
                else:
                    status = "passed"
        else:
            # Если формат не распознан, используем ответ как аннотацию
            annotation = response if response else initial_annotation
            report = "Проверка завершена"
            status = "passed"
        
        return annotation, status, report

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
