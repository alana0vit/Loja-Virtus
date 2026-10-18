#!/usr/bin/env bash
# Liga/desliga a falha da demo: um "deploy ruim" (v1.4.1) em UMA das réplicas de pagamentos.
#
#   ./scripts/falha.sh liga       -> réplica 2 de pagamentos vai para a v1.4.1 (com bug)
#   ./scripts/falha.sh desliga    -> rollback da réplica 2 para a v1.4.0
#   ./scripts/falha.sh status     -> mostra a versão de cada réplica
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-status}" in
  liga)    docker compose exec -T --index 2 pagamentos python -m app.deploy 1.4.1 >/dev/null
           echo "Falha LIGADA: pagamentos-2 agora roda a v1.4.1." ;;
  desliga) docker compose exec -T --index 2 pagamentos python -m app.deploy 1.4.0 >/dev/null
           echo "Falha DESLIGADA: rollback de pagamentos-2 para a v1.4.0."
           echo "Novos erros param em segundos; as barras antigas continuam no histórico do gráfico." ;;
  status)  ;;
  *) echo "uso: $0 liga|desliga|status"; exit 1 ;;
esac

echo "Versões em execução:"
for i in 1 2; do
  printf "  pagamentos-%s:" "$i"
  docker compose exec -T --index "$i" pagamentos python -m app.deploy status
done
