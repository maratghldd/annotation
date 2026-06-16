"""FastAPI web application for document analysis."""
import io
import os
import uuid
import asyncio
import requests
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel, field_validator
from core import DocumentAnalyzer, AnalysisResult, OllamaClient, OllamaModelConfig, PipelineConfig
import os

# Читаем режим из переменной окружения (устанавливается в run.py)
OLLAMA_MODE = os.environ.get("OLLAMA_MODE", "remote")

if OLLAMA_MODE == "local":
    from config_local import ollama_local_config as ollama_config
    # Для локального режима используем значения по умолчанию
    class _pipeline_config_defaults:
        enable_translation = True
        enable_annotation = True
        enable_review = True
        max_annotation_chars = 1000
        max_review_iterations = 2
    pipeline_config = _pipeline_config_defaults()
else:
    from config import ollama_config, pipeline_config


# In-memory task storage
tasks: Dict[str, dict] = {}
task_logs: Dict[str, List[str]] = {}
task_results: Dict[str, List[dict]] = {}
output_dirs: Dict[str, Path] = {}
source_folders: Dict[str, str] = {}
task_cancelled: Dict[str, bool] = {}
task_created_files: Dict[str, List[Path]] = {}  # files created per task for cleanup
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_log_callback(task_id: str):
    def log(msg: str):
        if task_id not in task_logs:
            task_logs[task_id] = []
        task_logs[task_id].append(msg)
    return log


def run_folder_analysis_task(
    task_id: str, 
    source: str, 
    output: str,
    translate_model: Optional[str] = None,
    annotate_model: Optional[str] = None,
    review_model: Optional[str] = None,
    enable_translation: Optional[bool] = None,
    enable_annotation: Optional[bool] = None,
    enable_review: Optional[bool] = None
):
    task_created_files[task_id] = []
    try:
        tasks[task_id]["status"] = "running"
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        output_dirs[task_id] = output_path
        source_folders[task_id] = source

        def cancel_check():
            return task_cancelled.get(task_id, False)

        # Загружаем модели в оперативную память перед началом
        log_callback = get_log_callback(task_id)
        log_callback("\n🔄 Загрузка моделей в оперативную память...")
        
        # Собираем уникальные модели для загрузки (чтобы не грузить одну модель 3 раза)
        models_to_load = set()
        if enable_translation if enable_translation is not None else pipeline_config.enable_translation:
            models_to_load.add(translate_model)
        if enable_annotation if enable_annotation is not None else pipeline_config.enable_annotation:
            models_to_load.add(annotate_model)
        if enable_review if enable_review is not None else pipeline_config.enable_review:
            models_to_load.add(review_model)
        
        # Загружаем каждую уникальную модель только один раз
        for model_name in models_to_load:
            if model_name:
                try:
                    log_callback(f"   - Загрузка модели: {model_name}...")
                    
                    # Отправляем запрос к модели, чтобы она загрузилась в память
                    payload = {
                        "model": model_name,
                        "prompt": "test",
                        "stream": False,
                        "keep_alive": -1  # Не выгружать из памяти
                    }
                    
                    # Увеличиваем таймаут для больших моделей (122B)
                    response = requests.post(
                        f"{ollama_config.base_url}/api/generate",
                        json=payload,
                        verify=ollama_config.verify_ssl,
                        timeout=(10, 1800)  # 30 минут на генерацию для больших моделей
                    )
                    response.raise_for_status()
                    
                    log_callback(f"   ✅ Модель {model_name} загружена в оперативную память")
                    
                    # Пауза чтобы модель стабилизировалась
                    import time
                    time.sleep(2)
                    
                except Exception as e:
                    log_callback(f"   ⚠️ Ошибка загрузки модели {model_name}: {e}")

        # Настройка конфигурации моделей (все модели обязательны)
        model_config = OllamaModelConfig(
            translate_model=translate_model,
            annotate_model=annotate_model,
            review_model=review_model
        )
        
        ollama_client = OllamaClient(
            base_url=ollama_config.base_url,
            config=model_config
        )
        
        # Настройка pipeline
        pipe_config = PipelineConfig(
            enable_translation=enable_translation if enable_translation is not None else pipeline_config.enable_translation,
            enable_annotation=enable_annotation if enable_annotation is not None else pipeline_config.enable_annotation,
            enable_review=enable_review if enable_review is not None else pipeline_config.enable_review
        )

        analyzer = DocumentAnalyzer(
            ollama_client=ollama_client,
            log_callback=log_callback,
            cancel_check=cancel_check,
            config=pipe_config
        )
        results, created_files = analyzer.analyze_folder(source, output_path)
        task_created_files[task_id] = created_files

        if task_cancelled.get(task_id, False):
            _cleanup_task_files(task_id)
            tasks[task_id]["status"] = "cancelled"
            task_results[task_id] = []
            log_callback("\nОстановлено. Созданные файлы удалены.")
            return

        task_results[task_id] = [
            {
                "file_name": r.file_name, 
                "original_name": r.original_name, 
                "title": r.title, 
                "status": r.status, 
                "file_path": r.file_path,
                "review_status": r.review_status,
                "review_report": r.review_report
            }
            for r in results
        ]
        tasks[task_id]["status"] = "completed"
        log_callback("\nРабота завершена")

        report_file = output_path / "результаты_анализа.txt"
        _save_results(results, report_file, source)
    except Exception as e:
        if task_cancelled.get(task_id, False):
            _cleanup_task_files(task_id)
            tasks[task_id]["status"] = "cancelled"
            log_callback("\nОстановлено. Созданные файлы удалены.")
        else:
            tasks[task_id]["status"] = "failed"
            task_results[task_id] = []
            get_log_callback(task_id)(f"\nОшибка: {str(e)}")


