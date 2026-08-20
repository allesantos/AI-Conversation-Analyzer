# Arquitetura — AI Conversation Analyzer

> Documento da **Fase 0** — Análise e Proposta Arquitetural  
> Data: 2026-08-19  
> Status: **Fase 1 concluída — aguardando aprovação para Fase 2**

---

## 1. Visão Geral

**AI Conversation Analyzer** é uma plataforma SaaS para análise inteligente de conversas do WhatsApp. O diferencial não é "usar ChatGPT", mas um mecanismo proprietário:

**Interest & Reciprocity Engine** — combina métricas objetivas, análise semântica, contexto temporal, LLM e evidências para produzir avaliações calibradas de reciprocidade e interesse, sempre distinguindo observação de inferência.

### Princípios arquiteturais

1. **Monólito modular** — um deploy, módulos desacoplados
2. **Métricas antes do LLM** — dados factuais calculados em Python
3. **RAG adaptativo** — só quando a conversa exige
4. **Evidências obrigatórias** — toda conclusão linkada a mensagens
5. **Privacidade by design** — isolamento multi-tenant, logs sem conteúdo privado
6. **Abstrações desacopladas** — providers de LLM, embeddings, transcrição e vector store substituíveis

---

## 2. Estado Atual do Repositório

| Item | Status |
|------|--------|
| Código backend | ✅ FastAPI + auth + conversas |
| Código frontend | ✅ Angular 20 + Material |
| Docker/Infra | ✅ postgres + redis (ADR-015) |
| Especificação | ✅ `.cursor/rules/project-spec.mdc` |
| Documentação | ✅ Fase 0 + DEVELOPMENT + API |

**Conclusão:** Fase 1 (base) implementada. Parser, IA e Interest Engine ainda não existem.

---

## 3. Análise Comparativa dos Projetos de Referência

### 3.1 Tabela Comparativa

| Critério | ChatLab | WhatsVector | Audio Transcriber | **Nosso Produto** |
|----------|---------|-------------|-------------------|-------------------|
| **Tipo** | Desktop (Electron) | CLI Python | Chrome Extension | **SaaS Web** |
| **Licença** | AGPL-3.0 ❌ | MIT ✅ | MIT ✅ | Proprietário |
| **Frontend** | Vue 3 | N/A (CLI) | JS (extensão) | **Angular** |
| **Backend** | Node.js/Electron | Python CLI | N/A | **FastAPI** |
| **Banco** | SQLite local | Qdrant | chrome.storage | **PostgreSQL + pgvector** |
| **Parser WhatsApp** | ✅ Maduro, multi-idioma | ⚠️ Básico (1 formato) | ❌ N/A | **Próprio (Fase 2)** |
| **Métricas objetivas** | ✅ SQL + charts | ❌ | ❌ | **✅ Interest Engine** |
| **RAG/Semântica** | ✅ Tools + SQL | ✅ Qdrant + LangGraph | ❌ | **✅ pgvector adaptativo** |
| **Análise reciprocidade** | ❌ Genérica | ❌ | ❌ | **✅ Diferencial** |
| **Evidências** | ⚠️ Parcial | ⚠️ Sources | ❌ | **✅ Obrigatório** |
| **Transcrição áudio** | ❌ | ❌ | ✅ Multi-provider | **✅ Whisper API (Fase 6)** |
| **Multi-tenant SaaS** | ❌ Local-only | ❌ CLI local | ❌ | **✅** |
| **Agent/Orquestração** | LangChain.js + tools | LangGraph simples | ❌ | **LangGraph pipeline** |
| **Maturidade** | Alta (~7k stars) | Baixa (v0.1.0) | Baixa (extensão) | Greenfield |
| **Privacidade** | ✅ Local-first | ⚠️ Local CLI | ⚠️ Envia áudio | **✅ Isolamento + LGPD** |

### 3.2 Mapa de Inspiração (conceitos, não código)

