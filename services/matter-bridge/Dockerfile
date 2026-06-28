FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    httpx==0.26.0 \
    aiokafka==0.12.0 \
    aiohttp==3.9.1 \
    prometheus-client==0.19.0

# python-matter-server is optional; installed separately when real hardware is available.
# Uncomment for production builds with Matter hardware:
# RUN pip install --no-cache-dir python-matter-server==6.0.0

COPY src/ ./src/
COPY main.py .

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8008/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
