"""
gateway — porta de entrada da loja. Recebe o checkout do cliente e repassa
para o serviço de pedidos. Quando algo falha, devolve ao cliente um
"código de suporte" (o trace_id), que é o que o usuário informa ao reclamar.
"""

import logging
import os

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .common import chamar, create_app
from .logging_setup import trace_id_var, user_id_var

PEDIDOS_URL = os.getenv("PEDIDOS_URL", "http://pedidos:8000")

app = create_app("gateway")
log = logging.getLogger("gateway")


class Item(BaseModel):
    sku: str
    quantidade: int = 1


class Checkout(BaseModel):
    user_id: str
    itens: list[Item]
    cupom: str | None = None


@app.post("/checkout")
async def checkout(dados: Checkout, request: Request):
    # O usuário autenticado entra no contexto: todos os logs daqui em diante o carregam
    user_id_var.set(dados.user_id)
    log.info("checkout iniciado", extra={"qtd_itens": len(dados.itens), "cupom": dados.cupom})

    try:
        resp = await chamar("POST", f"{PEDIDOS_URL}/pedidos", json=dados.model_dump())
    except httpx.HTTPError as exc:
        log.error("serviço de pedidos indisponível", extra={"erro": repr(exc)})
        return JSONResponse(
            {"erro": "Não foi possível concluir sua compra. Tente novamente.",
             "codigo_suporte": trace_id_var.get()},
            status_code=503,
        )

    if 400 <= resp.status_code < 500:
        # Erro do cliente (ex.: produto inexistente): esperado, não é incidente
        log.warning("checkout recusado", extra={"upstream": "pedidos", "upstream_status": resp.status_code})
        return JSONResponse({"erro": resp.json().get("erro", "pedido recusado")}, status_code=resp.status_code)

    if resp.status_code >= 500:
        # Note que o gateway não sabe a causa: ele só vê o status de quem chamou
        log.error("checkout falhou", extra={"upstream": "pedidos", "upstream_status": resp.status_code})
        return JSONResponse(
            {"erro": "Não foi possível concluir sua compra. Tente novamente.",
             "codigo_suporte": trace_id_var.get()},
            status_code=502,
        )

    pedido = resp.json()
    log.info("checkout concluído", extra={"pedido_id": pedido["pedido_id"], "valor_total": pedido["total"]})
    return pedido
