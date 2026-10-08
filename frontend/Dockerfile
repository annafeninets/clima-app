FROM nginx:stable-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/40-clima-config.sh /docker-entrypoint.d/40-clima-config.sh
RUN chmod +x /docker-entrypoint.d/40-clima-config.sh

COPY index.html service-worker.js icon-192.svg badge.svg /usr/share/nginx/html/
COPY src /usr/share/nginx/html/src
COPY styles /usr/share/nginx/html/styles
# config.js создаётся при старте контейнера из переменных окружения (см. 40-clima-config.sh).

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
