#!/usr/bin/env bash
# O "ANTES": como se investiga sem logs centralizados.
# Um terminal por contêiner, grep em cada um, e nada liga uma linha à outra.
set -uo pipefail
cd "$(dirname "$0")/.."

for c in $(docker compose ps --format '{{.Name}}' gateway pedidos estoque pagamentos); do
  echo "=================== $c ==================="
  docker logs --since 5m "$c" 2>&1 | grep -iE "erro|error|falh" | tail -n 5
done