```
ChatLab                          WhatsVector                    Audio Transcriber
    │                                │                                │
    ├─ Streaming parser         ──→  ├─ LangGraph agent         ──→  ├─ Multi-provider
    ├─ Métricas SQL             ──→  ├─ Pydantic models         ──→  ├─ OpenAI-compatible API
    ├─ Agent + 24 tools         ──→  ├─ DataLoader abstract     ──→  ├─ Cache de transcrições
    ├─ Desensibilização PII     ──→  ├─ Rich content embedding  ──→  └─ Groq como alternativa
    ├─ Normalização cross-plat  ──→  └─ Profile/config YAML
    └─ Visual analytics               (conceitos apenas)
         (conceitos apenas)
                                    │
                                    ▼
                         AI CONVERSATION ANALYZER
                         (implementação 100% própria)
```

---

## 4. Stack Tecnológica (Obrigatória)

### Backend

| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Python | 3.12+ | Linguagem principal |
| FastAPI | latest | API REST + OpenAPI |
| Pydantic | v2 | Validação/schemas |
| SQLAlchemy | 2.x | ORM |
| Alembic | latest | Migrações |
| uv | latest | Package manager |

### Frontend

| Tecnologia | Uso |
|-----------|-----|
| Angular | SPA framework |
| TypeScript | Linguagem |
| RxJS | Reatividade |
| Angular Material | Componentes UI |

### Infraestrutura

| Tecnologia | Uso |
|-----------|-----|
| PostgreSQL 16+ | Banco principal |
| pgvector | Embeddings/vetores |
| Redis | Cache + fila ARQ |
| ARQ | Jobs assíncronos |
| Docker + Compose | Containerização (apenas postgres + redis) |
| Docker Desktop (Windows nativo) | Dev environment — ver ADR-015 |

### IA

| Tecnologia | Uso |
|-----------|-----|
| LangChain | Integrações LLM |
| LangGraph | Orquestração pipeline |
| OpenAI API | LLM + Embeddings + Whisper (inicial) |

### Qualidade

| Backend | Frontend |
|---------|----------|
| pytest + pytest-asyncio | ESLint |
| httpx | Prettier |
| Ruff + Ruff Formatter | |

---

## 5. Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Angular)                       │
│  /login  /register  /dashboard  /conversations  /analysis       │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API (HTTPS)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API (FastAPI — Monólito Modular)            │
│  ┌─────────┐ ┌──────────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Auth   │ │ Conversation │ │    AI    │ │ Interest Engine│  │
│  │  JWT    │ │  Import/CRUD │ │ Pipeline │ │   (proprietário)│  │
│  └─────────┘ └──────────────┘ └──────────┘ └────────────────┘  │
└────────┬───────────────────────────────┬──────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌─────────────────┐
│  PostgreSQL 16  │            │     Redis       │
│  + pgvector     │            │  (cache + fila) │
│                 │            └────────┬────────┘
│  Users          │                     │
│  Conversations  │                     ▼
│  Messages       │            ┌─────────────────┐
│  Embeddings     │            │  Worker (ARQ)   │
│  Analyses       │            │  Jobs async:    │
│  AIUsage        │            │  - import       │
└─────────────────┘            │  - transcribe   │
                               │  - embed        │
                               │  - analyze      │
                               │  - timeline     │
                               │  - suggestions  │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │   LangGraph     │
                               │   Pipeline      │
                               │   (14+ nodes)   │
                               └────────┬────────┘
                                        │
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
                     OpenAI LLM   OpenAI Embed   OpenAI Whisper
                     (futuro:    (futuro:       (futuro:
                      Claude,     local,          Groq,
                      Gemini)     other)          local)
