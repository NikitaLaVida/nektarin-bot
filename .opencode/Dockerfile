FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir yt-dlp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker_main.py ./main.py
COPY gaming_news_bot.py .
COPY bot/ ./bot/
COPY bot_config.json . 2>/dev/null || true
COPY cookies.txt . 2>/dev/null || true

CMD ["python", "main.py", "--daemon"]
