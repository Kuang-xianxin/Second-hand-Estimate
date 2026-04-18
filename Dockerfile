# ===== 后端 Dockerfile ======
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
