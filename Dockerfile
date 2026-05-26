FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir feedparser requests
COPY . .
RUN mkdir -p /app/data
ENV STATE_FILE=/app/data/bot_state.json
CMD ["python", "-u", "main.py"]
