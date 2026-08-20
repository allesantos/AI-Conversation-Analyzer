# Desenvolvimento

Ambiente local conforme ADR-015 e ADR-016: apenas PostgreSQL e Redis no Docker; API, worker e Angular no Windows nativo. **Nenhuma porta padrão** (5432, 6379, 8000, 4200, 5050) é usada no host.

## Mapa de portas (host)

| Serviço | Porta host | Evita conflito com |
|---------|------------|--------------------|
| PostgreSQL (aca-postgres) | **55432** | `[other-local-service]` em 5432, `[other-local-service]` em 5433 |
| Redis (aca-redis) | **56379** | Redis já publicado em 6379 |
| FastAPI | **18000** | `[other-local-service]` em 8000, xflix em 8787 |
| Angular | **14200** | Porta padrão 4200 do `ng serve` |
| pgAdmin (opcional) | **15050** | UDP 5050 já em uso no host |

Credenciais do Postgres deste projeto: user/senha/db = `aca`. Isolamento real é pela **porta**.

## Requisitos

| Ferramenta | Versão |
|------------|--------|
| Python | 3.12+ (`uv python install 3.12`) |
| uv | 0.11+ |
| Node.js | 20+ |
| npm | 10+ |
| Docker Desktop | 24+ |

Não instale PostgreSQL nem Redis no Windows. Use os containers.

## Atalho na área de trabalho

| Atalho | Função |
|--------|--------|
| `AI Conversation Analyzer.bat` | Sobe tudo e abre o navegador em `/login` |
| `AI Conversation Analyzer - Parar.bat` | Encerra API (18000), worker e frontend (14200) |

Scripts canônicos no repositório:

- `scripts/dev-windows/start-dev.bat`
- `scripts/dev-windows/stop-dev.bat`
- `scripts/dev-windows/open-dev-browser.ps1`

## 1. Subir os bancos

```powershell
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
```

pgAdmin opcional:

```powershell
docker compose -f docker/docker-compose.yml --profile tools up -d
```

Interface em http://localhost:15050 (`admin@local.dev` / `admin`).

## 2. Configuração

```powershell
copy .env.example .env
```

Preencher:

- `OPENAI_API_KEY` — necessário para análise, perguntas, sugestões e transcrição
- `JWT_SECRET` — alterar antes de qualquer uso além de dev local

## 3. Backend

```powershell
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 18000
```

OpenAPI: http://localhost:18000/docs

### Worker ARQ

Em outro terminal:

```powershell
cd backend
uv run arq app.workers.settings.WorkerSettings
```

O worker processa: geração de embeddings (`generate_embeddings`) e transcrição de áudio (`generate_transcription`).

## 4. Frontend

```powershell
cd frontend
npm install
npm start
```

SPA em http://localhost:14200, consome `http://localhost:18000/api/v1`. CORS habilitado para a origem 14200.

## 5. Qualidade

```powershell
# Backend
cd backend
uv run pytest
uv run ruff check .
uv run ruff format .

# Frontend
cd frontend
npm run lint
npm run build
```

Testes do backend usam SQLite em memória e não exigem Docker.

## Estrutura do projeto

```
backend/app/
  api/v1/          auth, conversations, usage
  ai/              llm, embeddings, transcription, rag, prompts
  auth/            hash de senha
  conversation/    parser WhatsApp, chunker, métricas, context builder
  core/            config, db, logging, JWT, middleware, rate limiting
  interest_engine/ sinais, reciprocidade, score, evidências, timeline
  models/          User, Conversation, Message, Participant, ConversationAnalysis,
                   AnalysisEvidence, MessageEmbedding, ConversationEmbeddingJob,
                   EmbeddingUsageRecord, AudioTranscription, ResponseSuggestion, AIUsage
  repositories/
  response_engine/ geração de sugestões de resposta
  services/        analysis, conversation, embedding, transcription, usage
  workers/         ARQ (embeddings, transcription)
frontend/src/app/
  core/            auth, interceptor, guard, models, services
  features/        login, register, dashboard, conversations, usage
  shared/          shell, signal-pulse
docker/            postgres + redis
docs/              ARCHITECTURE, DECISIONS, THIRD_PARTY, DEVELOPMENT, API
```

