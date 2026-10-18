# Roteiro da apresentação — Tema 3: Logs estruturados e centralizados

**Duração:** 25 min de apresentação (mínimo 8 min de demo) + 10 min de perguntas.
**Limite absoluto:** 30 min (acima disso, −0,5 ponto). Ensaiem com cronômetro.

| Bloco | Tempo | Quem | Slides |
|---|---|---|---|
| 1. Problema | 3 min | Alana | 1–3 |
| 2. Fundamentação teórica | 6 min | Alana (3) + Pedro (3) | 4–8 |
| 3. Arquitetura da solução | 3 min | Pedro | 9 |
| 4. Demonstração | 9 min | Pedro (3) + Chrystian (6) | 10 |
| 5. Análise crítica | 4 min | Chrystian (2) + Alana (2) | 11–13 |
| Referências + fechamento | — | Alana | 14–15 |

Cada um fala ~8 min. O professor faz ao menos uma pergunta a cada integrante, então
**todos precisam saber o trabalho inteiro** — use a seção "Perguntas prováveis" para treinar.

---

## Antes de entrar na sala (checklist)

- [ ] `docker compose up -d --build` rodado **pelo menos 5 min antes** (as imagens já baixadas na véspera).
- [ ] Grafana aberto em http://localhost:3000, painel "Loja — Logs centralizados", janela "últimos 15 min".
- [ ] Uma aba do Grafana em **Explore**, fonte Loki, modo **Code** (ver `docs/EXPLORE.md`).
- [ ] `./scripts/falha.sh status` mostrando as duas réplicas em 1.4.0.
- [ ] Um terminal na pasta do repositório, fonte grande (zoom ≥ 150%).
- [ ] `./scripts/falha.sh desliga` executado (estado normal garantido).
- [ ] Vídeo do plano B (até 5 min) aberto em outra aba, pronto para tocar.
- [ ] Notebook na tomada, notificações desligadas.

---

## Bloco 1 — Problema (Alana, 3 min)

**Slide 1 — Capa.** Apresentar a equipe e o tema.

**Slide 2 — O cenário.**
> "Imagine uma loja online com quatro serviços: gateway, pedidos, estoque e pagamentos, e
> pagamentos roda em duas réplicas. A Maria liga no suporte: *'minha compra deu erro'*. Ela não sabe
> em qual serviço, nem a hora exata. Hoje, cada serviço escreve log em texto livre no próprio
> contêiner. Para investigar, alguém precisa entrar em cada máquina e rodar `grep`."

**Slide 3 — Por que é difícil em sistemas distribuídos.**
- Em um monólito, uma requisição = um processo = um arquivo de log, em ordem.
- Aqui, uma compra gera **~14 linhas em 4 serviços e 5 contêineres**, intercaladas com centenas de outras compras.
- Nada liga a linha "erro 502" do gateway à exceção real dentro de pagamentos.
- Contêineres são efêmeros: se o contêiner for recriado, o log local some.
- Relógios diferentes e réplicas tornam a ordem cronológica ambígua.

> "O problema não é ter pouco log — é não conseguir **juntar** os pedaços."

---

## Bloco 2 — Fundamentação teórica (6 min)

### Alana (3 min) — slides 4 e 5

**Slide 4 — Log estruturado.**
- Log = evento discreto com carimbo de tempo. Texto livre é feito para humanos lerem uma linha;
  estruturado (JSON) é feito para máquinas filtrarem milhões.
- Campos fixos em todo log: `ts`, `level`, `service`, `version`, `msg`, `trace_id`, `user_id`.
- Níveis com significado: `info` (fluxo normal), `warn` (anormal mas esperado, ex.: produto inexistente),
  `error` (exige ação). Se tudo é `error`, nada é.
- Mensagem estável ("pagamento aprovado") + dados em campos (`valor_total: 199.9`), não interpolados no texto.

**Slide 5 — Correlação.**
- O gateway gera um ID por requisição e o envia adiante no cabeçalho `traceparent`
  (padrão **W3C Trace Context**, o mesmo usado pelo OpenTelemetry).
