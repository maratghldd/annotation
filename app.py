"""FastAPI web application for document analysis."""
import io
import os
import uuid
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from core import DocumentAnalyzer, AnalysisResult, ReportGenerator


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


def run_folder_analysis_task(task_id: str, source: str, output: str):
    task_created_files[task_id] = []
    try:
        tasks[task_id]["status"] = "running"
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        output_dirs[task_id] = output_path
        source_folders[task_id] = source

        def cancel_check():
            return task_cancelled.get(task_id, False)

        analyzer = DocumentAnalyzer(log_callback=get_log_callback(task_id), cancel_check=cancel_check)
        results, created_files = analyzer.run_folder_analysis(source, output_path)
        task_created_files[task_id] = created_files

        if task_cancelled.get(task_id, False):
            _cleanup_task_files(task_id)
            tasks[task_id]["status"] = "cancelled"
            task_results[task_id] = []
            get_log_callback(task_id)("\nОстановлено. Созданные файлы удалены.")
            return

        task_results[task_id] = [
            {"file_name": r.file_name, "original_name": r.original_name, "title": r.title, "status": r.status, "file_path": r.file_path}
            for r in results
        ]
        tasks[task_id]["status"] = "completed"
        get_log_callback(task_id)("\nРабота завершена")

        report_file = output_path / "результаты_анализа.txt"
        ReportGenerator.save_results(results, report_file, source)
    except Exception as e:
        if task_cancelled.get(task_id, False):
            _cleanup_task_files(task_id)
            tasks[task_id]["status"] = "cancelled"
            get_log_callback(task_id)("\nОстановлено. Созданные файлы удалены.")
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


def run_single_file_task(task_id: str, file_path: Path, output_dir: Path):
    try:
        tasks[task_id]["status"] = "running"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dirs[task_id] = output_dir
        source_folders[task_id] = str(file_path.parent)

        analyzer = DocumentAnalyzer(log_callback=get_log_callback(task_id))
        result = analyzer.run_single_file(file_path, output_dir)

        task_results[task_id] = [{
            "file_name": result.file_name,
            "original_name": result.original_name,
            "title": result.title,
            "status": result.status,
            "file_path": result.file_path
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


class UpdateTitleRequest(BaseModel):
    task_id: str
    file_name: str
    new_title: str


class RegenerateRequest(BaseModel):
    task_id: str
    file_name: str
    detailed: bool = False


class CancelTaskRequest(BaseModel):
    task_id: str


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

    background_tasks.add_task(run_folder_analysis_task, task_id, source, output)
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/analyze-file")
async def analyze_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = Form(...)
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
    background_tasks.add_task(run_single_file_task, task_id, file_path, output_dir)
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/cancel-task")
async def cancel_task(req: CancelTaskRequest):
    """Cancel a running folder analysis task and clean up created files."""
    task_id = req.task_id
    if not task_id or task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    task_cancelled[task_id] = True
    return {"ok": True, "status": "cancelling"}


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

    # Этап регенерации теперь тоже использует цепочку моделей
    from core import OllamaClient, DocumentProcessor
    processor = DocumentProcessor()
    ollama = OllamaClient()
    
    filename = sanitize_filename(req.file_name)
    base = output_dirs[req.task_id]
    file_path = base / filename
    
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="Файл не найден")
         
    text = processor.read_text(file_path)
    
    # Полный цикл: Перевод -> Аннотация -> Проверка
    working_text = ollama.translate_if_needed(text)
    initial = ollama.generate_initial_annotation(working_text, filename)
    final_title = ollama.review_and_finalize(working_text, initial)
    
    for r in task_results[req.task_id]:
        if r["file_name"] == filename or r["original_name"] == req.file_name:
            r["title"] = final_title
            r["status"] = "success"
            return {"ok": True, "title": final_title}
            
    raise HTTPException(status_code=404, detail="Файл не найден в результатах")


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
        writer.writerow(["Имя файла", "Сгенерированное название", "Статус"])
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
        ws.append(["Имя файла", "Сгенерированное название", "Статус"])
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
    lines = ["РЕЗУЛЬТАТЫ АНАЛИЗА ДОКУМЕНТОВ", f"Исходная папка: {source}", "=" * 60, ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] Файл: {r['original_name']}")
        if r["status"] == "error":
            lines.append("   ⚠️ НЕВОЗМОЖНО ПРОЧИТАТЬ")
        else:
            lines.append(f"   Название: {r['title']}")
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