# AI Conversation Analyzer

Plataforma SaaS de análise inteligente de conversas do WhatsApp, com Angular + FastAPI, Interest & Reciprocity Engine, RAG adaptativo, transcrição de áudio (Whisper) e sugestões de resposta contextualizadas.

> Diferencial: **não** é “só usar ChatGPT”. Combina métricas objetivas, sinais, evidências e LLM — sempre separando **observação** de **inferência**.

---

## Índice
- [Descrição](#-descrição)
- [Screenshots](#-screenshots)
- [Recursos](#-recursos)
- [Tecnologias](#-tecnologias)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação](#-instalação)
- [Configuração](#️-configuração)
- [Uso](#️-uso)
- [Arquitetura](#️-arquitetura)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Docker Services](#-docker-services)
- [Segurança](#-segurança)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

---

## Descrição

**AI Conversation Analyzer** é uma aplicação web para importar exports do WhatsApp (`.txt` / `.zip`), analisar reciprocidade e interesse com evidências, perguntar sobre o histórico, sugerir respostas ao vivo e transcrever áudios.

Ambiente de desenvolvimento (ADR-015): **apenas PostgreSQL + Redis** no Docker; API, worker ARQ e Angular rodam nativos no Windows, em **portas não padrão**.

### Objetivo do Projeto

Demonstrar conhecimentos em:

- SaaS full-stack (Angular SPA + FastAPI REST/OpenAPI)
- Domínio de conversas (parser WhatsApp, participantes, mídia, timeline)
- PostgreSQL 16 + **pgvector** e Redis + jobs **ARQ**
- Orquestração de IA (LLM, embeddings, Whisper) com abstrações de provider
- Interest & Reciprocity Engine (sinais, score, confiança, evidências)
- RAG adaptativo (direto / resumo / retrieval conforme tamanho)
- Privacidade / LGPD (isolamento por usuário, exclusão, logs sem conteúdo privado)
- UX de produto (dashboard, abas Análise / Conversa / Explorar)

---

## Screenshots

Telas principais do fluxo — da landing até a análise e exploração.

> Todas as telas do fluxo principal estão em `docs/screenshots/` (landing → usage).

<br>

**1. Landing / marketing**

Apresentação do produto, proposta de valor e call-to-action para cadastro.

<img src="docs/screenshots/1-landing.png" width="700" alt="Landing page">

<br><br>

**2. Cadastro**

Criação de conta com validação e aceite de termos (LGPD).

<img src="docs/screenshots/2-register.png" width="700" alt="Cadastro">

<br><br>

**3. Login**

Autenticação JWT para acessar dashboard e conversas.

<img src="docs/screenshots/3-login.png" width="700" alt="Login">

<br><br>

**4. Dashboard da conta**

Totais de conversas, distribuição de interesse, últimas análises e uso de IA.

<img src="docs/screenshots/4-dashboard.png" width="700" alt="Dashboard">

<br><br>

**5. Lista de conversas**

Criação e listagem de conversas importadas.

<img src="docs/screenshots/5-conversations.png" width="700" alt="Conversas">

<br><br>

**6. Detalhe — aba Análise**

Nível de interesse, confiança, métricas, resumo, evolução temporal, sinais e evidências.

<img src="docs/screenshots/6-analysis.png" width="700" alt="Aba Análise">

<br><br>

**7. Detalhe — aba Conversa**

Atualizar dados (TXT/ZIP/áudio), completar mídias e timeline de mensagens.

<img src="docs/screenshots/7-conversation-tab.png" width="700" alt="Aba Conversa">

<br><br>

**8. Detalhe — aba Explorar**

Perguntas livres sobre o histórico e sugestões a partir de mensagem colada do WhatsApp.

<img src="docs/screenshots/8-explore.png" width="700" alt="Aba Explorar">

<br><br>

**9. Uso de IA**

Consumo agregado (tokens, áudio, custo estimado) por dia/operação.

<img src="docs/screenshots/9-usage.png" width="700" alt="Uso de IA">

<br>

---

## Recursos

### Implementados

- **Autenticação**
  - Registro com aceite de termos (LGPD)
  - Login JWT (Bearer)
  - Isolamento multi-tenant por `user_id`
  - Proteção de rotas no Angular (`authGuard`)

- **Importação WhatsApp**
  - Parser próprio de `.txt` (vários formatos de data, multilinha, sistema, mídia oculta)
  - Import `.zip` com pareamento de áudios
  - Reimport incremental (evita duplicatas)
  - Seleção do participante OWNER

- **Análise com IA**
  - Métricas objetivas em Python (volume, iniciativa, tempos de resposta, etc.)
  - Resumo contextual + observações vs. inferências
  - Interest & Reciprocity Engine (sinais +, neutros, −)
  - Score 0–100 → níveis (MUITO_BAIXO … MUITO_ALTO) + confiança
  - Evidências linkadas a mensagens
  - Evolução temporal (períodos)
  - Cache de análise quando os dados não mudaram

- **RAG adaptativo**
  - Conversas pequenas: contexto direto
  - Médias: resumo + seleção
  - Grandes: embeddings + pgvector + retrieval
  - Jobs ARQ para geração de embeddings

- **Áudio**
  - Upload vinculado à mensagem
  - Transcrição via Whisper (provider abstrato)
  - Colar texto manual na timeline / Completar mídias
  - Reanálise incorporando transcrições

- **Explorar**
  - Perguntar sobre o histórico (LLM + contexto/RAG)
  - Sugestões de resposta a partir da **mensagem colada agora** (não da última do export)
  - Categorias: NATURAL, DIVERTIDA, DIRETA, CONSERVADORA
  - Rate limiting nos endpoints de IA

- **Produto / UX**
  - Dashboard de conta (distribuição + recentes + usage)
  - Detalhe em abas: Análise | Conversa | Explorar
  - Tracking de uso de IA (`AIUsage`)
  - Design Flemm (Angular Material)

### Em evolução / próximos passos

- CI (GitHub Actions)
- Rate limit em login/register
- Hardening de produção (JWT obrigatório forte, OpenAPI fechado)
- Providers alternativos (Anthropic, Groq, Whisper local)

### Demo

- **URL:** https://analyzer.allecursos.cloud  
- Deploy VPS: ver [docs/DEPLOY.md](docs/DEPLOY.md)
- Contas novas: cadastro/import ok; **IA bloqueada** até liberação (exceto `alledesenvolvimento@gmail.com`)
- Contas liberadas: cota mensal **20 LLM** + **10 min** Whisper (owner sem limite)

---

## Tecnologias

| Camada | Tecnologias |
| :----- | :---------- |
| **Frontend** | Angular 20, TypeScript, RxJS, Angular Material |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| **Dados** | PostgreSQL 16 + pgvector, Redis 7 |
| **Jobs** | ARQ |
| **IA** | OpenAI (LLM, Embeddings, Whisper); abstrações para outros providers |
| **Orquestração** | Pipeline de análise (métricas → contexto → interesse → evidências) |
| **Qualidade** | pytest, pytest-asyncio, httpx, Ruff, ESLint, Prettier |
| **Packages** | uv (Python), npm (frontend) |
| **Containers** | Docker Compose (somente Postgres + Redis em dev) |

---

## Pré-requisitos

- **Python 3.12+** com [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** e npm
- **Docker Desktop** (Postgres + Redis)
- **Git**
- **OpenAI API Key** (análise, ask, sugestões, embeddings, Whisper)
- Windows 10/11 (fluxo principal documentado; Linux/macOS possível com ajustes de scripts)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/allesantos/AI-Conversation-Analyzer.git
cd AI-Conversation-Analyzer
```

### 2. Variáveis de ambiente

```powershell
copy .env.example .env
```

Preencha pelo menos `OPENAI_API_KEY` e altere `JWT_SECRET` se for além de experimento local.

### 3. Bancos (Docker)

```powershell
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
```

### 4. Backend

```powershell
cd backend
uv sync
uv run alembic upgrade head
```

### 5. Frontend

```powershell
cd frontend
npm install
```

---

## Configuração

Arquivo `.env` na raiz (nunca commitado). Exemplo baseado em `.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://aca:aca@localhost:55432/aca
REDIS_URL=redis://localhost:56379/0

OPENAI_API_KEY=sk-...

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
TRANSCRIPTION_PROVIDER=openai
TRANSCRIPTION_MODEL=whisper-1

JWT_SECRET=change-me-in-development-min-32-bytes
JWT_EXPIRE_MINUTES=1440

# RAG (limites ajustáveis)
RAG_DIRECT_MAX_MESSAGES=2000
RAG_SUMMARY_MAX_MESSAGES=10000
```

| Serviço | Porta host |
|---------|------------|
| PostgreSQL | **55432** |
| Redis | **56379** |
| FastAPI | **18000** |
| Angular | **14200** |
| pgAdmin (opcional) | **15050** |

Credenciais Postgres de **dev**: user/senha/db = `aca` (só localhost).

---

## Uso

### Subir tudo (Windows)

Atalhos / scripts:

```powershell
scripts\dev-windows\start-dev.bat
scripts\dev-windows\stop-dev.bat
```

Ou manualmente (3 terminais):

```powershell
# Terminal 1 — API
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 18000

# Terminal 2 — Worker ARQ
cd backend
uv run arq app.workers.settings.WorkerSettings

# Terminal 3 — Angular
cd frontend
npm start
```

| URL | Função |
|-----|--------|
| http://localhost:14200 | App |
| http://127.0.0.1:18000/docs | Swagger / OpenAPI |

### Testes

```powershell
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .

cd ..\frontend
npm run lint
npm run build
```

Os testes do backend usam SQLite em memória e **não** exigem Docker.

### Fluxo principal no app

1. Registrar conta (aceite de termos) → login  
2. Criar conversa → importar `.txt` ou `.zip`  
3. Definir quem é você (OWNER)  
4. **Gerar análise** (aba Análise)  
5. Completar mídias / colar transcrições (aba Conversa)  
6. Reanalisar se houver conteúdo novo  
7. Perguntar ou colar mensagem recebida agora para sugestões (aba Explorar)  
8. Acompanhar consumo em **Uso** e overview no **Dashboard**

---

## Arquitetura

### Componentes

```
┌──────────────────┐
│  Angular (14200) │
└────────┬─────────┘
         │ REST / JWT
         ▼
┌──────────────────┐     ┌─────────────┐
│ FastAPI (18000)  │────▶│ PostgreSQL  │
│ monólito modular │     │ + pgvector  │
└────────┬─────────┘     └─────────────┘
         │
         │ Redis
         ▼
┌──────────────────┐
│  ARQ Worker      │  embeddings + transcription
└──────────────────┘
         │
         ▼
   OpenAI (LLM / Embeddings / Whisper)
```

### Pipeline de análise (simplificado)

```
Import WhatsApp
  → Normalização + métricas objetivas
  → Estratégia de contexto (direto | resumo | RAG)
  → Interest Engine (sinais, reciprocidade, score, evidências)
  → Resumo / observações / inferências (LLM)
  → Persistência (ConversationAnalysis + Evidence)
```

### Sugestões de resposta

```
Usuário cola mensagem recebida AGORA
  → Histórico importado só como contexto (métricas + RAG)
  → LLM gera 4 tons (NATURAL / DIVERTIDA / DIRETA / CONSERVADORA)
```

Documentação detalhada: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DECISIONS.md](docs/DECISIONS.md) · [docs/API.md](docs/API.md)

---

## Estrutura do Projeto

```
AI-Conversation-Analyzer/
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   ├── app/
│   │   ├── api/v1/           # auth, conversations, dashboard, usage
│   │   ├── ai/               # llm, embeddings, transcription, rag, prompts
│   │   ├── auth/
│   │   ├── conversation/     # parser, metrics, context
│   │   ├── core/             # config, db, jwt, logging, rate limit
│   │   ├── interest_engine/  # sinais, score, evidências, timeline
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── response_engine/  # sugestões
│   │   ├── services/
│   │   └── workers/          # ARQ
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   └── src/app/
│       ├── core/             # auth, guards, services, models
│       ├── features/         # login, dashboard, conversations, usage, marketing
│       └── shared/           # shell, signal-pulse
├── docker/
│   └── docker-compose.yml    # postgres + redis (+ pgadmin opcional)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DECISIONS.md
│   ├── DEVELOPMENT.md
│   ├── THIRD_PARTY.md
│   └── screenshots/          # prints do README
├── infra/
└── scripts/dev-windows/      # start-dev / stop-dev
```

---

## Docker Services

### Desenvolvimento — só bancos

```powershell
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f postgres
docker compose -f docker/docker-compose.yml down
```

| Serviço | Imagem | Porta host |
|---------|--------|------------|
| `aca-postgres` | `pgvector/pgvector:pg16` | 55432 |
| `aca-redis` | `redis:7-alpine` | 56379 |
| `aca-pgadmin` (profile `tools`) | `dpage/pgadmin4` | 15050 |

```powershell
docker compose -f docker/docker-compose.yml --profile tools up -d
# http://localhost:15050  →  admin@local.dev / admin
```

API, worker e Angular **não** entram no Compose em dev (ADR-015).

---

## Segurança

### Implementado

- Senhas com **bcrypt**
- JWT Bearer; rotas de conversa filtradas por dono (404 cross-user)
- Secrets via `.env` (não versionado); `.env.example` só com placeholders
- Upload com limites de tamanho; áudio/storage com nomes UUID
- Rate limiting em endpoints de IA (`/analyze`, `/ask`, `/suggestions`)
- Logs estruturados **sem** conteúdo de mensagens
- DELETE de conversa com cascade (mensagens, análises, embeddings, etc.)
- Aceite de termos no registro

### Importante em produção

Não use os defaults de desenvolvimento:

```env
DEBUG=False
JWT_SECRET=<gere-um-segredo-forte>
POSTGRES_PASSWORD=<senha-forte>
# Redis com autenticação; não exponha 55432/56379 na internet
# Desligue ou proteja /docs em produção
```

Credenciais `aca`/`aca` e `JWT_SECRET=change-me-…` são **apenas para localhost**.

---

## Contribuição

1. Fork do projeto  
2. Branch: `git checkout -b feature/minha-feature`  
3. Commit no padrão [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`  
4. Push e Pull Request  

Antes do PR: `uv run pytest` no backend e `npm run lint` / `npm run build` no frontend.

---

## Troubleshooting

### `connection refused` no Postgres/Redis

```powershell
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml up -d
```

Confirme portas **55432** e **56379** no `.env`.

### Análise / ask / sugestões falham

- `OPENAI_API_KEY` preenchida no `.env`
- Worker ARQ rodando (embeddings / áudio)
- Conversa com mensagens importadas e OWNER definido

### CORS no browser

Frontend deve estar em `http://localhost:14200` (default do `cors_origins`).

---

## Licença

Uso do código sob termos a definir pelo autor (portfólio).

---

## Contato

Desenvolvido por **Alexandre Santos**

- Email: alledesenvolvimento@gmail.com  
- LinkedIn: [linkedin.com/in/alle-carlos-alexandre](https://www.linkedin.com/in/alle-carlos-alexandre)  
- GitHub: [github.com/allesantos](https://github.com/allesantos)  
- Repositório: [AI-Conversation-Analyzer](https://github.com/allesantos/AI-Conversation-Analyzer)

---

## Roadmap

### MVP (atual)

- [x] Auth, import WhatsApp, análise, Interest Engine  
- [x] RAG, áudio/Whisper, ask, sugestões  
- [x] Dashboard, usage, abas no detalhe  
- [x] Testes automatizados backend  
- [x] Screenshots do portfólio no README (`docs/screenshots/`)

### Próximo

- [ ] CI (GitHub Actions)  

### Demo

- [x] Demo deployada — https://analyzer.allecursos.cloud

### Futuro

- [ ] Providers LLM/transcrição adicionais  
- [ ] Planos FREE / PRO (sem cobrança no MVP)

---

**Se este projeto foi útil, deixe uma estrela no repositório.**

---

**Última atualização:** Agosto 2026  
**Versão:** 0.1.0 (MVP)