```

---

## 6. Estrutura de Pastas Proposta

```
AI-Conversation-Analyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── conversations.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── audio.py
│   │   │   │   └── usage.py
│   │   │   └── deps.py
│   │   ├── auth/
│   │   │   ├── jwt.py
│   │   │   └── password.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── embedding.py
│   │   │   ├── analysis.py
│   │   │   └── usage.py
│   │   ├── schemas/
│   │   │   └── ... (Pydantic v2)
│   │   ├── repositories/
│   │   │   └── ... (data access)
│   │   ├── services/
│   │   │   └── ... (business logic)
│   │   ├── conversation/
│   │   │   ├── whatsapp_parser.py
│   │   │   ├── normalizer.py
│   │   │   └── metrics.py
│   │   ├── ai/
│   │   │   ├── llm/
│   │   │   │   ├── provider.py
│   │   │   │   └── openai_provider.py
│   │   │   ├── embeddings/
│   │   │   │   ├── provider.py
│   │   │   │   └── openai_provider.py
│   │   │   ├── transcription/
│   │   │   │   ├── provider.py
│   │   │   │   └── openai_whisper.py
│   │   │   ├── rag/
│   │   │   │   ├── chunker.py
│   │   │   │   ├── vector_store.py
│   │   │   │   ├── retriever.py
│   │   │   │   └── context_builder.py
│   │   │   ├── agents/
│   │   │   │   ├── graph.py
│   │   │   │   └── nodes/
│   │   │   └── prompts/
│   │   │       ├── analysis/
│   │   │       ├── interest/
│   │   │       ├── reciprocity/
│   │   │       └── responses/
│   │   ├── interest_engine/
│   │   │   ├── signal_detector.py
│   │   │   ├── signal_classifier.py
│   │   │   ├── score_calculator.py
│   │   │   ├── confidence.py
│   │   │   ├── evidence_builder.py
│   │   │   ├── timeline_analyzer.py
│   │   │   └── reciprocity.py
│   │   ├── response_engine/
│   │   │   └── suggestion_generator.py
│   │   └── workers/
│   │       ├── settings.py
│   │       └── tasks.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/
│   │   │   ├── shared/
│   │   │   └── features/
│   │   │       ├── auth/
│   │   │       ├── dashboard/
│   │   │       ├── conversations/
│   │   │       └── analysis/
│   │   └── environments/
│   ├── angular.json
│   └── package.json
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── .env.example
├── docs/
│   ├── ARCHITECTURE.md      ← este documento
│   ├── THIRD_PARTY.md
│   ├── DECISIONS.md
│   ├── DEVELOPMENT.md       (Fase 1)
│   └── API.md               (Fase 1)
├── infra/
└── README.md                 (Fase 1)
```

---

## 7. Modelo de Dados

### Entidades principais

```
User ──────────┐
               │ 1:N
               ▼
          Conversation ──────────┐
               │                 │ 1:N
               │ 1:N             ▼
               ▼            Participant
           Message ─────────────┐
               │                 │ 1:N
               │ 1:N             ▼
               ▼         MessageAttachment
        AudioTranscription
               │
               │ 1:N
               ▼
          Embedding (vector pgvector)
               
Conversation ──┐
               │ 1:N
               ▼
    ConversationAnalysis ──┐
               │            │ 1:N
               │ 1:N        ▼
               ▼     AnalysisEvidence
        InterestAnalysis
               │
               │ 1:N
               ▼
      ResponseSuggestion

User ──→ AIUsage (tracking de consumo)
```

### Message

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | UUID | PK |
| conversation_id | UUID | FK |
| sender_id | UUID | FK → Participant |
| timestamp | datetime | Data/hora da mensagem |
| type | enum | TEXT, AUDIO, IMAGE, SYSTEM |
| content | text | Conteúdo (ou transcrição) |
| metadata | jsonb | Dados extras |
| created_at | datetime | Registro no sistema |

### ConversationAnalysis / InterestAnalysis

| Campo | Tipo | Descrição |
|-------|------|-----------|
| interest_score | int (0-100) | Score numérico |
| interest_level | enum | MUITO_BAIXO … MUITO_ALTO |
| confidence_score | int (0-100) | Confiança da avaliação |
| positive_signals | jsonb | Lista de sinais positivos |
| neutral_signals | jsonb | Lista de sinais neutros |
| negative_signals | jsonb | Lista de sinais negativos |
| summary | text | Resumo gerado |
| metrics | jsonb | Métricas objetivas calculadas |

---

## 8. Fluxos de Dados

### 8.1 Importação de Conversa

```
Usuário upload .txt
        │
        ▼
POST /conversations/{id}/import
        │
        ▼
WhatsAppParser (streaming)
  ├─ detecta formato de data
  ├─ parse linha a linha
  ├─ trata multilinha
  └─ identifica participantes
        │
        ▼
Normalizer → modelo unificado
        │
        ▼
Persist (Conversation, Participants, Messages)
        │
        ▼
Retorna resumo (total msgs, participantes, período)
```

### 8.2 Pipeline de Análise (LangGraph)

```
POST /conversations/{id}/analyze
        │
        ▼