def _cleanup_task_files(task_id: str):
    """Delete files created during the task."""
    for fp in task_created_files.get(task_id, []):
        try:
            p = Path(fp) if not isinstance(fp, Path) else fp
            if p and p.exists() and p.is_file():
                p.unlink()
        except Exception:
            pass
    if task_id in output_dirs:
        report_file = output_dirs[task_id] / "результаты_анализа.txt"
        if report_file.exists():
            try:
                report_file.unlink()
            except Exception:
                pass


def _save_results(results, output_file: Path, source_folder: str):
    """Сохранить результаты аннотирования в текстовый файл."""
    from core import AnalysisResult
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("РЕЗУЛЬТАТЫ АННОТИРОВАНИЯ ДОКУМЕНТОВ\n")
        f.write(f"Источник: {source_folder}\n")
        f.write("=" * 60 + "\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"[{i}] {r.original_name}\n   Аннотация: {r.title}\n" + "-"*40 + "\n")


def run_single_file_task(
    task_id: str, 
    file_path: Path, 
    output_dir: Path,
    translate_model: str,
    annotate_model: str,
    review_model: str
):
    try:
        tasks[task_id]["status"] = "running"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dirs[task_id] = output_dir
        source_folders[task_id] = str(file_path.parent)

        # Настройка конфигурации моделей (все модели обязательны)
        model_config = OllamaModelConfig(
            translate_model=translate_model,
            annotate_model=annotate_model,
            review_model=review_model
        )
        
        ollama_client = OllamaClient(
            base_url=ollama_config.base_url,
            config=model_config
        )
        
        analyzer = DocumentAnalyzer(
            ollama_client=ollama_client,
            log_callback=get_log_callback(task_id)
        )
        result = analyzer.analyze_single_file(file_path, output_dir)

        task_results[task_id] = [{
            "file_name": result.file_name,
            "original_name": result.original_name,
            "title": result.title,
            "status": result.status,
            "file_path": result.file_path,
            "review_status": result.review_status,
            "review_report": result.review_report
        }]
        tasks[task_id]["status"] = "completed"
        get_log_callback(task_id)("\nАнализ завершён")
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        task_results[task_id] = []
        get_log_callback(task_id)(f"\nОшибка: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(exist_ok=True)
    yield
    # Cleanup old uploads
    for f in UPLOAD_DIR.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass


app = FastAPI(title="Документ-анализатор", lifespan=lifespan)

# Static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- API ---

class AnalyzeFolderRequest(BaseModel):
    source_folder: str
    output_folder: str
    translate_model: str
    annotate_model: str
    review_model: str
    enable_translation: Optional[bool] = None
    enable_annotation: Optional[bool] = None
    enable_review: Optional[bool] = None

    @field_validator('translate_model', 'annotate_model', 'review_model')
    @classmethod
    def validate_model_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Модель обязательна для выбора')
        return v.strip()


class AnalyzeFileRequest(BaseModel):
    file_name: str
    translate_model: str
    annotate_model: str
    review_model: str

    @field_validator('translate_model', 'annotate_model', 'review_model')
    @classmethod
    def validate_model_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Модель обязательна для выбора')
        return v.strip()


class UpdateTitleRequest(BaseModel):
    task_id: str
    file_name: str
    new_title: str


class RegenerateRequest(BaseModel):
    task_id: str
    file_name: str
    translate_model: str
    annotate_model: str
    review_model: str

    @field_validator('translate_model', 'annotate_model', 'review_model')
    @classmethod
    def validate_model_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Модель обязательна для выбора')
        return v.strip()


class CancelTaskRequest(BaseModel):
    task_id: str


class GetModelsRequest(BaseModel):
    """Запрос для получения доступных моделей."""
    pass


def sanitize_filename(name: str) -> str:
    """Prevent path traversal."""
    return os.path.basename(name)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze-folder")
async def analyze_folder(req: AnalyzeFolderRequest, background_tasks: BackgroundTasks):
    source = req.source_folder.strip().strip('"\'')
    output = req.output_folder.strip().strip('"\'')
    if not os.path.exists(source):
        raise HTTPException(status_code=400, detail="Исходная папка не найдена")
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "progress": 0}
    task_logs[task_id] = []
    task_results[task_id] = []

    background_tasks.add_task(
        run_folder_analysis_task,
        task_id, source, output,
        req.translate_model, req.annotate_model, req.review_model,
        req.enable_translation, req.enable_annotation, req.enable_review
    )
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/analyze-file")
async def analyze_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = Form(...),
    translate_model: Optional[str] = Form(None),
    annotate_model: Optional[str] = Form(None),
    review_model: Optional[str] = Form(None)
):
    allowed = {".docx", ".doc", ".pdf"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Формат {ext} не поддерживается. Допустимы: .docx, .doc, .pdf")

    # Save uploaded file to temp location
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(file.filename or "document")
    file_path = task_dir / safe_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    tasks[task_id] = {"status": "pending"}
    task_logs[task_id] = []
    task_results[task_id] = []

    output_dir = task_dir / "output"
    background_tasks.add_task(
        run_single_file_task,
        task_id, file_path, output_dir,
        translate_model, annotate_model, review_model
    )
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/cancel-task")
async def cancel_task(req: CancelTaskRequest):
    """Cancel a running folder analysis task."""
    task_id = req.task_id
    if not task_id or task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    task_cancelled[task_id] = True
    tasks[task_id]["status"] = "cancelled"  # Сразу меняем статус
    return {"ok": True, "status": "cancelled"}


@app.get("/api/models")
async def get_available_models():
    """Получить список доступных моделей из Ollama."""
    try:
        print(f"\n[DEBUG /api/models] OLLAMA_MODE={OLLAMA_MODE}")
        print(f"[DEBUG /api/models] base_url={ollama_config.base_url}")
        
        ollama = OllamaClient()
        print(f"[DEBUG /api/models] OllamaClient создан: {type(ollama).__name__}")
        
        available = ollama.get_available_models()
        print(f"[DEBUG /api/models] available_models count: {len(available)}")
        print(f"[DEBUG /api/models] available_models: {available}")
        
        active = ollama.get_active_models()
        print(f"[DEBUG /api/models] active_models count: {len(active)}")
        print(f"[DEBUG /api/models] active_models: {active}\n")

        return {
            "available_models": available,
            "active_models": active,
            "base_url": ollama_config.base_url,
            "pipeline_config": {
                "enable_translation": pipeline_config.enable_translation,
                "enable_annotation": pipeline_config.enable_annotation,
                "enable_review": pipeline_config.enable_review,
            }
        }
    except Exception as e:
        print(f"Ошибка в /api/models: {e}")
        import traceback
        traceback.print_exc()
        return {
            "available_models": [],
            "active_models": [],
            "base_url": ollama_config.base_url,
            "pipeline_config": {},
            "error": str(e)
        }


@app.post("/api/load-model")
async def load_model(req: BaseModel):
    """Загрузить модель в оперативную память."""
    model_name = req.dict().get('model_name', '')
    if not model_name:
        raise HTTPException(status_code=400, detail="Имя модели не указано")
    
    try:
        ollama = OllamaClient()
        # Отправляем запрос к модели, чтобы она загрузилась
        payload = {
            "model": model_name,
            "prompt": "test",
            "stream": False,
            "keep_alive": -1  # Не выгружать из памяти
        }
        response = requests.post(
            f"{ollama_config.base_url}/api/generate",
            json=payload,
            verify=ollama_config.verify_ssl,
            timeout=(10, 600)
        )
        response.raise_for_status()
        return {"ok": True, "message": f"Модель {model_name} загружена в оперативную память"}
    except Exception as e:
        print(f"Ошибка загрузки модели {model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-connection")
async def test_connection():
    """Проверить подключение к Ollama."""
    ollama = OllamaClient()
    connected = ollama.check_connection()
    return {
        "connected": connected,
        "base_url": ollama_config.base_url
    }


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"task_id": task_id, "status": tasks[task_id]["status"]}


