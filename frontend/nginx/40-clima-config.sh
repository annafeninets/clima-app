#!/bin/sh
# Генерирует публичный runtime-конфиг frontend из переменных окружения контейнера.
set -eu

# В значения не пропускаем кавычки, обратные слэши и переводы строк.
clean() { printf '%s' "$1" | tr -d '"\\\r\n'; }

API_URL="$(clean "${CLIMA_PUBLIC_API_URL:-/api}")"
VAPID_PUBLIC_KEY="$(clean "${CLIMA_VAPID_PUBLIC_KEY:-}")"

cat > /usr/share/nginx/html/config.js <<CONFIG
window.CLIMA_CONFIG = {
  apiBaseUrl: "${API_URL}",
  vapidPublicKey: "${VAPID_PUBLIC_KEY}"
};
CONFIG
echo "clima: config.js generated (apiBaseUrl=${API_URL})"
