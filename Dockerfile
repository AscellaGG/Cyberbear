FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py briefing.py cves.py ai_ranking.py feeds.py svt_monitor.py database.py systemprompt.txt ./
COPY config/ ./config/

CMD ["python", "bot.py"]
