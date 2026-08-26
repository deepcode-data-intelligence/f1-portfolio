# F1 Portfolio — Bases do Projeto

> Repositório público: https://github.com/rodrigolmanso/f1-portifolio (README em inglês apresenta a plataforma; este documento é a base de planejamento em PT).
> Página da solução no site: https://deepcode.com.br/f1/

> Documento interno de fundação (PT). Os repositórios públicos serão em inglês.
> Status: fase de preparação — nenhum código escrito ainda.

## Visão

Portfólio público no GitHub (`github.com/rodrigolmanso`) que demonstra, com tema F1, as competências que o currículo afirma: **Data Engineering, IA aplicada/RAG, dashboards de telemetria, ML e sistemas de dados industriais**. Os cases não são projetos isolados — formam uma **plataforma integrada**, contando uma história de arquitetura de ponta a ponta:

```
                    ┌────────────────────┐
   Jolpica API ───▶ │  f1-data-platform   │──▶ f1.duckdb (história 1950–hoje)
   (história)       │  (Python ETL)       │         │
                    └────────────────────┘         ├──▶ f1-history-agent (RAG + tools + /stats API)
                                                   │        └──▶ f1-mobile (Flutter, fase 2)
                                                   └──▶ f1-strategy-ml (fase 2)
                    ┌────────────────────┐
   FastF1 ────────▶ │  f1-pims            │──▶ Parquet time-series (telemetria)
   (telemetria)     │  (Rust historian)   │         │
                    └────────────────────┘         └──▶ f1-telemetry-lab (dashboards)
```

## Os 5 cases

### 1. `f1-data-platform` — Data Engineering (Python)
ETL da história completa da F1 (Jolpica-F1 API, sucessora da Ergast) → camadas raw/staging/marts em **DuckDB + Parquet**. Testes de qualidade de dados, idempotência, rate-limiting respeitado (500 req/h → backfill completo roda em background ~2h; incremental depois é barato). Escopo de entidades: seasons, races, drivers, constructors, results, standings (laptimes/pitstops ficam com o PIMS/FastF1).

### 2. `f1-pims` — Historian básico em Rust + Parquet ⭐ NOVO
Um **PIMS (Process Information Management System) minimalista**, inspirado na arquitetura de historians industriais (AVEVA PI), aplicado a telemetria de F1:

- **Modelo de dados**: tags (ex.: `VER.speed`, `VER.throttle`, `HAM.brake`) × séries temporais (timestamp, valor, qualidade) — o modelo clássico de historian.
- **Ingestão**: (a) importador de sessões FastF1 (batch, via export intermediário); (b) endpoint de ingestão streaming (simulando "tempo real" com replay de sessão) — mostra o caminho OT→armazenamento.
- **Armazenamento**: **Parquet particionado** (sessão/tag/janela temporal) escrito via `arrow-rs`/`parquet` crates — colunar, compressão nativa, legível por qualquer engine (DuckDB, pandas, Spark).
- **Compressão de historian**: implementação do algoritmo de **swinging door** (exception/compression deviation — o mesmo conceito do PI Server) com taxa de compressão reportada. É O diferencial técnico do case: pouquíssima gente fora do mundo industrial conhece.
- **Query API**: HTTP (axum) — busca por tag + intervalo, downsampling/agregações (avg/min/max por janela), interpolação. Consumida pelo case 3.
- **Por que Rust**: performance/latência previsível para escrita contínua de séries temporais + segurança de memória — e adiciona Rust ao portfólio sem sair do domínio que ele domina.

### 3. `f1-telemetry-lab` — Dashboards comparativos (Python/Streamlit)
Painéis estilo PI Vision: piloto vs piloto por volta (velocidade/acelerador/freio por distância), gaps, degradação por stint, posições. **Consome a Query API do `f1-pims`** (com fallback FastF1 direto) — o que transforma dois cases em uma arquitetura integrada. Deploy no Streamlit Community Cloud.

