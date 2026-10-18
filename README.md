# Logs estruturados e centralizados — Seminário de Observabilidade (Tema 3)

**Equipe:** Alana, Pedro e Chrystian

> **Problema.** Logs em texto livre espalhados por vários contêineres: achar a causa de um erro
> exige `ssh` e `grep` em cada máquina — e mesmo assim nada liga a linha de um serviço à do outro.
>
> **Solução.** Todos os serviços passam a logar em **JSON** com campos fixos (`trace_id`, `user_id`,
> `service`, `version`...). O **Grafana Alloy** coleta o stdout de todos os contêineres e envia ao
> **Grafana Loki**, que guarda e indexa só rótulos de baixa cardinalidade. No **Grafana**, uma única
> consulta encontra a requisição de um usuário em todos os serviços.

---

## Subir tudo (um comando)

Pré‑requisito: Docker com Docker Compose v2 (Docker Desktop no Windows/macOS serve).

```bash
docker compose up -d --build
```

| O quê | Onde |
|---|---|
| Grafana (sem login) — painel "Loja — Logs centralizados" | http://localhost:3000 |
| Loki (API) | http://localhost:3100 |
| Alloy (grafo do pipeline de coleta) | http://localhost:12345 |
| API da loja (gateway) | http://localhost:8080/docs |

Em ~30 s o gerador de carga já está fazendo compras (≈4 por segundo) e os painéis se enchem.

Para desligar e apagar os dados: `docker compose down -v`.

---

## Arquitetura

```
                  ┌─────────── aplicação (logs JSON no stdout) ───────────┐
 loadgen ──HTTP──▶ gateway ──▶ pedidos ──┬──▶ estoque                      │
 cliente.sh                              └──▶ pagamentos (2 réplicas)       │
                  └──────────────────────────┬─────────────────────────────┘
                                             │ stdout dos contêineres (Docker)
                                             ▼
                        Grafana Alloy  ── descobre contêineres com o rótulo observabilidade.logs=true
                                       ── rótulos: service, container, level
                                       ── trace_id → metadado estruturado
                                             │ push HTTP
                                             ▼
                        Grafana Loki   ── índice só dos rótulos; linhas comprimidas em chunks
                                       ── retenção de 72 h
                                             │ LogQL
                                             ▼
                        Grafana        ── painel + Explore + link clicável no trace_id
```

- **Propagação de contexto.** O gateway cria o `trace_id` e o envia no cabeçalho
  `traceparent` (formato W3C Trace Context). Cada serviço lê o cabeçalho, coloca o ID num
  `contextvar` e todo log da requisição sai com ele — sem passar o ID manualmente.
- **Rótulos vs conteúdo.** Só `service`, `container` e `level` viram rótulos (≈15 streams no total).
  `user_id`, `pedido_id` e `trace_id` ficam no conteúdo JSON e são filtrados na hora da consulta.

### Estrutura do repositório

```
app/                    código dos serviços (Python + FastAPI), uma imagem só
  logging_setup.py      formatador JSON + contexto (trace_id, user_id)
  common.py             middleware de contexto/log e cliente HTTP que propaga o traceparent
  gateway.py pedidos.py estoque.py pagamentos.py
  loadgen.py            gerador de carga
  cliente.py            simula a cliente que reclama
  deploy.py             troca a versão de uma réplica (usado na falha)
observability/
  alloy/config.alloy    pipeline de coleta
  loki/config.yaml      armazenamento, esquema e retenção
  grafana/              fonte de dados + painel provisionados
scripts/                falha.sh, cliente.sh, grep-antes.sh
docs/ROTEIRO.md         roteiro da apresentação e da demo
docs/EXPLORE.md         passo a passo do Explore do Grafana
```

---

## Cenário de falha (reproduzir a demo)

A falha é um **deploy ruim em uma só réplica** do serviço `pagamentos`: a versão 1.4.1 lê a tabela
de cupons num formato novo (`"10%"` em vez de `10`) e quebra com `ValueError`. Só falham pedidos
**com cupom** que caem **nessa réplica** — intermitente e difícil de achar no `grep`.