Job ARQ: analyze_conversation
        │
        ▼
┌─ LangGraph Pipeline ──────────────────────────────────────┐
│                                                           │
│  START                                                    │
│    ↓                                                      │
│  LoadConversation                                         │
│    ↓                                                      │
│  NormalizeConversation                                    │
│    ↓                                                      │
│  CalculateMetrics ──── (Python puro, sem LLM)             │
│    ↓                                                      │
│  BuildConversationSummary                                 │
│    ↓                                                      │
│  DetermineContextStrategy                                 │
│    ├─ < 2k msgs → direct                                  │
│    ├─ 2k-10k → summary + selection                        │
│    └─ > 10k → RAG + summary + metrics                     │
│    ↓                                                      │
│  RetrieveRelevantContext (se necessário)                  │
│    ↓                                                      │
│  AnalyzeCommunication                                     │
│    ↓                                                      │
│  AnalyzeReciprocity                                       │
│    ↓                                                      │
│  AnalyzeInterestSignals                                   │
│    ↓                                                      │
│  GenerateEvidence                                         │
│    ↓                                                      │
│  GenerateInterestAssessment                               │
│    ↓                                                      │
│  GenerateSummary                                          │
│    ↓                                                      │
│  GenerateResponseSuggestions                              │
│    ↓                                                      │
│  END                                                      │
└───────────────────────────────────────────────────────────┘
        │
        ▼
Persist (ConversationAnalysis, InterestAnalysis, Evidence, Suggestions)
        │
        ▼
Retorna resultado com evidências
```

### 8.3 Pipeline de Áudio (Fase 6)

```
Upload áudio (.ogg/.opus)
        │
        ▼
POST /conversations/{id}/audio
        │
        ▼
Job ARQ: process_audio
        │
        ▼
TranscriptionProvider.transcribe()
  └─ OpenAI Whisper API (inicial)
        │
        ▼
Cria Message (type=AUDIO, content=transcrição)
        │
        ▼
Gera embedding (se conversa > limite RAG)
        │
        ▼
Disponível para re-análise
```

### 8.4 RAG Adaptativo (Fase 4)

```
Conversa grande (> 10k msgs)
        │
        ▼
Chunker (por janela temporal ou N mensagens)
        │
        ▼
EmbeddingProvider.embed(chunks)
        │
        ▼
VectorStore.store (pgvector)
        │
        ▼
Query do usuário / análise
        │
        ▼
ConversationRetriever.search(query, filters)
        │
        ▼
ContextBuilder.assemble(retrieved + metrics + summary)
        │
        ▼
LLM (com contexto selecionado, não histórico completo)
```

---

## 9. Interest & Reciprocity Engine (Diferencial)

Componente **100% proprietário**, não presente em nenhuma referência.

```
                    ┌──────────────────────┐
                    │   Métricas Objetivas  │
                    │  (calculadas antes)   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Signal Detector     │
                    │  (regras + padrões)   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Signal Classifier    │
                    │  positivo/neutro/neg  │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────┐  ┌─────────────┐  ┌──────────────┐
     │ Reciprocity│  │  Timeline   │  │    Score     │
     │  Analyzer  │  │  Analyzer   │  │  Calculator  │
     └─────┬──────┘  └──────┬──────┘  └──────┬───────┘
           │                │                 │
           └────────────────┼─────────────────┘
                            ▼
                   ┌─────────────────┐
                   │ Evidence Builder │
                   │ (msg links)      │
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  LLM Assessment │
                   │  (com evidências) │
                   └─────────────────┘
```

### Exemplo de output

```
Interest Level: ALTO
Confidence: 78%

Observação: "Ela iniciou 4 das últimas 10 conversas."
Inferência: "Isso pode indicar reciprocidade."
Conclusão: "Os sinais disponíveis sugerem reciprocidade moderada/alta."

Evidências:
  → [2026-03-15 14:32] "Oi, tudo bem? Vi aquele filme..."
  → [2026-03-14 09:15] "Bom dia! Conseguiu resolver?"
  → [2026-03-12 20:45] "E aí, como foi a prova?"
