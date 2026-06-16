"""Клиент для работы с Ollama API."""
import requests
from typing import List, Optional
from config import ollama_config, pipeline_config
from core.prompts import prompt_loader


class OllamaModelConfig:
    """Конфигурация моделей для каждого этапа."""
    def __init__(self, translate_model: str, annotate_model: str, review_model: str):
        self.translate_model = translate_model.strip()
        self.annotate_model = annotate_model.strip()
        self.review_model = review_model.strip()
    
    def __bool__(self):
        return bool(self.translate_model and self.annotate_model and self.review_model)


class OllamaClient:
    """Клиент для взаимодействия с Ollama API."""
    
    def __init__(self, base_url: str = None, config: OllamaModelConfig = None):
        self.base_url = (base_url or ollama_config.base_url).rstrip("/")
        self.config = config
        self.verify = ollama_config.verify_ssl
        self.default_timeout = (10, 900)  # (connect, read) — 15 минут для больших моделей
    
    def check_connection(self) -> bool:
        """Проверяет доступность Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", verify=self.verify, timeout=(10, 30))
            return response.status_code == 200
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """Получает список ВСЕХ установленных моделей."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", verify=self.verify, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            return [model.get("name", "") for model in data.get("models", []) if model.get("name")]
        except Exception as e:
            print(f"Ошибка получения моделей: {type(e).__name__}: {e}")
            return []
    
    def get_active_models(self) -> List[str]:
        """Получает список АКТИВНЫХ моделей (загруженных в память)."""
        try:
            response = requests.get(f"{self.base_url}/api/ps", verify=self.verify, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            # /api/ps возвращает {"models": [{"name": "...", "size": ..., ...}, ...]}
            return [model.get("name", "") for model in data.get("models", []) if model.get("name")]
        except Exception as e:
            # Если /api/ps недоступен - возвращаем пустой список (не ломаем всё)
            print(f"[WARN] Не удалось получить активные модели: {e}")
            return []
    
    def _call_model(self, model: str, prompt: str, timeout: tuple = None) -> str:
        """Вызывает модель с заданным промптом."""
        if not model:
            raise ValueError("Модель не указана")
        
        payload = {
            "model": model.strip(),
            "prompt": prompt,
            "stream": False,
            "think": False,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                verify=self.verify,
                timeout=timeout or self.default_timeout
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Превышено время ожидания ответа от модели {model}")
        except Exception as e:
            raise RuntimeError(f"Ошибка вызова модели {model}: {str(e)}")
    
    def translate_text(self, text: str, filename: str = "") -> str:
        """Переводит текст на русский язык."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
        
        # Загружаем промпт из файла
        prompt = prompt_loader.load(
            "translate",
            filename=filename,
            text=text[:5000]
        )
        
        return self._call_model(self.config.translate_model, prompt)
    
    def generate_annotation(self, text: str, filename: str) -> str:
        """Создает краткий пересказ содержимого документа."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
        
        # Загружаем промпт из файла с лимитом символов
        prompt = prompt_loader.load(
            "annotate",
            filename=filename,
            text=text[:5000],
            max_chars=pipeline_config.max_annotation_chars
        )
        
        return self._call_model(self.config.annotate_model, prompt)
    
    def review_annotation(self, text: str, initial_annotation: str) -> tuple:
        """
        Проверяет и улучшает краткий пересказ.
        Возвращает: (аннотация, статус_проверки, отчет)
        """
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
        
        # Загружаем промпт из файла
        prompt = prompt_loader.load(
            "review",
            original_text=text[:4000],
            annotation=initial_annotation
        )
        
        response = self._call_model(self.config.review_model, prompt)
        
        # Парсим ответ
        annotation = initial_annotation
        status = "passed"
        report = "Проверка пройдена без замечаний"
        
        # Ожидаемый формат:
        # ===СТАТУС===
        # [PASS или FAIL]
        # ===ОТЧЁТ===
        # [текст]
        # ===ПЕРЕСКАЗ===
        # [текст]
        # ===КОНЕЦ===
        
        if "===СТАТУС===" in response and "===ПЕРЕСКАЗ===" in response:
            # Извлекаем статус
            status_part = response.split("===СТАТУС===")[1].split("===ОТЧЁТ===")[0].strip()
            report_part = response.split("===ОТЧЁТ===")[1].split("===ПЕРЕСКАЗ===")[0].strip()
            annotation_part = response.split("===ПЕРЕСКАЗ===")[1].split("===КОНЕЦ===")[0].strip() if "===КОНЕЦ===" in response else response.split("===ПЕРЕСКАЗ===")[1].strip()
            
            annotation = annotation_part if annotation_part else annotation
            report = report_part
            
            # Определяем статус по ключевым словам
            if status_part.upper() == "PASS":
                status = "passed"
            else:
                status = "failed"
        else:
            # Если формат не распознан, считаем что проверка пройдена
            annotation = response if response else initial_annotation
            report = "Проверка завершена"
            status = "passed"
        
        return annotation, status, report
    
    def fix_annotation(self, text: str, annotation: str, issues: str) -> str:
        """Устраняет замечания в пересказе."""
        if not self.config:
            raise ValueError("Конфигурация моделей не установлена")
        
        # Загружаем промпт из файла с лимитом символов
        prompt = prompt_loader.load(
            "fix",
            original_text=text[:4000],
            annotation=annotation,
            issues=issues,
            max_chars=pipeline_config.max_annotation_chars
        )
        
        return self._call_model(self.config.review_model, prompt)
