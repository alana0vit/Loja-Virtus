"""
Peças comuns aos serviços:
- middleware que lê/gera o contexto de rastreio (W3C Trace Context) e
  registra início e fim de cada requisição;
- cliente HTTP que propaga esse contexto para o próximo serviço.
"""

import logging
import os
import re
import secrets
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .logging_setup import setup_logging, span_id_var, trace_id_var, user_id_var

log = logging.getLogger("http")

# traceparent: versão-traceid(32 hex)-spanid(16 hex)-flags  (W3C Trace Context)
TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


def create_app(title: str) -> FastAPI:
    setup_logging()
    app = FastAPI(title=title)

    @app.middleware("http")
    async def contexto_e_log(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        # 1. Reaproveita o trace_id de quem chamou ou inicia um novo
        match = TRACEPARENT_RE.match(request.headers.get("traceparent", ""))
        trace_id = match.group(1) if match else secrets.token_hex(16)
        parent_span = match.group(2) if match else ""
        span_id = secrets.token_hex(8)

        trace_id_var.set(trace_id)
        span_id_var.set(span_id)
        user_id_var.set(request.headers.get("x-user-id", ""))

        inicio = time.perf_counter()
        log.info(
            "requisição recebida",
            extra={"http_method": request.method, "http_path": request.url.path,
                   "parent_span_id": parent_span},
        )
        try:
            response = await call_next(request)
        except Exception:
            duracao = round((time.perf_counter() - inicio) * 1000, 1)
            log.exception(
                "erro não tratado",
                extra={"http_method": request.method, "http_path": request.url.path,
                       "http_status": 500, "duracao_ms": duracao},
            )
            response = JSONResponse({"erro": "erro interno", "trace_id": trace_id},
                                    status_code=500)
        else:
            duracao = round((time.perf_counter() - inicio) * 1000, 1)
            nivel = logging.WARNING if response.status_code >= 400 else logging.INFO
            log.log(
                nivel,
                "requisição concluída",
                extra={"http_method": request.method, "http_path": request.url.path,
                       "http_status": response.status_code, "duracao_ms": duracao},
            )
        response.headers["x-trace-id"] = trace_id
        return response

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def headers_propagados() -> dict:
    """Cabeçalhos que levam o contexto adiante para o próximo serviço."""
    return {
        "traceparent": f"00-{trace_id_var.get()}-{span_id_var.get()}-01",
        "x-user-id": user_id_var.get(),
    }


async def chamar(metodo: str, url: str, **kwargs) -> httpx.Response:
    # Cliente novo por chamada: o DNS do Docker distribui entre as réplicas
    timeout = float(os.getenv("HTTP_TIMEOUT", "3"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.request(metodo, url, headers=headers_propagados(), **kwargs)
