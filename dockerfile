# Базовый образ
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY bot/ .

ENV PATH=/root/.local/bin:$PATH
CMD ["python", "bot.py"]