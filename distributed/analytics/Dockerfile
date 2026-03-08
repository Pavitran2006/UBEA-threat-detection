FROM python:3.9-slim

WORKDIR /app

# Install dependencies including ML libs
RUN pip install pandas numpy scikit-learn elasticsearch aiokafka

# Copy code
COPY shared /app/shared
COPY analytics /app/analytics

WORKDIR /app/analytics

CMD ["python", "main.py"]
