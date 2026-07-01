# Dockerfile для Аннотатора документов
# Версия: 1.0

# Используем стабильный Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Открываем порт для веб-интерфейса
EXPOSE 8000

# Переменная окружения для режима (по умолчанию local)
ENV OLLAMA_MODE=local

# Запускаем приложение
CMD ["python", "run.py"]
