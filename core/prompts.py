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
    
    def reload(self):
        """Перезагружает все промпты из файлов (полезно при разработке)."""
        self._cache.clear()


# Глобальный экземпляр
prompt_loader = PromptLoader()
