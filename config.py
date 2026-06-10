"""Конфигурация приложения."""
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Конфигурация Ollama. Модели НЕ имеют значений по умолчанию - выбор обязателен."""
    base_url: str = os.environ.get("OLLAMA_URL", "https://ollama.k2.iksi.edu")
    verify_ssl: bool = os.environ.get("OLLAMA_VERIFY_SSL", "false").lower() == "true"


@dataclass
class PipelineConfig:
    """Конфигурация pipeline анализа."""
    enable_translation: bool = os.environ.get("ENABLE_TRANSLATION", "true").lower() == "true"
    enable_annotation: bool = os.environ.get("ENABLE_ANNOTATION", "true").lower() == "true"
    enable_review: bool = os.environ.get("ENABLE_REVIEW", "true").lower() == "true"
    max_annotation_chars: int = int(os.environ.get("MAX_ANNOTATION_CHARS", "800"))
    max_review_iterations: int = 2  # Защита от бесконечного цикла


# Глобальная конфигурация
ollama_config = OllamaConfig()
pipeline_config = PipelineConfig()