```

---

## 10. API REST (Endpoints MVP)

| Método | Endpoint | Fase |
|--------|----------|------|
| POST | `/api/v1/auth/register` | 1 |
| POST | `/api/v1/auth/login` | 1 |
| POST | `/api/v1/conversations` | 1 |
| GET | `/api/v1/conversations` | 1 |
| GET | `/api/v1/conversations/{id}` | 2 |
| POST | `/api/v1/conversations/{id}/import` | 2 |
| POST | `/api/v1/conversations/{id}/analyze` | 3/5 |
| GET | `/api/v1/conversations/{id}/analysis` | 3/5 |
| GET | `/api/v1/conversations/{id}/timeline` | 5 |
| POST | `/api/v1/conversations/{id}/ask` | 3/4 |
| POST | `/api/v1/conversations/{id}/suggestions` | 7 |
| POST | `/api/v1/conversations/{id}/audio` | 6 |
| DELETE | `/api/v1/conversations/{id}` | 1 |
| GET | `/api/v1/usage` | 8 |

---

## 11. Docker Compose (Dev)

> ⚠️ Atualizado — ver ADR-015 em `docs/DECISIONS.md`. Apenas os bancos de dados rodam em Docker; API, worker e frontend rodam nativamente no Windows.

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["55432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aca -d aca"]

  redis:
    image: redis:7-alpine
    ports: ["56379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

volumes:
  pgdata:
```

FastAPI, ARQ worker e Angular rodam diretamente no Windows (fora do Docker), conectando-se aos bancos via `localhost:55432` e `localhost:56379`.

Atalhos na área de trabalho (mesmo padrão de Site Cursos / Game Hub):

- `AI Conversation Analyzer.bat` → `scripts/dev-windows/start-dev.bat`
- `AI Conversation Analyzer - Parar.bat` → `scripts/dev-windows/stop-dev.bat`

```
# Terminal 1 — API
cd backend && uv run uvicorn app.main:app --reload --port 18000

# Terminal 2 — Worker
cd backend && uv run arq app.workers.settings.WorkerSettings

# Terminal 3 — Frontend
cd frontend && npm start
```

---

## 12. Plano de Implementação por Fases

| Fase | Escopo | Estimativa | Dependências |
|------|--------|-----------|-------------|
| **0** | Análise + docs | ✅ Concluída | — |
| **1** | Base: backend, frontend, Docker, auth, DB | ✅ Concluída | Fase 0 aprovada |
| **2** | Importação: WhatsAppParser + storage + UI | 2-3 sem | Fase 1 |
| **3** | IA básica: LLM, métricas, resumo, ask | 2-3 sem | Fase 2 |
| **4** | RAG adaptativo: embeddings + pgvector | 2 sem | Fase 3 |
| **5** | Interest Engine: sinais, score, evidências, timeline | 3-4 sem | Fase 3 |
| **6** | Áudio: upload, Whisper, transcrição | 1-2 sem | Fase 2 |
| **7** | Response Engine: sugestões contextualizadas | 1-2 sem | Fase 5 |
| **8** | Refinamento: UX, usage, observabilidade, docs | 2-3 sem | Todas |
| **9** | **Import 2.0:** zip com mídia, wizard export, incremental, timeline unificada (ADR-018 v0.5.0) | 3-5 sem | Fase 6, 8 |

**Estimativa total MVP:** 15-22 semanas (1 dev) — **Fases 0–8 concluídas.** Fase 9 é evolução pós-MVP.

### Fase 9 — Import 2.0 (ADR-018 v0.5.0)

**Evolution API descartado** para produto comercial (ToS, ban, LGPD). Captura via **export oficial** do WhatsApp — padrão ChatLab / ChatStats / WhatsAnalyze.

```
WhatsApp app  →  Exportar (.txt / .zip)
                      ↓
              ACA Import 2.0 (wizard + parser + áudios + incremental)
                      ↓
              Timeline + Interest Engine (pipeline atual)
```

- Público **1:1 pessoal**; **nunca** enviar mensagens.
- Sem QR code, webhook ou sessão WhatsApp na nuvem.
- Detalhes: `docs/DECISIONS.md` ADR-018.

### Critério de sucesso do MVP

