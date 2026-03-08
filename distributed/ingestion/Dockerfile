FROM python:3.9-slim

WORKDIR /app

RUN pip install fastapi uvicorn aiokafka pydantic

COPY shared /app/shared
COPY ingestion /app/ingestion

WORKDIR /app/ingestion

CMD ["python", "main.py"]
