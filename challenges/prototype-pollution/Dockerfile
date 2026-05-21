FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --omit=dev --no-audit --no-fund

COPY server.js .


# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

EXPOSE 3000
USER node
CMD ["node", "server.js"]
