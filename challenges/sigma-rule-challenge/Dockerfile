FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY *.json .

RUN python generate_logs.py

EXPOSE 5000

CMD ["python", "app.py"]
