# Como usar o Explore do Grafana (para a demo)

O **Explore** é a tela do Grafana para fazer consultas livres, sem montar painel.
Na demo ele serve para os passos 7 a 10: achar os erros da Maria, abrir a requisição dela inteira e ver a causa.

> **Atalho:** se o Explore der problema na hora, o próprio painel resolve. Cole `maria` ou o código de suporte
> na caixa **"Buscar"** no topo do painel e role até o painel de logs.

---

## 1. Abrir e preparar (antes da apresentação)

1. Abra http://localhost:3000.
2. No menu da esquerda, clique em **Explore** (ícone de bússola).
3. No topo, à esquerda, confira que a fonte de dados é **Loki**. Se não for, clique e escolha Loki.
4. No topo, à direita, deixe o período em **Last 15 minutes**.
5. Na caixa da consulta, à direita, há duas abas: **Builder** e **Code**. Clique em **Code**.
   - Builder monta a consulta com menus; Code deixa colar o texto. Na demo, use sempre **Code**.
6. Deixe essa aba aberta no navegador.

## 2. Rodar uma consulta

1. Clique na caixa de texto da consulta e apague o que tiver nela.
2. Cole a consulta (exemplos abaixo).
3. Clique no botão azul **Run query** (canto superior direito), ou aperte **Shift + Enter**.

O resultado aparece embaixo, em duas partes:

- **Logs volume** (gráfico de barras): quantas linhas por momento, coloridas por nível.
- **Lista de logs**: uma linha por evento, a mais nova em cima.

## 3. As quatro consultas da demo

**Passo 7 — os erros da Maria**

```logql
{service=~".+"} | json | user_id="maria" | level="error"
```

Leitura: `{service=~".+"}` = todos os serviços; `| json` = abre o JSON de cada linha; o resto filtra pelos campos.

**Passo 8 — a requisição inteira, pelo código de suporte**

Copie o `codigo_suporte` que o `./scripts/cliente.sh` mostrou e cole no lugar de `COLE_AQUI`:

```logql
{service=~".+"} | trace_id="COLE_AQUI" | json
```

Aparecem umas 14 linhas de 4 serviços. Para ler na ordem em que aconteceram, mude a ordenação para
**Oldest first** (nas opções acima da lista de logs).

**Passo 9 — ver a causa**

Na lista, clique na linha **vermelha** de `pagamentos`. Ela se expande e mostra os campos:
`version: 1.4.1`, `cupom`, `error_type: ValueError`, `error_message` e `stack_trace`.

No fim dos campos há um link no `trace_id`: **"Ver esta requisição em todos os serviços"**.
Ele faz o mesmo que a consulta do passo 8, com um clique.

**Passo 10 — confirmar que é uma réplica só**

```logql
sum by (container, version) (count_over_time({level="error"} | json [5m]))
```

Esta consulta devolve números em vez de linhas. Se aparecer gráfico, troque para **Table** no seletor de
visualização. Lá estão `gateway-1`, `pedidos-1` e `pagamentos-2` (versão 1.4.1), nunca `pagamentos-1`.

---

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| "No logs found" | O período está curto, ou o `trace_id` foi colado com aspas ou espaço a mais. Aumente para *Last 30 minutes* e confira o código. |
| A consulta aparece em menus, não em texto | Você está no modo **Builder**. Clique em **Code**. |
| Erro "parse error" | Falta uma aspa ou uma chave `}`. Copie a consulta de novo deste arquivo. |
| Não aparece nada de lugar nenhum | Rode `docker compose ps`: `loki`, `alloy` e `grafana` precisam estar *running*. |

## Por que as barras não "somem" depois do rollback

Os gráficos mostram o histórico dos últimos 15 minutos. Depois do `./scripts/falha.sh desliga`, as barras
antigas **continuam lá**: são o registro do incidente. O sinal de que o rollback funcionou é outro:

- nenhuma barra nova aparece à direita da segunda linha laranja "Deploy";
- "Erros (último minuto)" volta a 0 em cerca de 1 minuto;
- `./scripts/falha.sh status` mostra as duas réplicas na versão 1.4.0.
