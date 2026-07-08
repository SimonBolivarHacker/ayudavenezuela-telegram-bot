FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    TG_MODE=polling

CMD ["python", "-m", "bot.main"]