O MVP estará completo quando for possível:
1. Criar conta e login
2. Criar conversa e importar `.txt`
3. Visualizar mensagens e participantes
4. Executar análise com sinais positivos/neutros/negativos
5. Ver nível de reciprocidade, confidence e evidências
6. Ver evolução temporal
7. Fazer perguntas sobre histórico
8. Receber sugestões de resposta
9. Upload/transcrição de áudio
10. Re-análise considerando áudio

---

## 13. Riscos Técnicos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|--------------|-----------|
| Parser WhatsApp incompleto (formatos BR, multilinha) | **Alto** | **Alta** | Testes extensivos; fixtures diversas; iterar com exports reais |
| Custos OpenAI em conversas grandes | **Alto** | **Média** | RAG adaptativo; métricas sem LLM; tracking AIUsage |
| Calibração do Interest Engine | **Alto** | **Alta** | Iteração com dados fictícios; pesos configuráveis; feedback loop |
| Performance import conversas >100k msgs | **Médio** | **Média** | Streaming parser; jobs async; batch inserts |
| AGPL ChatLab — tentação de copiar | **Alto** | **Baixa** | Documentação clara; code review; implementação própria |
| Isolamento multi-tenant falho | **Crítico** | **Baixa** | Testes de autorização desde Fase 1; middleware user_id |
| pgvector performance em escala | **Médio** | **Baixa** | Abstração VectorStore; índices HNSW; migrar Qdrant se necessário |
| LangGraph complexidade | **Médio** | **Média** | Nodes independentes; testes por node; pipeline incremental |

---

## 14. O que Reutilizar vs. Implementar do Zero

### ✅ Reutilizar (conceitos/padrões)

| Origem | Conceito | Aplicação |
|--------|----------|-----------|
| ChatLab | Streaming parser | `WhatsAppParser` |
| ChatLab | Métricas antes do LLM | `metrics.py` + Interest Engine |
| ChatLab | Agent + tools | LangGraph nodes com tools |
| ChatLab | Desensibilização PII | Middleware pré-LLM |
| ChatLab | Normalização cross-platform | `normalizer.py` |
| WhatsVector | DataLoader abstract | `VectorStore` interface |
| WhatsVector | LangGraph agent + tool | `agents/graph.py` |
| WhatsVector | Rich content p/ embeddings | Formato de chunk enriquecido |
| Audio Transcriber | Multi-provider pattern | `TranscriptionProvider` |

### ❌ Implementar do zero

| Componente | Motivo |
|-----------|--------|
| WhatsAppParser completo | AGPL (ChatLab) + incompleto (WhatsVector) |
| Interest & Reciprocity Engine | Diferencial; não existe em referências |
| Response Engine | Específico do produto |
| Frontend Angular | Stack diferente de todas referências |
| API REST multi-tenant | SaaS vs. desktop/CLI |
| Auth + isolamento | Requisito SaaS |
| Modelo de dados PostgreSQL | Stack definida na spec |
| Pipeline LangGraph completo | Muito mais rico que WhatsVector |

### ❌ NÃO reutilizar

| Item | Motivo |
|------|--------|
| Código ChatLab | AGPL-3.0 |
| Qdrant como store | Spec define pgvector |
| Electron/Vue UI | Spec define Angular |
| WhatsApp Web injection | Fora de escopo MVP |
| Browser Whisper (Transformers.js) | Backend usa Whisper API |

---

## 15. Próximos Passos

A **Fase 1** está implementada. Após aprovação explícita, a **Fase 2** cobre:

- `WhatsAppParser` (TXT exportado)
- Persistência de participantes e mensagens
- Visualização da conversa no Angular

Não avançar automaticamente.

---

## Histórico de Revisões

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-08-19 | 0.1.0 | Documento inicial — Fase 0 |
| 2026-08-19 | 0.1.1 | Ambiente de dev revisado (Seção 4/11/15) — apenas postgres+redis em Docker, API/worker/frontend nativos no Windows. Ver ADR-015. |
| 2026-08-19 | 0.2.0 | Fase 1 implementada (base). |
| 2026-08-19 | 0.2.1 | Portas de host não padrão (ADR-016). |
| 2026-08-19 | 0.2.2 | Atalhos .bat na área de trabalho e scripts/dev-windows. |
