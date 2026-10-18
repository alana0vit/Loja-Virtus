#!/usr/bin/env bash
# Simula a cliente que reclama: faz compras até uma falhar e mostra o código de suporte.
#
#   ./scripts/cliente.sh                 -> maria, cupom BEMVINDO10
#   ./scripts/cliente.sh joao BLACK20
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose exec gateway python -m app.cliente "${1:-maria}" "${2:-BEMVINDO10}"
