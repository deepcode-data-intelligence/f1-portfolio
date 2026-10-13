# F1 Portfolio — Bases do Projeto

> Repositório público (monorepo): https://github.com/rodrigolmanso/f1-portifolio — cada case é uma subpasta. README em inglês apresenta a plataforma; este documento é a base de planejamento em PT.
> Página da solução no site: https://deepcode.com.br/f1/

> Documento interno de fundação (PT). Os repositórios públicos serão em inglês.
> Status: scaffold concluído em 2026-10-12 (estrutura, CI, Docker e smoke tests de todos os cases). Implementação começa pelo case 1.

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
   FastF1 ────────▶ │  box-box            │──▶ Parquet time-series (telemetria)
   (telemetria)     │  (Rust historian)   │         │
                    └────────────────────┘         └──▶ f1-telemetry-lab (dashboards)
```

## Os 5 cases

### 1. `f1-data-platform` — Data Engineering (Python)
ETL da história completa da F1 (Jolpica-F1 API, sucessora da Ergast) → camadas raw/staging/marts em **DuckDB + Parquet**. Testes de qualidade de dados, idempotência, rate-limiting respeitado (500 req/h → backfill completo roda em background ~2h; incremental depois é barato). Escopo de entidades: seasons, races, drivers, constructors, results, standings (laptimes/pitstops ficam com o PIMS/FastF1).

### 2. `box-box` — Historian básico em Rust + Parquet ⭐ NOVO
*("Box, box": o chamado de rádio para o pit stop — o carro entra, o dado sai.)*
Um **PIMS (Process Information Management System) minimalista**, inspirado na arquitetura de historians industriais (AVEVA PI), aplicado a telemetria de F1:

- **Modelo de dados**: tags (ex.: `VER.speed`, `VER.throttle`, `HAM.brake`) × séries temporais (timestamp, valor, qualidade) — o modelo clássico de historian.
- **Ingestão**: (a) importador de sessões FastF1 (batch, via export intermediário); (b) endpoint de ingestão streaming (simulando "tempo real" com replay de sessão) — mostra o caminho OT→armazenamento.
- **Armazenamento**: **Parquet particionado** (sessão/tag/janela temporal) escrito via `arrow-rs`/`parquet` crates — colunar, compressão nativa, legível por qualquer engine (DuckDB, pandas, Spark).
- **Compressão de historian**: implementação do algoritmo de **swinging door** (exception/compression deviation — o mesmo conceito do PI Server) com taxa de compressão reportada. É O diferencial técnico do case: pouquíssima gente fora do mundo industrial conhece.
- **Query API**: HTTP (axum) — busca por tag + intervalo, downsampling/agregações (avg/min/max por janela), interpolação. Consumida pelo case 3.
- **Por que Rust**: performance/latência previsível para escrita contínua de séries temporais + segurança de memória — e adiciona Rust ao portfólio sem sair do domínio que ele domina.

### 3. `f1-telemetry-lab` — Dashboards comparativos (Python/Streamlit)
Painéis estilo PI Vision: piloto vs piloto por volta (velocidade/acelerador/freio por distância), gaps, degradação por stint, posições. **Consome a Query API do `box-box`** (com fallback FastF1 direto) — o que transforma dois cases em uma arquitetura integrada. Deploy no Streamlit Community Cloud.

### 4. `f1-history-agent` — RAG + Agente headless (Python/FastAPI)
API interna (`POST /ask`) híbrida: **tool-calling → SQL** no DuckDB do case 1 para fatos exatos + **RAG** (Wikipedia, embeddings locais, vector store leve) para narrativa. Inferência plugável: `LLMBackend` com `ClaudeHeadlessBackend` (`claude -p`, sem custo de API) e `InternalAPIBackend` (a API interna que o Rodrigo criará). Eval automatizado com ~50 pares pergunta/resposta-ouro. Carregar o skill `claude-api` antes de codar esta parte.

### 5. `f1-strategy-ml` — ML de estratégia (fase 2)
Degradação de pneu/janela de pit com dados dos cases 1 e 2. Só após os quatro primeiros publicados.

### 6. `f1-mobile` — App Android/iOS em Flutter ⭐ NOVO
Aplicativo multiplataforma (**Flutter/Dart**) que permite interagir com a base de dados da plataforma pelo celular:

- **Consulta em linguagem natural**: tela de chat que consome a API do `f1-history-agent` (`POST /ask`) — o agente RAG no bolso.
- **Explorador de estatísticas**: navegação por temporadas, pilotos, construtores e resultados — consome uma **API REST de estatísticas** (endpoints read-only sobre o DuckDB do case 1, expostos pelo mesmo serviço FastAPI do agente, ex.: `GET /seasons/{year}/results`).
- **Telemetria**: gráficos comparativos simples (velocidade por distância) consumindo a Query API do `box-box`.
- **Offline-first**: cache local (SQLite/drift) das consultas recentes — padrão mobile maduro.
- Arquitetura no app: camadas UI → state (Riverpod ou Bloc) → repositories → API clients; tema escuro DeepCode.
- **Por que**: adiciona mobile ao portfólio e prova que a plataforma é consumível por qualquer cliente — a API interna vira contrato público.

> Implicação de arquitetura: o serviço do case 4 passa a ser o **gateway da plataforma** (endpoints `/ask` + `/stats/*`), consumido por site, app e terceiros.

## Ordem de execução (revisada)

| # | Case | Motivo da ordem |
|---|------|-----------------|
| 1 | `f1-data-platform` | Fundação de dados; backfill demorado roda em background |
| 2 | `box-box` (Rust) | Fundação de telemetria; o case mais diferenciado |
| 3 | `f1-telemetry-lab` | Consome o PIMS — prova a integração |
| 4 | `f1-history-agent` | Consome o DuckDB; fecha o ciclo IA |
| 5 | `f1-strategy-ml` | Fase 2 |
| 6 | `f1-mobile` (Flutter) | Fase 2 — consome as APIs estabilizadas dos cases 2 e 4 |

## Padrões comuns a todos os repos

- Inglês; README com narrativa de case (problema → arquitetura com diagrama → como rodar → demo/screenshots); LICENSE MIT; CI GitHub Actions (testes + lint); disclaimer "unofficial, not affiliated with Formula 1"; atribuição de fontes (Jolpica CC, FastF1 MIT, Wikipedia CC BY-SA).
- **Docker/Docker Compose como requisito para subir o projeto**: todo case executável (serviços, ETL, dashboards) publica `Dockerfile` + `docker-compose.yml`, e `docker compose up` é o caminho canônico de execução documentado no README — quem clona não precisa de uv/rustup/Flutter instalados para rodar (toolchains locais ficam como opção para desenvolvimento). Exceção: `f1-mobile` (app Flutter) — o build do app é nativo, mas os serviços que ele consome sobem via compose.
- Commits com identidade `rodrigo@deepcode.com.br`. **Mensagens de commit e PRs NUNCA incluem co-autoria ou atribuição ao Claude** (sem `Co-Authored-By`, sem "Generated with Claude Code").
- Python: gerenciado com `uv` (Python 3.12 fixado em `.python-version` de cada case; `ruff` + `pytest`). Rust: toolchain estável via `rustup`, `cargo fmt` + `clippy -D warnings`.
- Cross-link entre os repos e com deepcode.com.br; ao final, README de perfil do GitHub apresentando a plataforma.

## Decisões tomadas (2026-10-12)

1. **Estrutura**: monorepo `f1-portfolio`, um diretório por case (não repos separados). CI com filtro por path; `docker-compose.yml` único na raiz.
2. **Nome do PIMS**: `box-box` (crate `boxbox`, binário `box-box`).
3. **Escopo v1 do box-box**: swinging door **na v1** + ingestão streaming/replay de sessão **na v1** + Query API HTTP.
4. **Dashboard consome o box-box via HTTP** (fallback FastF1 direto), não lê Parquet direto.
5. **Ordem de trabalho**: scaffold de todos os cases primeiro (feito), depois implementação na ordem da tabela acima.

## Pré-requisitos de ferramenta (instalar quando começarmos a codar)

- **Docker + Docker Compose** (⚠️ ainda não instalado nesta máquina — Docker Desktop ou OrbStack/colima; requisito para subir qualquer case).
- `uv` (✅ instalado via brew, Python 3.12 por projeto), `rustup`/`cargo` (✅ 1.98 + rustfmt/clippy), `gh` (✅ logado como rodrigolmanso) — apenas para desenvolvimento local fora dos containers.
