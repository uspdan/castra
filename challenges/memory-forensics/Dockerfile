FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN mkdir -p /data && python generate_dump.py

EXPOSE 5000

CMD ["python", "app.py"]
