@echo off
chcp 65001 >nul
echo ============================================================
echo   Запуск Аннотатора на офлайн-компьютере
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

:: Проверка образа
if not exist "annotator.tar" (
    echo [ОШИБКА] Файл annotator.tar не найден!
    echo Скопируйте его из папки project на флешке.
    pause
    exit /b 1
)

:: Загрузка образа
echo [1/3] Загрузка Docker-образа...
docker load -i annotator.tar
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось загрузить образ!
    pause
    exit /b 1
)
echo [OK] Образ загружен
echo.

:: Проверка запущенных контейнеров
docker ps --format "{{.Names}}" | findstr "ollama-annotator" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Контейнер уже запущен. Останавливаем...
    docker-compose down
)

:: Запуск через docker-compose
echo [2/3] Запуск контейнера...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось запустить контейнер!
    echo Попробуйте запустить вручную:
    echo   docker run -d -p 8000:8000 --name annotator annotator:v1
    pause
    exit /b 1
)
echo [OK] Контейнер запущен
echo.

:: Ожидание запуска
echo [3/3] Ожидание запуска сервера...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo   ГОТОВО!
echo ============================================================
echo.
echo Откройте браузер и перейдите по адресу:
echo   http://localhost:8000
echo.
echo В веб-интерфейсе:
echo   1. Выберите режим LOCAL
echo   2. Нажмите "Применить и перезапустить сервер"
echo   3. Выберите модели из списка
echo.
echo Для остановки выполните: docker-compose down
echo Для просмотра логов: docker logs annotator
echo.
pause
