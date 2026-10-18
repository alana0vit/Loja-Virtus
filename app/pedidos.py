"""
pedidos — orquestra a compra: reserva os itens no estoque e cobra no
serviço de pagamentos. Se a cobrança falhar, desfaz a reserva.
"""

import logging
import os
import secrets

import httpx
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .common import chamar, create_app

ESTOQUE_URL = os.getenv("ESTOQUE_URL", "http://estoque:8000")
PAGAMENTOS_URL = os.getenv("PAGAMENTOS_URL", "http://pagamentos:8000")

app = create_app("pedidos")
log = logging.getLogger("pedidos")


class Item(BaseModel):
    sku: str
    quantidade: int = 1


class NovoPedido(BaseModel):
    user_id: str
    itens: list[Item]
    cupom: str | None = None


@app.post("/pedidos")
async def criar_pedido(dados: NovoPedido):
    pedido_id = "PED-" + secrets.token_hex(4).upper()
    log.info("pedido criado", extra={"pedido_id": pedido_id})

    # 1. Reserva no estoque
    try:
        reserva = await chamar("POST", f"{ESTOQUE_URL}/reservas",
                               json={"pedido_id": pedido_id, "itens": [i.model_dump() for i in dados.itens]})
    except httpx.HTTPError as exc:
        log.error("estoque indisponível", extra={"pedido_id": pedido_id, "erro": repr(exc)})
        return JSONResponse({"erro": "estoque indisponível"}, status_code=503)
    if reserva.status_code >= 400:
        log.warning("reserva recusada", extra={"pedido_id": pedido_id, "upstream_status": reserva.status_code})
        return JSONResponse({"erro": "itens indisponíveis"}, status_code=409)
    subtotal = reserva.json()["subtotal"]

    # 2. Cobrança
    try:
        cobranca = await chamar("POST", f"{PAGAMENTOS_URL}/cobrancas",
                                json={"pedido_id": pedido_id, "subtotal": subtotal, "cupom": dados.cupom})
    except httpx.HTTPError as exc:
        cobranca = None
        log.error("pagamentos indisponível", extra={"pedido_id": pedido_id, "erro": repr(exc)})

    if cobranca is None or cobranca.status_code >= 400:
        if cobranca is not None:
            log.error("cobrança falhou", extra={"pedido_id": pedido_id, "upstream": "pagamentos",
                                                 "upstream_status": cobranca.status_code})
        # Compensação: libera o que foi reservado
        await chamar("POST", f"{ESTOQUE_URL}/liberacoes", json={"pedido_id": pedido_id})
        log.warning("reserva desfeita após falha no pagamento", extra={"pedido_id": pedido_id})
        return JSONResponse({"erro": "falha no pagamento"}, status_code=502)

    total = cobranca.json()["total"]
    log.info("pedido confirmado", extra={"pedido_id": pedido_id, "valor_total": total})
    return {"pedido_id": pedido_id, "status": "confirmado", "total": total}
