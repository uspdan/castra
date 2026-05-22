FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

RUN mkdir -p /data && python generate_keys.py


EXPOSE 5000

CMD ["python", "app.py"]
