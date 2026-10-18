"""
pagamentos — aplica cupom de desconto e cobra o pedido.

Roda com 2 réplicas. A falha da demo é um "deploy ruim" (versão 1.4.1)
aplicado em apenas UMA réplica: a nova tabela de cupons guarda o percentual
como texto ("10%") e o código faz int("10%") -> ValueError. Só pedidos COM
cupom que caem NESSA réplica falham — por isso é difícil de achar com grep.

POST /admin/versao {"versao": "1.4.1"} troca a versão em tempo de execução
(usado por scripts/falha.sh).
"""

import asyncio
import logging
import os
import random

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .common import create_app
from .logging_setup import service_version

app = create_app("pagamentos")
log = logging.getLogger("pagamentos")

# Tabela de cupons da versão estável (1.4.0): percentual como inteiro
CUPONS_V140 = {"BEMVINDO10": 10, "FRETE5": 5, "BLACK20": 20}
# Tabela "migrada" na versão 1.4.1: percentual virou texto
CUPONS_V141 = {"BEMVINDO10": "10%", "FRETE5": "5%", "BLACK20": "20%"}


class Cobranca(BaseModel):
    pedido_id: str
    subtotal: float
    cupom: str | None = None


class Versao(BaseModel):
    versao: str


def calcular_desconto(subtotal: float, cupom: str | None) -> float:
    if not cupom:
        return 0.0
    if service_version() == "1.4.1":
        percentual = int(CUPONS_V141[cupom])  # BUG: int("10%") -> ValueError
    else:
        percentual = CUPONS_V140.get(cupom, 0)
    return round(subtotal * percentual / 100, 2)


@app.post("/cobrancas")
async def cobrar(dados: Cobranca):
    await asyncio.sleep(random.uniform(0.02, 0.08))  # chamada ao "adquirente"
    try:
        desconto = calcular_desconto(dados.subtotal, dados.cupom)
    except Exception:
        log.exception("erro ao calcular desconto do cupom",
                      extra={"pedido_id": dados.pedido_id, "cupom": dados.cupom})
        return JSONResponse({"erro": "falha interna no pagamento"}, status_code=500)

    total = round(dados.subtotal - desconto, 2)
    log.info("pagamento aprovado", extra={"pedido_id": dados.pedido_id, "cupom": dados.cupom,
                                          "desconto": desconto, "valor_total": total})
    return {"pedido_id": dados.pedido_id, "total": total, "status": "aprovado"}


@app.get("/admin/versao")
async def versao_atual():
    return {"versao_atual": service_version()}


@app.post("/admin/versao")
async def trocar_versao(dados: Versao):
    anterior = service_version()
    os.environ["SERVICE_VERSION"] = dados.versao
    log.warning("versão alterada (deploy)", extra={"versao_anterior": anterior, "versao_nova": dados.versao})
    return {"versao_anterior": anterior, "versao_atual": dados.versao}