```bash
./scripts/falha.sh liga        # réplica 2 de pagamentos vai para a v1.4.1 (com bug)
./scripts/cliente.sh maria     # a "Maria" compra até falhar e recebe um código de suporte
./scripts/grep-antes.sh        # como seria investigar sem a solução
./scripts/falha.sh desliga     # rollback para a v1.4.0
./scripts/falha.sh status      # versão em execução de cada réplica
```

**No Windows sem Git Bash**, os mesmos comandos direto:

```powershell
docker compose exec --index 2 pagamentos python -m app.deploy 1.4.1
docker compose exec gateway python -m app.cliente maria BEMVINDO10
docker compose exec --index 2 pagamentos python -m app.deploy 1.4.0
docker compose exec --index 2 pagamentos python -m app.deploy status
```

### Diagnóstico passo a passo (Grafana → Explore → Loki)

Primeira vez no Explore? Veja o passo a passo em [`docs/EXPLORE.md`](docs/EXPLORE.md).

1. **Detecção** — no painel, "Erros (último minuto)" fica vermelho, "Falha no checkout" sobe para ~15 % e
   uma linha laranja "Deploy" marca o momento da troca de versão.
2. **Pela reclamação da usuária:**
   ```logql
   {service=~".+"} | json | user_id="maria" | level="error"
   ```
3. **Pelo código de suporte (trace_id) — a requisição inteira, em todos os serviços:**
   ```logql
   {service=~".+"} | trace_id="<código>" | json
   ```
   (ou clique no link **"Ver esta requisição em todos os serviços"** no detalhe de qualquer linha)
4. **Causa** — a linha de `pagamentos` traz `error_type=ValueError`, `version=1.4.1` e o stack trace.
5. **Confirmação: é só uma réplica?**
   ```logql
   sum by (container, version) (count_over_time({level="error"} | json [5m]))
   ```
   Todos os erros vêm de `observabilidade-logs-pagamentos-2`, versão `1.4.1`.

### Outras consultas úteis

```logql
# Taxa de linhas por serviço e nível
sum by (service, level) (rate({service=~".+"}[1m]))

# Latência p95 do checkout calculada a partir dos logs
quantile_over_time(0.95, {service="gateway"} |= "requisição concluída" | json | unwrap duracao_ms | __error__="" [1m]) by (service)

# Usuários mais afetados por erros
topk(5, sum by (user_id) (count_over_time({level="error"} | json | user_id!="" [15m])))
```

### O "antes": logs em texto livre

```bash
LOG_FORMAT=texto docker compose up -d     # mesmos serviços, logs sem estrutura e sem IDs
./scripts/grep-antes.sh
LOG_FORMAT=json docker compose up -d      # volta ao normal
```

---

## Medindo volume e custo no Loki

```bash
# bytes e linhas recebidos pelo Loki desde que subiu
curl -s localhost:3100/metrics | grep -E "loki_distributor_(bytes|lines)_received_total"
# quantidade de streams (séries) ativas
curl -s localhost:3100/metrics | grep loki_ingester_memory_streams
```

No Grafana, a consulta `sum by (service) (bytes_over_time({service=~".+"}[1h]))` mostra quanto
cada serviço "custa" em volume.

---

## Ferramentas e versões

| Componente | Versão | Papel |
|---|---|---|
| Python + FastAPI | 3.12 / 0.115 | serviços da aplicação |
| Grafana Alloy | v1.9.0 | coleta e processamento dos logs |
| Grafana Loki | 3.5.0 | armazenamento e consulta (LogQL) |
| Grafana | 12.0.0 | visualização |

Todas gratuitas e de código aberto; o conjunto roda em notebook comum (~1,5 GB de RAM).

## Uso de IA generativa

Declarado no relatório, conforme as regras do seminário.
