"""Core modules for document analysis."""
import os

# Динамический выбор клиента Ollama в зависимости от режима
if os.environ.get("OLLAMA_MODE") == "local":
    from .ollama_local import OllamaLocalClient as OllamaClient, OllamaLocalModelConfig as OllamaModelConfig
    from config_local import local_pipeline_config as _local_pipeline_config
    
    # Создаём класс-обёртку чтобы можно было создавать экземпляры
    class PipelineConfig:
        def __init__(self, enable_translation=None, enable_annotation=None, enable_review=None):
            self.enable_translation = enable_translation if enable_translation is not None else _local_pipeline_config.enable_translation
            self.enable_annotation = enable_annotation if enable_annotation is not None else _local_pipeline_config.enable_annotation
            self.enable_review = enable_review if enable_review is not None else _local_pipeline_config.enable_review
else:
    from .ollama_models import OllamaClient, OllamaModelConfig
    from config import pipeline_config as _pipeline_config
    from config import PipelineConfig

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
