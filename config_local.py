"""Конфигурация для локальной Ollama (на вашем компьютере)."""
import os
from dataclasses import dataclass


@dataclass
class OllamaLocalConfig:
    """Конфигурация локальной Ollama."""
    base_url: str = os.environ.get("OLLAMA_LOCAL_URL", "http://localhost:11434")
    verify_ssl: bool = False  # Локально SSL не нужен


@dataclass
class LocalPipelineConfig:
    """Конфигурация pipeline для локальной Ollama."""
    enable_translation: bool = True
    enable_annotation: bool = True
    enable_review: bool = True
    max_annotation_chars: int = int(os.environ.get("MAX_ANNOTATION_CHARS", "1000"))
    max_review_iterations: int = 2  # Защита от бесконечного цикла


# Глобальная конфигурация
ollama_local_config = OllamaLocalConfig()
local_pipeline_config = LocalPipelineConfig()