- Cada serviço coloca esse ID no contexto (`contextvars`) — todo log sai com ele automaticamente.
- Ao cliente, devolvemos o mesmo ID como "código de suporte".
- Ligação com o Tema 1: é o mesmo `trace_id` que um sistema de tracing usaria; aqui o usamos para costurar logs.

### Pedro (3 min) — slides 6, 7 e 8

**Slide 6 — Centralização: coletar, guardar, consultar.**
- Os serviços só escrevem no **stdout** (12-Factor App: "logs são fluxos de eventos"). Quem coleta é a plataforma.
- Coletor (Alloy) → armazenamento (Loki) → consulta (Grafana / LogQL).

**Slide 7 — Rótulos vs conteúdo (a decisão central).**
- O Loki indexa **só os rótulos**. Cada combinação de rótulos = um *stream*.
- Rótulos de baixa cardinalidade: `service`, `container`, `level` → ~15 streams.
- Se `trace_id` fosse rótulo: um stream por requisição → a 4 req/s, **14.400 streams novos por hora**.
- Conteúdo (`user_id`, `trace_id`) é filtrado na consulta: `| json | user_id="maria"`.
- Contraste com Elasticsearch/OpenSearch: índice invertido de todo o texto — busca mais rápida
  e flexível, armazenamento e memória muito maiores.

**Slide 8 — Volume e retenção.**
- JSON é ~6,5× maior que texto livre por linha (326 B vs 50 B, medido).
- Compressão em chunks (snappy) reduz ~6×; retenção configurada em 72 h.
- Amostragem e níveis: `info` de health check não precisa ser guardado.

---

## Bloco 3 — Arquitetura (Pedro, 3 min) — slide 9

Mostrar o diagrama e seguir o caminho de **uma linha de log**:
1. `pagamentos` escreve um JSON no stdout.
2. O Docker guarda no `json-file` do contêiner.
3. O Alloy descobre o contêiner pelo socket do Docker (só os que têm o rótulo `observabilidade.logs=true`),
   adiciona `service` e `container`, lê o JSON, transforma `level` em rótulo e `trace_id` em metadado estruturado.
4. Envia ao Loki por HTTP (`/loki/api/v1/push`).
5. O Grafana consulta o Loki em LogQL.

> Opcional (se sobrar tempo): abrir http://localhost:12345 e mostrar o grafo do pipeline do Alloy.

---

## Bloco 4 — Demonstração (9 min) — slide 10 fica na tela como "mapa" da demo

Roteiro obrigatório: **estado normal → falha → detecção → diagnóstico → causa** (+ correção).

### Pedro — estado normal e falha (3 min)

1. **Estado normal** (painel do Grafana):
   > "O gerador de carga faz ~4 compras por segundo. Erros: zero. Falha no checkout: 0 %.
   > Latência p95 do checkout, calculada a partir dos próprios logs. Volume: ~55 linhas por segundo."
2. Rolar até o painel de logs e expandir uma linha: mostrar os campos JSON, o `trace_id` e o `user_id`.
3. **Provocar a falha** no terminal:
   ```bash
   ./scripts/falha.sh liga
   ```
   > "Acabamos de fazer um deploy da versão 1.4.1 de pagamentos — mas só em uma das duas réplicas,
   > como num deploy gradual. Não vamos dizer qual é o bug: vamos achá-lo pelos dados."
4. **A cliente reclama**:
   ```bash
   ./scripts/cliente.sh maria
   ```
   Ler em voz alta a resposta: *"Não foi possível concluir sua compra"* + `codigo_suporte`. Copiar o código.
5. **O "antes"** (30 s):
   ```bash
   ./scripts/grep-antes.sh
   ```
   > "Sem a solução: o gateway diz 'checkout falhou 502', pedidos diz 'cobrança falhou'. Qual réplica?
   > Qual pedido é o da Maria? Não dá para saber."

### Chrystian — detecção, diagnóstico e causa (6 min)

