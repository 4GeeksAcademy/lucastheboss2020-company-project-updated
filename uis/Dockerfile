FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache bash python3

COPY uis/website/package.json uis/website/package-lock.json ./uis/website/
RUN cd /app/uis/website && npm ci

COPY uis/backoffice/package.json uis/backoffice/package-lock.json ./uis/backoffice/
RUN cd /app/uis/backoffice && npm ci

COPY . .

EXPOSE 3000 3001

CMD ["bash", "/app/uis/start.sh"]