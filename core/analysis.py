"""Основная логика анализа документов с использованием многоэтапного pipeline."""
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

from .ollama_models import OllamaClient, OllamaModelConfig
from .processing import DocumentProcessor


@dataclass
class AnalysisResult:
    """Результат анализа одного файла."""
    file_name: str
    title: str
    status: str
    original_name: str = ""
    file_path: str = ""


@dataclass
class PipelineConfig:
    """Конфигурация pipeline анализа."""
    enable_translation: bool = True
    enable_annotation: bool = True
    enable_review: bool = True
    annotation_length: str = "medium"  # short, medium, long


class DocumentAnalyzer:
    """Анализатор документов с многоэтапным pipeline."""
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        config: Optional[PipelineConfig] = None
    ):
        self.ollama = ollama_client
        self.processor = DocumentProcessor(log_callback)
        self._log = log_callback or print
        self._cancel_check = cancel_check or (lambda: False)
        self.config = config or PipelineConfig()

    def analyze_single_file(self, file_path: Path, output_dir: Path) -> AnalysisResult:
        """Анализ одного файла через весь pipeline."""
        try:
            # Конвертация
            processed = self.processor.process_file(file_path, output_dir)
            if not processed:
                return AnalysisResult(
                    file_name=file_path.name,
                    title="Ошибка обработки",
                    status="error",
                    original_name=file_path.name
                )
            
            # Чтение текста
            text = self.processor.read_text(processed)
            if not text:
                return AnalysisResult(
                    file_name=processed.name,
                    title="Нет текста",
                    status="error",
                    original_name=file_path.name,
                    file_path=str(processed)
                )
            
            working_text = text
            
            # Этап 1: Перевод (если включен)
            if self.config.enable_translation:
                self._log("   - Этап 1: Проверка языка/Перевод")
                working_text = self.ollama.translate_text(text)
            
            # Этап 2: Аннотирование
            if self.config.enable_annotation:
                self._log("   - Этап 2: Первичная аннотация")
                initial_title = self.ollama.generate_annotation(working_text, file_path.name)
            else:
                initial_title = ""
            
            # Этап 3: Проверка
            if self.config.enable_review and initial_title:
                self._log("   - Этап 3: Проверка достоверности")
                final_title = self.ollama.review_annotation(working_text, initial_title)
            else:
                final_title = initial_title
            
            return AnalysisResult(
                file_name=processed.name,
                title=final_title if final_title else "Нет названия",
                status="success",
                original_name=file_path.name,
                file_path=str(processed)
            )
            
        except Exception as e:
            self._log(f"Ошибка обработки {file_path.name}: {e}")
            return AnalysisResult(
                file_name=file_path.name,
                title=f"Ошибка: {str(e)}",
                status="error",
                original_name=file_path.name
            )

    def analyze_folder(self, source: str, output: Path) -> tuple[List[AnalysisResult], List[Path]]:
        """Анализ всех файлов в папке."""
        self._log("Запуск анализа папки...")
        files = self.processor.find_all_files(source)
        results = []
        created_files = []

        for i, file_path in enumerate(files, 1):
            if self._cancel_check():
                self._log("Остановлено пользователем")
                break
                
            self._log(f"[{i}/{len(files)}] Обработка: {file_path.name}")
            
            result = self.analyze_single_file(file_path, output)
            results.append(result)
            
            if result.status == "success" and result.file_path:
                created_files.append(Path(result.file_path))
            
            if result.status == "success":
                self._log(f"   Готово: {result.title}")
            else:
                self._log(f"   Ошибка: {result.title}")

        return results, created_files
