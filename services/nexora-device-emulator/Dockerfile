FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir websockets>=12.0
COPY emulator.py /app/emulator.py

CMD ["python", "/app/emulator.py"]
