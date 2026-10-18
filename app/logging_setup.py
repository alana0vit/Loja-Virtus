"""
Configuração de logs estruturados (JSON) compartilhada por todos os serviços.

Cada linha de log é um objeto JSON com campos fixos:
    ts, level, service, version, msg, trace_id, span_id, user_id
mais quaisquer campos extras passados em `extra={...}`.

O contexto da requisição (trace_id, user_id...) fica em `contextvars`,
então qualquer log emitido durante a requisição já sai com esses campos,
sem precisar repassá-los manualmente.

LOG_FORMAT=texto liga o modo "antes": logs em texto livre, sem IDs,
para mostrar o problema que a solução resolve.
"""

import contextvars
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

SERVICE = os.getenv("SERVICE_NAME", "desconhecido")

# Contexto da requisição atual (um valor por requisição/tarefa assíncrona)
trace_id_var = contextvars.ContextVar("trace_id", default="")
span_id_var = contextvars.ContextVar("span_id", default="")
user_id_var = contextvars.ContextVar("user_id", default="")

# Atributos padrão do LogRecord que não devem ir como campos extras
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # campo extra do uvicorn, só serve para terminal colorido
}


def service_version() -> str:
    # Lido a cada log para refletir trocas de versão em tempo de execução
    return os.getenv("SERVICE_VERSION", "1.0.0")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname.lower().replace("warning", "warn"),
            "service": SERVICE,
            "version": service_version(),
            "msg": record.getMessage(),
            "logger": record.name,
            "trace_id": trace_id_var.get(),
            "span_id": span_id_var.get(),
            "user_id": user_id_var.get(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            exc_type, exc, tb = record.exc_info
            entry["error_type"] = exc_type.__name__
            entry["error_message"] = str(exc)
            entry["stack_trace"] = "".join(traceback.format_exception(exc_type, exc, tb))
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """O "antes": texto livre, sem identificadores de correlação."""

    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(message)s")


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv("LOG_FORMAT", "json").lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(TextFormatter() if fmt == "texto" else JsonFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Bibliotecas barulhentas: só avisos para cima
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
