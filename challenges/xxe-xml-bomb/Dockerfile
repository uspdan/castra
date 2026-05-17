FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libxml2 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY flag.txt /flag.txt
RUN chmod 0444 /flag.txt

EXPOSE 5000

CMD ["python", "app.py"]
