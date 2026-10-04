FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_PORT=8000 \
    FILE_STORAGE_DIR=/data/files

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app app

# Sign-in evidence includes Chinese addresses; missing glyphs must never produce
# an apparently successful but incomplete location watermark.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from PIL import ImageFont; font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 20); assert font.getbbox('签到地点')[2] > 0"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN mkdir -p /data/files && chown -R app:app /app /data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3)); assert d['status']=='READY'"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000} --workers ${WEB_CONCURRENCY:-4}"]
