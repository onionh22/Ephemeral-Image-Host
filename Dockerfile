FROM python:3.13.4-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

RUN mkdir -p /app/uploaded_images && chmod 777 /app/uploaded_images

ENV UPLOAD_DIR="uploaded_images"

ENV SWEEP_INTERVAL=30

ENV TTL_LIMIT=86400

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:7860", "main:app"]