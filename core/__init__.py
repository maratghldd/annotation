"""Core modules for document analysis."""
import os

# Читаем режим из переменной окружения
_ollama_mode = os.environ.get("OLLAMA_MODE", "remote")

# Динамический выбор клиента Ollama в зависимости от режима
if _ollama_mode == "local":
    from .ollama_local import OllamaLocalClient as OllamaClient, OllamaLocalModelConfig as OllamaModelConfig
    from config_local import local_pipeline_config as _local_pipeline_config
    
    # Создаём класс-обёртку чтобы можно было создавать экземпляры
    class PipelineConfig:
        def __init__(self, enable_translation=None, enable_annotation=None, enable_review=None):
            self.enable_translation = enable_translation if enable_translation is not None else _local_pipeline_config.enable_translation
            self.enable_annotation = enable_annotation if enable_annotation is not None else _local_pipeline_config.enable_annotation
            self.enable_review = enable_review if enable_review is not None else _local_pipeline_config.enable_review
            self.max_review_iterations = _local_pipeline_config.max_review_iterations
            self.max_annotation_chars = _local_pipeline_config.max_annotation_chars
else:
    from .ollama_models import OllamaClient, OllamaModelConfig
    from config import pipeline_config as _pipeline_config
    
    # Создаём класс-обёртку чтобы можно было создавать экземпляры
    class PipelineConfig:
        def __init__(self, enable_translation=None, enable_annotation=None, enable_review=None):
            self.enable_translation = enable_translation if enable_translation is not None else _pipeline_config.enable_translation
            self.enable_annotation = enable_annotation if enable_annotation is not None else _pipeline_config.enable_annotation
            self.enable_review = enable_review if enable_review is not None else _pipeline_config.enable_review
            self.max_review_iterations = _pipeline_config.max_review_iterations
            self.max_annotation_chars = _pipeline_config.max_annotation_chars

from .processing import DocumentProcessor
from .analysis import DocumentAnalyzer, AnalysisResult

__all__ = [
    "OllamaClient",
    "OllamaModelConfig", 
    "DocumentProcessor",
    "DocumentAnalyzer",
    "AnalysisResult",
    "PipelineConfig",
]
