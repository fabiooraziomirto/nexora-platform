FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry==1.7.1
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY src ./src
ENV PYTHONPATH=/app/src

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "plugin_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
