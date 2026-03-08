FROM python:3.9-slim

WORKDIR /app

RUN pip install sqlalchemy pymysql aiokafka pydantic

COPY shared /app/shared
COPY risk /app/risk

WORKDIR /app/risk

CMD ["python", "main.py"]