6. **Detecção** — voltar ao painel (refresh de 5 s): "Erros (último minuto)" ficou vermelho; "Falha no checkout"
   sobe para ~15 %. Nos gráficos aparece uma **linha vertical laranja "Deploy"** (anotação gerada pelo próprio
   log de troca de versão): as barras de erro começam logo depois dela.
   No gráfico "Erros por contêiner" aparecem 3 cores — gateway, pedidos e **pagamentos-2**. Pagamentos-1 não aparece.
   > "Gateway e pedidos erram em cascata, um por causa do outro. A pergunta é: onde a corrente começa?"
7. **Diagnóstico pela usuária** — Explore (passo a passo em `docs/EXPLORE.md`):
   ```logql
   {service=~".+"} | json | user_id="maria" | level="error"
   ```
   > "Erros da Maria em dois serviços: gateway e pagamentos. O gateway só sabe que recebeu um 502."
8. **Diagnóstico pelo código de suporte** — colar o código:
   ```logql
   {service=~".+"} | trace_id="COLE_O_CODIGO" | json
   ```
   Ordenar por tempo e narrar a história da requisição: gateway recebeu → pedidos criou → estoque reservou →
   pagamentos **ValueError** → pedidos desfez a reserva → gateway devolveu 502.
   Mostrar também o link clicável no `trace_id` (detalhe da linha → "Ver esta requisição em todos os serviços").
9. **Causa** — expandir a linha de erro de pagamentos:
   `error_type: ValueError`, `error_message: invalid literal for int() with base 10: '10%'`,
   `version: 1.4.1`, `cupom: BEMVINDO10`, e o `stack_trace` apontando `calcular_desconto`.
10. **Confirmar o raio de impacto** — tabela "Onde estão os erros" do painel ou:
    ```logql
    sum by (container, version) (count_over_time({level="error"} | json [5m]))
    ```
    > "Todos os erros vêm da réplica `pagamentos-2`, versão 1.4.1, e só em pedidos com cupom.
    > Causa: a migração da tabela de cupons mudou o percentual para texto."
11. **Correção** — rollback:
    ```bash
    ./scripts/falha.sh desliga
    ```
    O script mostra a versão de cada réplica (as duas em 1.4.0). No painel: surge a segunda anotação "Deploy"
    (v1.4.1 → v1.4.0) e **nenhuma barra nova à direita dela**. As barras antigas continuam no gráfico — é o
    histórico do incidente, não erro novo. "Erros (último minuto)" volta a 0 em cerca de 1 min.

> Frase de fechamento da demo: "Da reclamação à linha de código em menos de dois minutos,
> sem abrir nenhum terminal dentro dos contêineres."

---

## Bloco 5 — Análise crítica (4 min)

### Chrystian (2 min) — slides 11 e 12

**Slide 11 — Custos e overhead (com números medidos).**
- Volume: ~14 linhas e ~4,4 KB de log por compra; a 4 compras/s → ~1,5 GB/dia bruto, ~250 MB/dia comprimido.
- JSON custa ~6,5× mais bytes que texto livre e ~5 µs a mais de CPU por linha (6,5 µs vs 1,5 µs) —
  desprezível perto dos ~200 ms da requisição, relevante em serviços de altíssima vazão.
- Consulta por conteúdo (`| json | user_id=`) varre os chunks do período: barato em 15 min, caro em 30 dias.

**Slide 12 — Alternativas.**
| | Loki | Elasticsearch/OpenSearch |
|---|---|---|
| Índice | só rótulos | texto completo |
| Busca livre em período longo | lenta | rápida |
| Armazenamento/RAM | baixo | alto |
| Operação | simples | complexa (shards, mapeamentos) |

Coletor: Alloy vs Fluent Bit vs Promtail (Promtail está em fim de vida; o Alloy é o sucessor).

### Alana (2 min) — slide 13

