FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn[standard]==0.30.1 \
    httpx==0.27.0 \
    aiomqtt==2.3.0 \
    aiokafka==0.11.0 \
    prometheus-client==0.20.0

COPY src/ src/
COPY main.py .

ENV PYTHONPATH=/app/src

EXPOSE 8010

CMD ["python", "main.py"]
