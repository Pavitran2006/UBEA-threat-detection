FROM python:3.9-slim

WORKDIR /app

RUN pip install fastapi uvicorn aiokafka elasticsearch sqlalchemy pymysql jinja2

COPY shared /app/shared
COPY gateway /app/gateway

WORKDIR /app/gateway

EXPOSE 8000

CMD ["python", "main.py"]