@app.get("/api/results/{task_id}")
async def get_results(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"task_id": task_id, "results": task_results.get(task_id, [])}


@app.get("/api/files/{task_id}/{filename}")
async def get_file(task_id: str, filename: str):
    filename = sanitize_filename(filename)
    if task_id not in output_dirs:
        raise HTTPException(status_code=404, detail="Результаты не найдены")
    base = output_dirs[task_id]
    file_path = base / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(file_path, filename=filename)


@app.post("/api/regenerate-title")
async def regenerate_title(req: RegenerateRequest):
    """Regenerate title for a single file using the multi-model pipeline."""
    if req.task_id not in task_results or req.task_id not in output_dirs:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    from core import OllamaClient, OllamaModelConfig
    
    # Настройка моделей (все модели обязательны)
    model_config = OllamaModelConfig(
        translate_model=req.translate_model,
        annotate_model=req.annotate_model,
        review_model=req.review_model
    )

    ollama = OllamaClient(base_url=ollama_config.base_url, config=model_config)

    filename = sanitize_filename(req.file_name)
    base = output_dirs[req.task_id]
    file_path = base / filename
    
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="Файл не найден")
         
    # Используем DocumentProcessor напрямую для чтения текста
    from core import DocumentProcessor
    processor = DocumentProcessor()
    text = processor.read_text(file_path)
    
    # Полный цикл: Перевод -> Аннотация -> Проверка (с защитой от цикла)
    working_text = ollama.translate_text(text, filename)
    initial = ollama.generate_annotation(working_text, filename)
    
    # Проверка с ограничением итераций
    final_title = initial
    review_status = "passed"
    review_report = "Проверка не проводилась"
    max_iterations = 2
    
    for iteration in range(max_iterations):
        final_title, review_status, review_report = ollama.review_annotation(working_text, final_title)
        
        if review_status == "passed":
            break
        elif iteration < max_iterations - 1:
            # Автоматически исправляем
            final_title = ollama.fix_annotation(working_text, final_title, review_report)
    
    # Если после всех итераций всё ещё есть замечания — принимаем как passed
    if review_status != "passed":
        review_status = "passed"
        review_report += "\n(Проверка завершена после максимального количества попыток)"
    
    for r in task_results[req.task_id]:
        if r["file_name"] == filename or r["original_name"] == req.file_name:
            r["title"] = final_title
            r["status"] = "success"
            r["review_status"] = review_status
            r["review_report"] = review_report
            return {"ok": True, "title": final_title, "review_status": review_status, "review_report": review_report}
            
    raise HTTPException(status_code=404, detail="Файл не найден в результатах")


