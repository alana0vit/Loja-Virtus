"""
Simula UM cliente reclamando: faz uma compra e mostra o que o usuário vê.

    docker compose exec gateway python -m app.cliente maria BEMVINDO10

Repete a compra até ela falhar (no máximo 20 vezes) — com a falha ligada,
pedidos com cupom falham quando caem na réplica com bug.
"""

import json
import os
import sys

import httpx

GATEWAY_URL = os.getenv("CLIENTE_GATEWAY_URL", "http://localhost:8000")


def main() -> None:
    usuario = sys.argv[1] if len(sys.argv) > 1 else "maria"
    cupom = sys.argv[2] if len(sys.argv) > 2 else "BEMVINDO10"
    compra = {"user_id": usuario, "cupom": cupom,
              "itens": [{"sku": "MOCHILA-03", "quantidade": 1}, {"sku": "CANECA-02", "quantidade": 2}]}

    for tentativa in range(1, 21):
        r = httpx.post(f"{GATEWAY_URL}/checkout", json=compra, timeout=10,
                       headers={"x-user-id": usuario})  # simula o usuário autenticado
        if r.status_code >= 400:
            print(f"\n[{usuario}] tentativa {tentativa}: HTTP {r.status_code}")
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))
            print("\n>>> O usuário só tem esta mensagem e o código de suporte. Bora investigar.")
            return
        print(f"[{usuario}] tentativa {tentativa}: OK {r.json()['pedido_id']} (R$ {r.json()['total']})")
    print("\nNenhuma falha em 20 tentativas — a falha está ligada? (./scripts/falha.sh liga)")


if __name__ == "__main__":
    main()
