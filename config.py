"""Конфигурация приложения."""
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Конфигурация Ollama."""
    base_url: str = os.environ.get("OLLAMA_URL", "https://ollama.k2.iksi.edu")
    translate_model: str = os.environ.get("OLLAMA_TRANSLATE_MODEL", "glm-4.7-flash:latest")
    annotate_model: str = os.environ.get("OLLAMA_ANNOTATE_MODEL", "qwen3:235b")
    review_model: str = os.environ.get("OLLAMA_REVIEW_MODEL", "deepseek-r1:32b")
    verify_ssl: bool = os.environ.get("OLLAMA_VERIFY_SSL", "false").lower() == "true"


@dataclass
class PipelineConfig:
    """Конфигурация pipeline анализа."""
    enable_translation: bool = os.environ.get("ENABLE_TRANSLATION", "true").lower() == "true"
    enable_annotation: bool = os.environ.get("ENABLE_ANNOTATION", "true").lower() == "true"
    enable_review: bool = os.environ.get("ENABLE_REVIEW", "true").lower() == "true"


# Глобальная конфигурация
ollama_config = OllamaConfig()
pipeline_config = PipelineConfig()
