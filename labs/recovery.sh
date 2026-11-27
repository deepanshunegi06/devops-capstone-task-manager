#!/usr/bin/env bash
# Restore into a fresh scratch database; never overwrite the source.
set -euo pipefail
docker exec orbit-labs-db-1 pg_dump -U taskmanager -d taskmanager --no-owner --no-acl > /tmp/orbit-lab-backup.sql
docker exec orbit-labs-db-1 createdb -U taskmanager orbit_lab_restore
docker exec -i orbit-labs-db-1 psql -v ON_ERROR_STOP=1 -U taskmanager -d orbit_lab_restore < /tmp/orbit-lab-backup.sql
for database in taskmanager orbit_lab_restore; do
  docker exec orbit-labs-db-1 psql -U taskmanager -d "$database" -Atc 'SELECT count(*) FROM tasks;'
done
