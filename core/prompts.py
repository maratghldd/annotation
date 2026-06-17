"""Модуль загрузки и управления промптами."""
import os
from pathlib import Path
from jinja2 import Template
from typing import Dict, Any


class PromptLoader:
    """Загружает промпты из файлов шаблонов."""
    
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            # По умолчанию ищем папку prompts рядом с этим файлом
            prompts_dir = Path(__file__).parent.parent / "prompts"
        
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, Template] = {}
    
    def load(self, prompt_name: str, **kwargs) -> str:
        """
        Загружает промпт из файла и подставляет переменные.
        
        Args:
            prompt_name: Имя файла без расширения (например, 'translate')
            **kwargs: Переменные для подстановки в шаблон
        
        Returns:
            Готовый промпт с подставленными значениями
        """
        # Проверяем кэш
        if prompt_name in self._cache:
            template = self._cache[prompt_name]
        else:
            # Загружаем из файла
            file_path = self.prompts_dir / f"{prompt_name}.txt"
            
            if not file_path.exists():
                raise FileNotFoundError(f"Промпт не найден: {file_path}")
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            template = Template(content)
            self._cache[prompt_name] = template
        
        # Рендерим с переменными
        return template.render(**kwargs)
    
    def get_current_template(self, prompt_name: str) -> str:
        """Получает текущий текст промта (без рендеринга)."""
        file_path = self.prompts_dir / f"{prompt_name}.txt"
        if not file_path.exists():
            return ""
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def get_default_template(self, prompt_name: str) -> str:
        """Получает стандартный промт (заранее определённый)."""
        defaults = {
            "translate": """Переведи следующий текст на русский язык.
Сохраняй деловой стиль и терминологию.

Текст для перевода:
{{ text }}

Перевод:""",
            
            "annotate": """Сделай краткий пересказ документа "{{ filename }}".

Текст документа:
{{ text }}

Требования:
- Объем: не более {{ max_chars }} символов
- Язык: русский
- Стиль: деловой
- Выдели основную суть

Пересказ:""",
            
            "review": """Проверь качество пересказа документа.

Оригинальный текст:
{{ original_text }}

Пересказ:
{{ annotation }}

Оцени пересказ по критериям:
1. Полнота (все ли ключевые моменты отражены)
2. Точность (нет ли искажений)
3. Лаконичность (нет ли лишних деталей)

Ответь в формате:
===СТАТУС===
PASS или FAIL
===ОТЧЁТ===
[текст замечаний или "Замечаний нет"]
===ПЕРЕСКАЗ===
[улучшенная версия пересказа, если есть замечания]
===КОНЕЦ===""",
            
            "fix": """Устрани замечания в пересказе документа.

Оригинальный текст:
{{ original_text }}

Текущий пересказ:
{{ annotation }}

Замечания:
{{ issues }}

Исправленный пересказ (объем до {{ max_chars }} символов):""",
        }
        
        return defaults.get(prompt_name, "")
    
    def save_template(self, prompt_name: str, content: str):
        """Сохраняет промт в файл."""
        file_path = self.prompts_dir / f"{prompt_name}.txt"
        
        # Создаём директорию если нет
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Очищаем кэш для этого промта
        if prompt_name in self._cache:
            del self._cache[prompt_name]
    
    def reload(self):
        """Перезагружает все промпты из файлов (полезно при разработке)."""
        self._cache.clear()


# Глобальный экземпляр
prompt_loader = PromptLoader()
