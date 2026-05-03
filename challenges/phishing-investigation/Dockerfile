FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY *.js *.json .

EXPOSE 3000

CMD ["node", "server.js"]
