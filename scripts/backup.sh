#!/bin/sh
# Резервная копия базы и фотографий из работающего docker compose-стека в ./backups
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"

# Консистентный снимок SQLite (безопасно при работающем сервере, WAL учитывается).
docker compose exec -T backend python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/clima.sqlite3")
dst = sqlite3.connect("/data/backup.sqlite3")
src.backup(dst)
dst.close()
src.close()
PY
docker compose cp backend:/data/backup.sqlite3 "backups/clima-$stamp.sqlite3"
docker compose exec -T backend rm -f /data/backup.sqlite3
docker compose exec -T backend tar -C /data -cf - uploads > "backups/uploads-$stamp.tar"
echo "Готово: backups/clima-$stamp.sqlite3, backups/uploads-$stamp.tar"
