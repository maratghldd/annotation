@echo off
chcp 65001 >nul
echo ============================================================
echo   Подготовка проекта для переноса на офлайн-компьютер
echo ============================================================
echo.

:: Проверка Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не найден! Установите Docker Desktop.
    pause
    exit /b 1
)
echo [OK] Docker найден
echo.

:: Сборка образа
echo [1/3] Сборка Docker-образа...
docker build -t annotator:v1 .
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось собрать образ!
    pause
    exit /b 1
)
echo [OK] Образ собран
echo.

:: Сохранение образа
echo [2/3] Сохранение образа в annotator.tar...
docker save annotator:v1 -o annotator.tar
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось сохранить образ!
    pause
    exit /b 1
)
echo [OK] Образ сохранен в annotator.tar
echo.

:: Создание папки для флешки
echo [3/3] Подготовка файлов для флешки...
if exist "FLASH_DRIVE_READY" rmdir /s /q "FLASH_DRIVE_READY"
mkdir "FLASH_DRIVE_READY"
mkdir "FLASH_DRIVE_READY\project"
mkdir "FLASH_DRIVE_READY\ollama_models"

:: Копирование файлов проекта
copy /Y "annotator.tar" "FLASH_DRIVE_READY\project\"
copy /Y "Dockerfile" "FLASH_DRIVE_READY\project\"
copy /Y "docker-compose.yml" "FLASH_DRIVE_READY\project\"
copy /Y "requirements.txt" "FLASH_DRIVE_READY\project\"
copy /Y "DEPLOYMENT.md" "FLASH_DRIVE_READY\project\"
copy /Y "config_local.py" "FLASH_DRIVE_READY\project\"

:: Копирование моделей Ollama (если есть)
if exist "%USERPROFILE%\.ollama\models" (
    echo Копирование моделей Ollama...
    xcopy "%USERPROFILE%\.ollama\models\*" "FLASH_DRIVE_READY\ollama_models\" /E /I /Y
    echo [OK] Модели скопированы
) else (
    echo [ПРЕДУПРЕЖДЕНИЕ] Модели Ollama не найдены в %USERPROFILE%\.ollama\models
    echo Скачайте модели командой: ollama pull qwen2.5:3b
)

echo.
echo ============================================================
echo   ГОТОВО!
echo ============================================================
echo.
echo Папка FLASH_DRIVE_READY содержит:
echo   - project/          - файлы проекта
echo   - ollama_models/    - модели Ollama
echo   - annotator.tar     - Docker-образ
echo.
echo Скопируйте содержимое FLASH_DRIVE_READY на флешку.
echo Также скачайте установщики:
echo   - Docker Desktop: https://www.docker.com/products/docker-desktop/
echo   - Ollama: https://ollama.com/download
echo.
pause