**Slide 13 — Limitações e quando NÃO usar.**
- Logs mostram **o que aconteceu**, mas não **onde o tempo foi gasto** — para latência, tracing (Tema 1) é melhor.
- Para "quantos erros por minuto", métricas são mais baratas que contar linhas de log (Tema 2).
- Rótulos errados (alta cardinalidade) derrubam o Loki; exige disciplina do time.
- Dados pessoais em log (CPF, cartão) viram problema de LGPD — mascarar na origem.
- Um único Loki monolítico é ponto único de falha; produção exige modo distribuído e armazenamento em objeto (S3).
- Não vale a pena para um único serviço num único servidor: `journalctl` resolve.

**Slide 14 — Referências** (10 s, só mostrar).

**Slide 15 — Fechamento.**
> "Log estruturado + um ID que atravessa os serviços + um lugar central para consultar.
> Três ideias simples que transformam 'ssh e grep em cada máquina' numa consulta."

Abrir para perguntas.

---

## Plano B (se o ambiente falhar)

1. Não tentar consertar ao vivo por mais de 1 minuto.
2. Tocar o vídeo gravado (até 5 min) e narrar por cima, seguindo os mesmos passos 1–11.
3. Mostrar os slides de backup com capturas de tela de cada etapa.

**Gravar o vídeo:** com o OBS ou o gravador do sistema, executar a demo inteira uma vez, sem cortes,
em até 5 min. Fazer capturas de tela dos passos 6, 8, 9 e 10 para os slides de backup.

---

## Perguntas prováveis (todos devem saber responder)

**Por que não colocar `user_id` como rótulo, se vocês filtram por ele?**
Cada valor novo de rótulo cria um stream. Com milhares de usuários, o índice explode, os chunks ficam
pequenos e o Loki fica lento. Filtrar no conteúdo varre mais dados por consulta, mas mantém o índice pequeno.

**O que é metadado estruturado e por que usar para o `trace_id`?**
Recurso do Loki 3: pares chave‑valor guardados junto à linha, fora do índice de streams. Filtrar
`| trace_id="..."` não exige parsear o JSON, e não cria séries.

**Isso não é tracing?**
Não. Usamos o mesmo identificador padrão (W3C Trace Context), mas não medimos spans nem duração por etapa.
O tracing mostra o *caminho e o tempo*; o log mostra *o que aconteceu e por quê* (exceção, dados). Os dois se complementam
— e com o mesmo `trace_id` daria para pular de um para o outro (Tema 5).

**Por que o stdout e não um arquivo de log?**
Contêineres são efêmeros; o arquivo morre com eles. O stdout é capturado pelo runtime e o serviço não precisa
saber para onde os logs vão (12‑Factor).

**O que acontece se o Loki cair?**
O Alloy mantém uma fila e tenta reenviar (com limite). O Docker também guarda o log local do contêiner.
Se ficar fora muito tempo, perdem-se logs — por isso em produção o Loki roda replicado.

**Como garantir que todo serviço use o mesmo formato?**
Biblioteca de log compartilhada (aqui, `logging_setup.py`) e convenção de nomes de campos — as convenções
semânticas do OpenTelemetry são uma boa referência.

**Quanto custa?**
Ver slide 11. O custo cresce com o volume bruto (ingestão) e com o período de retenção (armazenamento).
Os maiores aliados: níveis bem usados, não logar health checks e retenção curta para `info`.

**Por que Loki e não Elasticsearch?**
Para o nosso caso (busca por usuário/ID numa janela curta de tempo), o índice só de rótulos é suficiente e
muito mais barato. Se a necessidade fosse busca textual livre em meses de log, o Elasticsearch seria melhor.

**Qual é o bug, exatamente?**
A versão 1.4.1 lê o percentual do cupom como texto ("10%") e faz `int("10%")`, que lança `ValueError`.
Só falha com cupom e só na réplica atualizada, por isso é intermitente (~15 % dos checkouts).

**Os logs são consistentes em ordem?**
Cada linha leva o horário do contêiner que a escreveu. Na mesma máquina, a ordem é confiável; entre máquinas,
diferenças de relógio podem inverter linhas próximas — por isso agrupamos pelo `trace_id`, não pela hora.
