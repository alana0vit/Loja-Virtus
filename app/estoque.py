"""
estoque — reserva e libera itens. Tem latência variável para que a
demo tenha números realistas.
"""

import asyncio
import logging
import random

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .common import create_app

app = create_app("estoque")
log = logging.getLogger("estoque")

PRODUTOS = {
    "CAMISETA-01": {"preco": 59.90, "saldo": 10_000},
    "CANECA-02": {"preco": 34.50, "saldo": 10_000},
    "MOCHILA-03": {"preco": 189.00, "saldo": 10_000},
    "CADERNO-04": {"preco": 22.00, "saldo": 10_000},
    "FONE-05": {"preco": 249.90, "saldo": 10_000},
}


class Item(BaseModel):
    sku: str
    quantidade: int = 1


class Reserva(BaseModel):
    pedido_id: str
    itens: list[Item]


class Liberacao(BaseModel):
    pedido_id: str


@app.post("/reservas")
async def reservar(dados: Reserva):
    await asyncio.sleep(random.uniform(0.01, 0.06))
    subtotal = 0.0
    for item in dados.itens:
        produto = PRODUTOS.get(item.sku)
        if produto is None:
            log.warning("sku inexistente", extra={"pedido_id": dados.pedido_id, "sku": item.sku})
            return JSONResponse({"erro": f"sku {item.sku} inexistente"}, status_code=404)
        subtotal += produto["preco"] * item.quantidade
    log.info("itens reservados", extra={"pedido_id": dados.pedido_id,
                                         "skus": [i.sku for i in dados.itens],
                                         "subtotal": round(subtotal, 2)})
    return {"pedido_id": dados.pedido_id, "subtotal": round(subtotal, 2)}


@app.post("/liberacoes")
async def liberar(dados: Liberacao):
    log.info("reserva liberada", extra={"pedido_id": dados.pedido_id})
    return {"pedido_id": dados.pedido_id, "status": "liberado"}
