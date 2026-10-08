#!/bin/sh
# Резервная копия PostgreSQL и фотографий из работающего docker compose-стека в ./backups
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"

# pg_dump делает консистентный снимок без остановки сервера. Формат custom сжат; восстановление — pg_restore.
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "backups/clima-$stamp.dump"
docker compose exec -T backend tar -C /data -cf - uploads > "backups/uploads-$stamp.tar"
echo "Готово: backups/clima-$stamp.dump, backups/uploads-$stamp.tar"