### 4. `f1-history-agent` — RAG + Agente headless (Python/FastAPI)
API interna (`POST /ask`) híbrida: **tool-calling → SQL** no DuckDB do case 1 para fatos exatos + **RAG** (Wikipedia, embeddings locais, vector store leve) para narrativa. Inferência plugável: `LLMBackend` com `ClaudeHeadlessBackend` (`claude -p`, sem custo de API) e `InternalAPIBackend` (a API interna que o Rodrigo criará). Eval automatizado com ~50 pares pergunta/resposta-ouro. Carregar o skill `claude-api` antes de codar esta parte.

### 5. `f1-strategy-ml` — ML de estratégia (fase 2)
Degradação de pneu/janela de pit com dados dos cases 1 e 2. Só após os quatro primeiros publicados.

### 6. `f1-mobile` — App Android/iOS em Flutter ⭐ NOVO
Aplicativo multiplataforma (**Flutter/Dart**) que permite interagir com a base de dados da plataforma pelo celular:

- **Consulta em linguagem natural**: tela de chat que consome a API do `f1-history-agent` (`POST /ask`) — o agente RAG no bolso.
- **Explorador de estatísticas**: navegação por temporadas, pilotos, construtores e resultados — consome uma **API REST de estatísticas** (endpoints read-only sobre o DuckDB do case 1, expostos pelo mesmo serviço FastAPI do agente, ex.: `GET /seasons/{year}/results`).
- **Telemetria**: gráficos comparativos simples (velocidade por distância) consumindo a Query API do `f1-pims`.
- **Offline-first**: cache local (SQLite/drift) das consultas recentes — padrão mobile maduro.
- Arquitetura no app: camadas UI → state (Riverpod ou Bloc) → repositories → API clients; tema escuro DeepCode.
- **Por que**: adiciona mobile ao portfólio e prova que a plataforma é consumível por qualquer cliente — a API interna vira contrato público.

> Implicação de arquitetura: o serviço do case 4 passa a ser o **gateway da plataforma** (endpoints `/ask` + `/stats/*`), consumido por site, app e terceiros.

## Ordem de execução (revisada)

| # | Case | Motivo da ordem |
|---|------|-----------------|
| 1 | `f1-data-platform` | Fundação de dados; backfill demorado roda em background |
| 2 | `f1-pims` (Rust) | Fundação de telemetria; o case mais diferenciado |
| 3 | `f1-telemetry-lab` | Consome o PIMS — prova a integração |
| 4 | `f1-history-agent` | Consome o DuckDB; fecha o ciclo IA |
| 5 | `f1-strategy-ml` | Fase 2 |
| 6 | `f1-mobile` (Flutter) | Fase 2 — consome as APIs estabilizadas dos cases 2 e 4 |

## Padrões comuns a todos os repos

- Inglês; README com narrativa de case (problema → arquitetura com diagrama → como rodar → demo/screenshots); LICENSE MIT; CI GitHub Actions (testes + lint); disclaimer "unofficial, not affiliated with Formula 1"; atribuição de fontes (Jolpica CC, FastF1 MIT, Wikipedia CC BY-SA).
- Commits com identidade `rodrigo@deepcode.com.br`.
- Python: gerenciado com `uv` (⚠️ ainda não instalado; Python do sistema é 3.9 — uv instala 3.12+). Rust: toolchain via `rustup` (verificar se instalado).
- Cross-link entre os repos e com deepcode.com.br; ao final, README de perfil do GitHub apresentando a plataforma.

## Decisões em aberto (confirmar antes de codar)

1. **Nome do PIMS**: `f1-pims` é descritivo; alternativa com marca própria (ex.: `chicane` — "historian de telemetria em Rust") é mais memorável como projeto open source. 
2. **Escopo do streaming** no PIMS: replay de sessão via WebSocket/HTTP chunked basta para o case, ou fica batch-only na v1?
3. **Swinging door** na v1 ou v1.1? (Recomendo v1 — é o coração do case.)
4. Dashboard consome PIMS via HTTP (recomendo) ou lê Parquet direto?

## Pré-requisitos de ferramenta (instalar quando começarmos a codar)

- `uv` (Python 3.12+), `rustup`/`cargo`, verificação do `gh` (ok — logado como rodrigolmanso).
