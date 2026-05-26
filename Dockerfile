FROM python:3.13-slim

RUN pip install --no-cache-dir feedparser requests

WORKDIR /app
COPY . .

RUN mkdir -p /app/data

ENV STATE_FILE=/app/data/bot_state.json
ENV DATA_DIR=/app/data

CMD ["python", "-u", "bot.py"]