## Observabilidade

- Structured logging (JSON) com request ID, método, path, status e duração
- `X-Request-ID` propagado em todas as requisições
- Logs **nunca** incluem conteúdo de mensagens (privacidade)
- Job status trackado (PENDING → PROCESSING → COMPLETED/FAILED)

## Segurança

- Autenticação via JWT em todos os endpoints protegidos
- Isolamento por `user_id` em todas as queries de conversa/análise
- Validação de upload: tipo, extensão e tamanho máximo (50MB)
- Secrets via `.env` (nunca commitados)
- Rate limiting (token bucket, 5 req/burst, ~12/min) nos endpoints de IA
- `DELETE /conversations/{id}` remove todos os dados derivados em cascade

## Privacidade

- Logs **não** incluem corpo de requisição nem conteúdo de mensagens
- Conversas isoladas por `user_id`
- Áudio armazenado em filesystem local (não versionado)
- Exclusão completa via DELETE (conversa, mensagens, análises, embeddings, áudio, sugestões)

## Cache de análise e custo de LLM

O backend evita chamadas desnecessárias à OpenAI comparando um **fingerprint semântico** do conteúdo analisável (`timestamp`, tipo, nome do remetente, texto). IDs de mensagem e participante **não** entram no hash — isso permite reimportar o mesmo `.txt` (com novos UUIDs) sem invalidar o resumo.

Implementação principal:

- `backend/app/conversation/analysis_fingerprint.py` — `compute_analysis_fingerprint()`
- `AnalysisService.analyze()` — retorna cache quando `llm_content_fingerprint` coincide e `summary_stale=false`
- `AnalysisService.refresh_derived_analysis()` — recalcula Interest Engine localmente (métricas, sinais, evidências) sem LLM
- `AnalysisService.reconcile_after_import()` — chamado após `POST /import`; remapeia evidências e preserva resumo se o conteúdo for idêntico

Fingerprints persistidos em `ConversationAnalysis.metrics`:

- `content_fingerprint` — estado atual da conversa
- `llm_content_fingerprint` — fingerprint na última execução com LLM
- `summary_stale` — resumo textual desatualizado em relação ao conteúdo atual

Testes relacionados: `tests/test_analysis_fingerprint.py`, `test_analyze_returns_cache_when_data_unchanged`, `test_reimport_same_txt_reuses_llm_cache` em `tests/test_analysis.py`.

## Troubleshooting

**Alembic não conecta:** confira se `aca-postgres` está healthy (`docker ps`) e se `DATABASE_URL` usa `localhost:55432`.

**CORS no browser:** frontend deve estar em `http://localhost:14200` e `CORS_ORIGINS` deve incluir essa origem.

**API em outra porta:** o comando padrão é `--port 18000`. Se mudar, atualize `frontend/src/environments/environment.ts` e `CORS_ORIGINS`.

**Atalho não sobe:** Docker Desktop precisa estar aberto. O script usa as portas 55432/56379/18000/14200.

**Análise retorna 202:** embeddings estão sendo gerados em background. Aguarde alguns segundos e tente novamente (o frontend faz polling automático).

**Rate limiting (429):** endpoints de IA têm limite de ~5 requisições em rajada. Aguarde alguns segundos.

**Transcrição falha:** verifique se `OPENAI_API_KEY` está configurada e se o worker ARQ está rodando.

**OPENAI_API_KEY:** necessária para análise, perguntas, sugestões e transcrição. Sem ela, apenas importação e visualização funcionam. Nos testes, um FakeLLMProvider substitui a API real.

**Reanalisar parece “não fazer nada”:** se o conteúdo não mudou, a resposta vem do cache (`from_cache: true`) e não há novo consumo em `/usage`. Isso é esperado.

**Reimportei o `.txt` e o resumo sumiu:** a reconciliação no import preserva a análise quando o conteúdo é idêntico. Se o arquivo tiver diferenças (mesmo que pequenas), `summary_stale` fica `true` — clique em Reanalisar para gerar um resumo novo (1 chamada LLM).

**Análise antiga sempre gasta LLM:** conversas analisadas antes do fingerprint semântico podem precisar de uma reanálise única para gravar o novo formato; depois disso o cache funciona normalmente.
