FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openssh-server \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Setup SSH on a high port so cap_drop=ALL can still bind it
# (port 22 would need CAP_NET_BIND_SERVICE which the orchestrator
# strips). /run/sshd is recreated by the entrypoint each launch
# because /run is a fresh tmpfs under the read-only rootfs profile.
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# Create CTF user
RUN useradd -m -s /bin/bash ctfuser && \
    echo 'ctfuser:ctfuser' | chpasswd

# Create the flag file owned by root
RUN echo 'CTF{REDACTED}' > /root/flag.txt && \
    chmod 600 /root/flag.txt

# Create dummy data files for the backup tool
RUN mkdir -p /opt/data && \
    echo 'Server configuration file v2.1' > /opt/data/config.txt && \
    echo 'Application log entry 2024-01-15' > /opt/data/app.log && \
    echo 'Database connection: db.internal:5432' > /opt/data/database.conf && \
    echo 'Backup schedule: daily at 02:00 UTC' > /opt/data/schedule.txt && \
    echo 'Service status: running' > /opt/data/status.txt

# Copy and compile the vulnerable SUID binary
COPY siege-backup.c /tmp/siege-backup.c
RUN gcc -o /usr/local/bin/siege-backup /tmp/siege-backup.c && \
    chown root:root /usr/local/bin/siege-backup && \
    chmod u+s /usr/local/bin/siege-backup && \
    rm /tmp/siege-backup.c


# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

EXPOSE 2222

CMD ["sh", "-c", "mkdir -p /run/sshd && exec /usr/sbin/sshd -D"]
