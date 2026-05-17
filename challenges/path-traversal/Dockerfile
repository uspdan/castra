FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY docs/ /var/www/docs/
COPY flag.txt /flag.txt
RUN chmod 0444 /flag.txt

EXPOSE 5000

CMD ["python", "app.py"]
