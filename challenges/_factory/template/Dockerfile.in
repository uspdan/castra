FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        python3 \
        python3-flask \
        curl \
        jq \
        ripgrep \
        less \
        vim-tiny \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

RUN useradd -m -s /bin/bash hunter && \
    echo 'hunter:hunter' | chpasswd

COPY logs/ /home/hunter/logs/
COPY investigation.md /home/hunter/investigation.md
COPY validator.py /opt/validator.py
COPY answer /usr/local/bin/answer
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chown -R hunter:hunter /home/hunter && \
    chmod +x /usr/local/bin/answer /usr/local/bin/entrypoint.sh && \
    chmod 600 /opt/validator.py

EXPOSE 2222

CMD ["/usr/local/bin/entrypoint.sh"]
