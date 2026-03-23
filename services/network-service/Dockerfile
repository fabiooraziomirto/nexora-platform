FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 prometheus-client==0.19.0 sqlalchemy==2.0.23 pymysql==1.1.1 cryptography==41.0.7
COPY main.py .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
