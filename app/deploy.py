"""
Simula um deploy/rollback na réplica onde é executado.

    python -m app.deploy 1.4.1    # versão com bug
    python -m app.deploy 1.4.0    # rollback
    python -m app.deploy status   # só mostra a versão em execução
"""

import sys

import httpx

URL = "http://localhost:8000/admin/versao"
arg = sys.argv[1] if len(sys.argv) > 1 else "status"

if arg == "status":
    versao = httpx.get(URL, timeout=5).json()["versao_atual"]
else:
    versao = httpx.post(URL, json={"versao": arg}, timeout=5).json()["versao_atual"]

aviso = "  <- COM BUG" if versao == "1.4.1" else ""
print(f" versão {versao}{aviso}")
