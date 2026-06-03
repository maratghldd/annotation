"""Core modules for document analysis."""
import os

# Динамический выбор клиента Ollama в зависимости от режима
if os.environ.get("OLLAMA_MODE") == "local":
    from .ollama_local import OllamaLocalClient as OllamaClient, OllamaLocalModelConfig as OllamaModelConfig
    from config_local import local_pipeline_config as PipelineConfig
else:
    from .ollama_models import OllamaClient, OllamaModelConfig
    from config import pipeline_config as PipelineConfig

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
