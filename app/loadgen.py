"""
Gerador de tráfego: simula clientes fazendo compras continuamente,
para que os painéis tenham dados e a falha apareça "no meio da multidão".
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
RPS = float(os.getenv("RPS", "4"))

USUARIOS = ["maria", "joao", "ana", "lucas", "beatriz", "rafael", "camila", "diego",
            "fernanda", "gustavo", "helena", "igor"]
SKUS = ["CAMISETA-01", "CANECA-02", "MOCHILA-03", "CADERNO-04", "FONE-05"]
CUPONS = ["BEMVINDO10", "FRETE5", "BLACK20"]


def gerar_compra() -> dict:
    itens = [{"sku": random.choice(SKUS), "quantidade": random.randint(1, 3)}
             for _ in range(random.randint(1, 3))]
    if random.random() < 0.02:
        itens.append({"sku": "PRODUTO-REMOVIDO", "quantidade": 1})  # ruído realista: 404
    cupom = random.choice(CUPONS) if random.random() < 0.35 else None
    return {"user_id": random.choice(USUARIOS), "itens": itens, "cupom": cupom}


def resumo(evento: dict) -> None:
    # O loadgen loga em JSON também, mas não entra no Loki (sem o rótulo de coleta)
    print(json.dumps(evento, ensure_ascii=False), flush=True)


async def uma_compra(client: httpx.AsyncClient) -> None:
    compra = gerar_compra()
    try:
        r = await client.post(f"{GATEWAY_URL}/checkout", json=compra,
                              headers={"x-user-id": compra["user_id"]})  # usuário "autenticado"
        resumo({"ts": datetime.now().isoformat(timespec="seconds"), "user_id": compra["user_id"],
                "status": r.status_code})
    except httpx.HTTPError as exc:
        resumo({"ts": datetime.now().isoformat(timespec="seconds"), "erro": repr(exc)})


async def main() -> None:
    await asyncio.sleep(float(os.getenv("ATRASO_INICIAL", "5")))
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            asyncio.create_task(uma_compra(client))
            await asyncio.sleep(random.expovariate(RPS))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
