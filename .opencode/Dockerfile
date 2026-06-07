FROM python:3.13-slim

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 --no-create-home app

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
COPY bot_config_template.json ./bot_config_template.json

USER app

CMD ["python", "main.py", "--daemon"]