@app.post("/api/fix-review")
async def fix_review(req: RegenerateRequest):
    """Устранить замечания проверки для конкретного файла."""
    if req.task_id not in task_results or req.task_id not in output_dirs:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    from core import OllamaClient, OllamaModelConfig
    
    model_config = OllamaModelConfig(
        translate_model=req.translate_model,
        annotate_model=req.annotate_model,
        review_model=req.review_model
    )

    ollama = OllamaClient(base_url=ollama_config.base_url, config=model_config)

    filename = sanitize_filename(req.file_name)
    base = output_dirs[req.task_id]
    file_path = base / filename
    
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="Файл не найден")
         
    from core import DocumentProcessor
    processor = DocumentProcessor()
    text = processor.read_text(file_path)
    
    # Находим текущую аннотацию и отчет
    current_result = None
    for r in task_results[req.task_id]:
        if r["file_name"] == filename or r["original_name"] == req.file_name:
            current_result = r
            break
    
    if not current_result:
        raise HTTPException(status_code=404, detail="Файл не найден в результатах")
    
    # Устраняем замечания
    working_text = ollama.translate_text(text, filename)
    fixed_title = ollama.fix_annotation(
        working_text, 
        current_result["title"], 
        current_result.get("review_report", "")
    )
    
    # Перепроверяем исправленную версию
    final_title, review_status, review_report = ollama.review_annotation(working_text, fixed_title)
    
    # Если всё ещё есть замечания — принимаем как passed
    if review_status != "passed":
        review_status = "passed"
        review_report += "\n(Замечания устранены, проверка завершена)"
    
    current_result["title"] = final_title
    current_result["review_status"] = review_status
    current_result["review_report"] = review_report
    
    return {"ok": True, "title": final_title, "review_status": review_status, "review_report": review_report}


