# AI Conversation Analyzer

Plataforma SaaS para análise inteligente de conversas do WhatsApp. O diferencial é o **Interest & Reciprocity Engine**: métricas objetivas, sinais e evidências — não apenas "usar ChatGPT".

> Status: **Fase 8 — Refinamento** concluída. Todas as funcionalidades do MVP estão implementadas.

## Iniciar no Windows

Na área de trabalho:

- **AI Conversation Analyzer.bat** — sobe Docker (Postgres/Redis), API, worker e Angular, e abre o navegador
- **AI Conversation Analyzer - Parar.bat** — encerra API, worker e frontend (mantém os bancos no Docker)

Ou, na pasta do projeto:

```powershell
scripts\dev-windows\start-dev.bat
scripts\dev-windows\stop-dev.bat
```

| Serviço | URL |
|---------|-----|
| App | http://localhost:14200 |
| API / Swagger | http://127.0.0.1:18000/docs |

## Requisitos

- Windows 10/11
- Python 3.12+ com [uv](https://docs.astral.sh/uv/)
- Node.js 20+ e npm
- Docker Desktop (apenas PostgreSQL e Redis)

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Angular 20, TypeScript, RxJS, Angular Material |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Dados | PostgreSQL 16 + pgvector, Redis, ARQ |
| IA | LangChain, OpenAI (GPT-4o-mini, Whisper, Embeddings) |
| Qualidade | pytest, Ruff, ESLint, Prettier |

## Instalação rápida

```powershell
# 1. Bancos (Docker)
docker compose -f docker/docker-compose.yml up -d

# 2. Backend
cd backend
copy ..\.env.example ..\.env   # preencher OPENAI_API_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 18000

# 3. Worker (outro terminal)
cd backend
uv run arq app.workers.settings.WorkerSettings

# 4. Frontend (outro terminal)
cd frontend
npm install
npm start
```

- API: http://localhost:18000/docs
- App: http://localhost:14200

## Funcionalidades (MVP)

1. Autenticação (registro/login com aceite de termos)
2. Importação de conversas WhatsApp (.txt)
3. Análise com IA (resumo, métricas objetivas, observações vs. inferências)
4. RAG adaptativo (direto/resumo/embeddings conforme tamanho da conversa)
5. Interest & Reciprocity Engine (sinais positivos/neutros/negativos, score, confiança, evidências)
6. Timeline temporal (7d/30d/90d/completo)
7. Upload e transcrição de áudio (Whisper)
8. Sugestões de resposta (4 categorias: Natural/Divertida/Direta/Conservadora)
9. Perguntas livres sobre o histórico
10. Tracking de uso de IA (tokens, custo estimado)
11. Rate limiting em endpoints de IA
12. UI dark theme com design system customizado

## Testes

```powershell
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .

cd ..\frontend
npm run lint
npm run build
```

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Decisões (ADR)](docs/DECISIONS.md)
- [Terceiros e licenças](docs/THIRD_PARTY.md)
- [Desenvolvimento](docs/DEVELOPMENT.md)
- [API](docs/API.md)

## Fases

| Fase | Escopo | Status |
|------|--------|--------|
| 0 | Análise e arquitetura | Concluída |
| 1 | Base (auth, Docker, Angular, testes) | Concluída |
| 2 | Importação WhatsApp TXT | Concluída |
| 3 | IA básica (LLM, métricas, resumo) | Concluída |
| 4 | RAG adaptativo (embeddings, pgvector) | Concluída |
| 5 | Interest Engine (sinais, reciprocidade, evidências) | Concluída |
| 6 | Áudio / Whisper (upload, transcrição) | Concluída |
| 7 | Response Engine (sugestões de resposta) | Concluída |
| 8 | Refinamento (UI, usage, observabilidade, segurança) | Concluída |
