FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 prometheus-client==0.19.0 aiokafka==0.12.0 "redis[hiredis]>=5.0.1" \
    opentelemetry-sdk==1.24.0 opentelemetry-exporter-otlp-proto-grpc==1.24.0 opentelemetry-instrumentation-fastapi==0.45b0
COPY src/ ./src/
COPY main.py .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