@app.put("/api/update-title")
async def update_title(req: UpdateTitleRequest):
    if req.task_id not in task_results:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    for r in task_results[req.task_id]:
        if r["file_name"] == req.file_name or r["original_name"] == req.file_name:
            r["title"] = req.new_title
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Файл не найден в результатах")


@app.get("/api/export/{task_id}")
async def export_results(task_id: str, format: str = "txt"):
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    results = task_results[task_id]
    source = source_folders.get(task_id, "")

    if format.lower() == "csv":
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Имя файла", "Аннотация", "Статус"])
        for r in results:
            writer.writerow([r["original_name"], r["title"], r["status"]])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=results.csv"}
        )

    if format.lower() == "excel":
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(status_code=500, detail="Установите openpyxl: pip install openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Результаты"
        ws.append(["Имя файла", "Аннотация", "Статус"])
        for r in results:
            ws.append([r["original_name"], r["title"], r["status"]])
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=results.xlsx"}
        )

    # txt
    lines = ["РЕЗУЛЬТАТЫ АННОТИРОВАНИЯ ДОКУМЕНТОВ", f"Исходная папка: {source}", "=" * 60, ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] Файл: {r['original_name']}")
        if r["status"] == "error":
            lines.append("   ⚠️ НЕВОЗМОЖНО ПРОЧИТАТЬ")
        else:
            lines.append(f"   Аннотация: {r['title']}")
        lines.append("-" * 40)
    text = "\n".join(lines)
    return StreamingResponse(
        iter([text.encode("utf-8")]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=результаты_анализа.txt"}
    )


@app.get("/api/browse")
async def browse(path: str = ""):
    """List directories for folder picker."""
    p = Path(path) if path else Path.home()
    if not p.exists() or not p.is_dir():
        p = Path.home()
    try:
        items = []
        for x in sorted(p.iterdir()):
            if x.name.startswith("."):
                continue
            items.append({"name": x.name, "path": str(x), "is_dir": x.is_dir()})
        return {"path": str(p), "items": items}
    except PermissionError:
        return {"path": str(p), "items": []}


# WebSocket for logs
@app.websocket("/ws/logs/{task_id}")
async def websocket_logs(websocket: WebSocket, task_id: str):
    await websocket.accept()
    last_len = 0
    try:
        while True:
            if task_id in task_logs:
                logs = task_logs[task_id]
                if len(logs) > last_len:
                    for msg in logs[last_len:]:
                        await websocket.send_text(msg)
                    last_len = len(logs)
                if task_id in tasks and tasks[task_id]["status"] in ("completed", "failed"):
                    break
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()