"""
Ponto de entrada único: `python -m app.run <servico>`.
Sobe o uvicorn com os logs do próprio servidor também em JSON.
"""

import importlib
import os
import sys

import uvicorn

if __name__ == "__main__":
    servico = sys.argv[1] if len(sys.argv) > 1 else os.environ["SERVICE_NAME"]
    os.environ.setdefault("SERVICE_NAME", servico)
    modulo = importlib.import_module(f"app.{servico}")
    # log_config=None: uvicorn usa o logger raiz, já configurado em JSON
    uvicorn.run(modulo.app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                log_config=None, access_log=False)
