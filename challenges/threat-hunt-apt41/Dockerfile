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

# sshd on a high port — cap_drop=ALL strips CAP_NET_BIND_SERVICE
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# The hunter account. Password is documented in challenge.json + README.
RUN useradd -m -s /bin/bash hunter && \
    echo 'hunter:hunter' | chpasswd

# Investigation artefacts: log corpus, briefing, validator backend, CLI.
COPY logs/ /home/hunter/logs/
COPY investigation.md /home/hunter/investigation.md
COPY validator.py /opt/validator.py
COPY answer /usr/local/bin/answer
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chown -R hunter:hunter /home/hunter && \
    chmod +x /usr/local/bin/answer /usr/local/bin/entrypoint.sh && \
    chmod 600 /opt/validator.py


# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

EXPOSE 2222

CMD ["/usr/local/bin/entrypoint.sh"]
