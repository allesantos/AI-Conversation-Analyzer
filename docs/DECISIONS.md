# Decisões Arquiteturais (ADR)

> Documento da **Fase 0** — AI Conversation Analyzer  
> Data: 2026-08-19

Registro de decisões tomadas com base na análise do repositório, projetos de referência e especificação do produto.

Formato: **ADR** (Architecture Decision Record)

---

## ADR-001: Repositório Greenfield

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

O repositório `AI-Conversation-Analyzer` contém apenas a especificação (`.cursor/rules/project-spec.mdc`). Não há código backend, frontend ou infraestrutura.

### Decisão

Iniciar implementação do zero na Fase 1, sem migração ou fork de projetos de referência.

### Consequências

- Liberdade total de arquitetura dentro da stack obrigatória
- Nenhuma dívida técnica herdada
- Parser, engine e frontend serão implementados do zero

---

## ADR-002: Não Copiar Código do ChatLab (AGPL-3.0)

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

ChatLab é a referência mais madura para parsing de WhatsApp e métricas de conversa, mas usa licença **AGPL-3.0**, incompatível com SaaS proprietário.

### Decisão

- **Não copiar** nenhum código do ChatLab
- **Estudar** arquitetura, padrões e especificação ChatLab Format
- **Implementar** parser e métricas próprios inspirados nos conceitos

### Alternativas consideradas

| Alternativa | Descartada porque |
|------------|-------------------|
| Fork do ChatLab | AGPL exige open-source do SaaS |
| Licenciar comercialmente | Sem evidência de oferta comercial |
| Usar apenas CLI/API do ChatLab | Dependência externa desktop; não é SaaS |

### Consequências

- Maior esforço inicial no parser WhatsApp
- Parser deve ser testado extensivamente (ChatLab tem anos de edge cases)
- Inspirar-se no pipeline: detect → parse → normalize → persist → query

---

## ADR-003: Implementação Própria do Parser WhatsApp

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

- ChatLab: parser maduro, mas AGPL
- WhatsVector: parser MIT, mas suporta apenas formato `[DD/MM/YY, HH:MM:SS]`
- Spec exige suporte a formatos BR: `DD/MM/YYYY HH:MM - Nome: mensagem`

### Decisão

Criar `WhatsAppParser` desacoplado com:
- Parsing streaming (linha a linha)
- Suporte multilinha
- Múltiplos formatos de data/hora
- Tratamento de mensagens de sistema e anexos
- Testes extensivos com fixtures fictícias

### Consequências

- Fase 2 terá esforço significativo (~2-3 semanas estimadas)
- Qualidade do parser é crítica para todo o pipeline downstream

---

## ADR-004: PostgreSQL + pgvector em vez de Qdrant

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

WhatsVector usa Qdrant. ChatLab usa SQLite-vec local. A spec define PostgreSQL + pgvector.

### Decisão

Manter PostgreSQL + pgvector com abstração `VectorStore` desacoplada.

### Alternativas consideradas

| Alternativa | Descartada porque |
|------------|-------------------|
| Qdrant (WhatsVector) | Spec define pgvector; adiciona serviço extra |
| SQLite-vec (ChatLab) | Desktop-only; não escala para SaaS multi-tenant |
| Pinecone/Weaviate | Vendor lock-in; custo adicional |

### Consequências

- Um banco para dados relacionais + vetores
- Abstração permite migrar para Qdrant futuramente sem reescrever RAG
- Embeddings via OpenAI API inicialmente

---

## ADR-005: Interest & Reciprocity Engine Proprietário

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

Nenhum projeto de referência implementa análise de reciprocidade/interesse com evidências. ChatLab tem métricas genéricas; WhatsVector é RAG puro.

### Decisão

O **Interest & Reciprocity Engine** é o diferencial do produto e será implementado do zero:
- Métricas objetivas calculadas antes do LLM
- Sinais positivos/neutros/negativos com pesos
- Score 0-100 convertido para níveis qualitativos
- Evidências linkadas a mensagens específicas
- Separação observação vs. inferência vs. conclusão

### Consequências

- Fase 5 será a mais complexa e crítica (~3-4 semanas)
- Requer calibração empírica dos pesos dos sinais
- Diferencial competitivo real do produto

---

## ADR-006: LangGraph para Orquestração de IA

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

- ChatLab: Agent + Function Calling (LangChain.js)
- WhatsVector: LangGraph com agente simples + tool de busca
- Spec: LangGraph com pipeline de nodes independentes

### Decisão

Usar LangGraph com pipeline modular (14+ nodes) conforme spec. Inspirar-se no padrão agent + tools do WhatsVector, mas com pipeline muito mais rico.

### Consequências

- Cada node independente e testável
- Pipeline adaptativo (RAG só quando necessário)
- Complexidade de orquestração gerenciável com LangGraph

---

## ADR-007: Estratégia RAG Adaptativa

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

WhatsVector sempre usa RAG. ChatLab usa tools + SQL + RAG seletivo. Spec define limites configuráveis.

### Decisão

| Tamanho da conversa | Estratégia |
|--------------------|-----------|
| < 2.000 mensagens | Análise direta (sem RAG) |
| 2.000 – 10.000 | Resumo + métricas + contexto selecionado |
| > 10.000 | RAG + resumo + métricas |

Limites configuráveis via `.env`.

### Consequências

- Economia de tokens/custo em conversas pequenas
- RAG implementado na Fase 4, não antes
- `DetermineContextStrategy` node no LangGraph

---

## ADR-008: TranscriptionProvider Abstrato

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

Audio Transcriber demonstra padrão multi-provider (Groq/OpenAI/Local). Spec exige abstração com Whisper API inicial.

### Decisão

```python
class TranscriptionProvider(Protocol):
    async def transcribe(self, audio: bytes, *, language: str | None) -> TranscriptionResult: ...
```

Implementações:
1. `OpenAIWhisperProvider` (inicial)
2. `GroqWhisperProvider` (futuro)
3. `LocalWhisperProvider` (futuro)

Inspirado no padrão de `transcribeWithProvider()` do Audio Transcriber, reimplementado em Python.

### Consequências

- Upload de áudio via API (Fase 6), não integração WhatsApp Web
- Sem análise acústica de sentimento (conforme spec)
- Análise baseada no conteúdo transcrito

---

## ADR-009: Monólito Modular (não Microserviços)

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

Produto MVP com equipe pequena. Referências são apps monolíticos (ChatLab Electron, WhatsVector CLI).

### Decisão

Monólito modular FastAPI com workers ARQ separados (processo, não serviço).

```
api (FastAPI) ──┐
                ├── PostgreSQL + pgvector
worker (ARQ) ───┘── Redis
frontend (Angular) → API REST
```

### Consequências

- Deploy simples via Docker Compose
- Escalar workers independentemente se necessário
- Migrar para microserviços só se houver necessidade real

---

## ADR-010: Importação via TXT (não Integração WhatsApp)

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

- ChatLab: importação de export `.txt`
- WhatsVector: importação de export `.txt`
- Audio Transcriber: integração WhatsApp Web (extensão)
- Spec: MVP via `.txt`; integração direta futura

### Decisão

MVP importa arquivo `.txt` exportado pelo WhatsApp. Interface `WhatsAppProvider` mockada para futuro.

### Consequências

- Sem risco de violação ToS do WhatsApp no MVP
- UX de upload simples na Fase 2
- Integração direta (Cloud API / Evolution API) na Fase 8+

---

## ADR-011: Métricas Objetivas Antes do LLM

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

ChatLab calcula métricas via SQL antes de consultar IA ("organize, then analyze"). WhatsVector delega tudo ao LLM via RAG.

### Decisão

Seguir abordagem ChatLab (conceitualmente):
1. Calcular métricas objetivas (Python puro)
2. Passar métricas + contexto selecionado ao LLM
3. LLM gera inferências com evidências

Métricas iniciais:
- Total de mensagens por participante
- Quem inicia conversas
- Proporção de mensagens
- Média de tamanho
- Tempo de resposta (média, distribuição)
- Frequência por período
- Quantidade de áudios/perguntas

### Consequências

- Resultados mais consistentes e reproduzíveis
- Menor dependência do LLM para dados factuais
- Métricas testáveis unitariamente

---

## ADR-012: Privacidade e LGPD by Design

**Status:** Aceito  
**Data:** 2026-08-19

### Contexto

Produto processa conversas privadas. ChatLab desensibiliza antes de enviar ao LLM. SaaS multi-tenant exige isolamento.

### Decisão

- Isolamento por `user_id` em todas as queries
- DELETE cascata completo (conversa + mensagens + embeddings + análises)
- Logs **nunca** contêm conteúdo de mensagens
- Desensibilização opcional antes de chamadas LLM (PII → placeholders)
- Documentação de privacidade para o usuário

### Consequências

- Middleware de autorização desde Fase 1
- Testes de isolamento entre usuários
- Endpoint DELETE robusto na Fase 1

---

## ADR-013: Frontend Angular (não Vue/React)

**Status:** Aceito (definido na spec)  
**Data:** 2026-08-19

### Contexto

ChatLab usa Vue 3. Spec define Angular obrigatoriamente.

### Decisão

Angular + TypeScript + RxJS + Angular Material. Consome exclusivamente API REST do FastAPI.

### Consequências

- Nenhuma reutilização de UI do ChatLab
- SPA independente do backend
- Pode rodar via `npm start` em dev (fora do Docker)

---

## ADR-014: Consentimento e Tratamento de Dados de Terceiros

**Status:** Aceito (mitigação para MVP; revisão jurídica formal pendente)  
**Data:** 2026-08-19

### Contexto

O sistema analisa conversas entre duas pessoas, mas apenas o usuário (OWNER) consente com o uso da plataforma. O participante "OTHER" tem seus dados pessoais — mensagens, padrões de comportamento, inferências sobre interesse/reciprocidade — processados sem consentimento direto. A LGPD trata isso como dado pessoal de terceiro.

### Decisão

MVP segue com abordagem de mitigação, não de resolução plena (que exige consultoria jurídica dedicada):

- Termo de uso explícito no cadastro, deixando claro que a responsabilidade pelo tratamento do dado do terceiro é do usuário (OWNER), que já tem acesso legítimo à conversa por ser parte dela.
- Nome do participante "OTHER" pode ser anonimizado/pseudonimizado por padrão na interface (ex: "Pessoa X"), reduzindo exposição de identificação direta.
- Nenhum dado do "OTHER" é usado para treinar modelos ou combinado entre contas de usuários diferentes.
- Documentar como risco de produto conhecido, com plano de revisão jurídica formal antes de lançamento comercial público (saída de fase de testes fechados/beta).

### Consequências

- Não elimina o risco legal, apenas reduz a exposição no MVP de validação
- Revisão jurídica formal é pré-requisito antes de sair de beta fechado
- Anonimização de "OTHER" pode impactar UX (ex: sugestões de resposta citando nome) — avaliar na Fase 5/7

---

## Decisões Pendentes — RESOLVIDAS (2026-08-19)

| # | Decisão | Opções | Resolução |
|---|---------|--------|-----------|
| D-01 | Modelo LLM default | gpt-4o-mini / gpt-4o | ✅ **gpt-4o-mini** |
| D-02 | Modelo de embedding | text-embedding-3-small / large | ✅ **text-embedding-3-small** (recomendação Cursor, custo) |
| D-03 | Limites RAG iniciais | 2000/10000 ou outros | ✅ **Manter spec (2k/10k), ajustar após testes** (recomendação Cursor) |
| D-04 | Autenticação | JWT simples / OAuth2 | ✅ **JWT simples** |
| D-05 | Storage de áudio | Filesystem / S3-compatible | ✅ **Filesystem local no MVP** (recomendação Cursor) |
| D-06 | Ambiente de desenvolvimento | Docker completo / Docker parcial / Cloud | ✅ **Apenas PostgreSQL + Redis em Docker. API (FastAPI), worker (ARQ) e frontend (Angular) rodam diretamente no Windows.** Diverge da Seção 4 original do `project-spec.mdc` (que prescrevia FastAPI+worker também em Docker) — ver ADR-015. |

---

## ADR-015: Ambiente de Desenvolvimento Revisado — Backend Nativo no Windows

**Status:** Aceito  
**Data:** 2026-08-19  
**Substitui parcialmente:** Seção 4 do `project-spec.mdc`

### Contexto

A especificação original previa PostgreSQL, Redis, FastAPI e ARQ todos rodando em containers Docker Desktop, com apenas o Angular rodando nativamente via `npm start`. O usuário optou por simplificar: só os serviços de dados (PostgreSQL + Redis) ficam em containers; API, worker e frontend rodam diretamente no Windows.

### Decisão

```
Docker Desktop:
  - postgres (pgvector/pgvector:pg16)
  - redis (redis:7-alpine)

Windows nativo:
  - FastAPI (uvicorn, via uv)
  - ARQ worker (via uv)
  - Angular (npm start)
```

API e worker se conectam aos containers via `localhost:55432` (Postgres) e `localhost:56379` (Redis). Ver ADR-016.

### Consequências

- Setup de dev mais simples (menos rebuild de imagem Docker a cada mudança de código Python)
- Requer Python 3.12+, uv e Node.js instalados diretamente no Windows (fora do WSL2)
- `docker-compose.yml` da Fase 1 deve conter **apenas** `postgres` e `redis`
- Paridade dev/produção é menor (produção provavelmente containerizará tudo) — aceitável para fase de MVP/validação
- `.env` de desenvolvimento deve apontar para `localhost` em vez de nomes de serviço Docker (ex: `DATABASE_URL=postgresql://...@localhost:55432/aca` em vez de `@postgres:5432`)

---

## ADR-016: Portas de host não padrão (evitar conflito com outros projetos)

**Status:** Aceito  
**Data:** 2026-08-19  
**Complementa:** ADR-015

### Contexto

Neste Windows já havia outros containers e serviços publicados em portas padrão (Postgres, Redis, backends e UDP no host). Usar 5432/6379/8000/4200/5050 neste projeto colidiria com esses serviços ou com o default do Angular/pgAdmin.

### Decisão

| Serviço ACA | Porta host |
|-------------|------------|
| PostgreSQL | 55432 |
| Redis | 56379 |
| FastAPI | 18000 |
| Angular | 14200 |
| pgAdmin | 15050 |

Dentro do container as portas nativas permanecem (5432/6379/80). Só o mapeamento no host muda.

Credenciais (`aca`/`aca`/`aca`) são específicas deste projeto. O isolamento em relação aos outros Postgres é a **porta de host**, não o nome do banco.

### Consequências

- `DATABASE_URL` e `REDIS_URL` no `.env` usam 55432 e 56379
- `uvicorn --port 18000`
- `ng serve --port 14200`
- CORS = `http://localhost:14200`

---

## ADR-017: Fingerprint Semântico e Cache de Análise LLM

**Status:** Aceito  
**Data:** 2026-08-19  
**Implementado em:** Fase 3+ (refinamento de custo)

### Contexto

Usuários reimportam o mesmo `.txt` do WhatsApp (novos UUIDs de mensagem/participante) ou clicam em “Reanalisar” sem alterar o conteúdo. Cada chamada a `/analyze` consumia tokens OpenAI desnecessariamente. Exclusão de áudios `analysis_only` invalidava a análise inteira ou forçava novo LLM quando apenas métricas e sinais precisavam ser recalculados.

O Interest Engine roda localmente (Python); o LLM é necessário principalmente para resumo, observações e inferências textuais.

### Decisão

1. **Fingerprint semântico** (`compute_analysis_fingerprint`): hash SHA-256 de mensagens analisáveis ordenadas por `timestamp`, `message_type`, `sender_name` e `content`. **Não** incluir `message.id` nem `sender_id` — sobrevive a reimportações.

2. **Cache em `/analyze`:** se `metrics.llm_content_fingerprint` coincide com o fingerprint atual **e** `summary_stale=false`, retornar análise persistida com `from_cache: true` **sem** chamar o LLM.

3. **Refresh derivado** (`refresh_derived_analysis`): recalcular métricas, Interest Engine, sinais e evidências localmente. Usado após exclusão de áudio `analysis_only` ou quando o conteúdo mudou mas o resumo antigo ainda é útil até o usuário pedir atualização.

4. **Reconciliação no import** (`reconcile_after_import`): após `POST /import`, se já existir análise:
   - conteúdo idêntico → preservar resumo LLM, remapear `message_ids` das evidências, `summary_stale=false`;
   - conteúdo diferente → refresh local + `summary_stale=true`;
   - sem mensagens analisáveis → remover análise.

5. **Persistência em** `ConversationAnalysis.metrics`:
   - `content_fingerprint` — estado atual;
   - `llm_content_fingerprint` — fingerprint na última execução com LLM;
   - `summary_stale` — resumo textual desatualizado.

### Alternativas consideradas

| Alternativa | Descartada porque |
|------------|-------------------|
| Fingerprint com UUIDs de mensagem | Reimport invalida cache mesmo com mesmo `.txt` |
| Sempre reexecutar LLM em reimport | Custo alto; UX desnecessária |
| Invalidar análise inteira ao excluir áudio | Perda de resumo e evidências; pior UX |
| Hash do arquivo `.txt` bruto | Ignora áudios transcritos/importados fora da timeline |

### Consequências

- Redução significativa de custo em F5, reanálise idempotente e reimport do mesmo export
- Análises gravadas **antes** desta ADR (fingerprint baseado em IDs) podem exigir **uma** reanálise para normalizar `llm_content_fingerprint`
- `/ask` e `/suggestions` **não** usam este cache (continuam chamando LLM por requisição)
- Documentação: `docs/API.md`, `docs/DEVELOPMENT.md`
- Testes: `test_analysis_fingerprint.py`, `test_reimport_same_txt_reuses_llm_cache`

---

## ADR-018: Captura de conversas WhatsApp — export oficial + Import 2.0 (Evolution descartado para SaaS)

**Status:** Aceito (revisado — **v0.5.0**)  
**Data:** 2026-08-19  
**Relacionado:** ADR-010 (import TXT), ADR-014 (LGPD terceiros)  
**Revoga:** ADR-018 v0.4.0 (Evolution API, tempo real)

### Contexto

Após o MVP (import `.txt` + áudios da pasta), avaliou-se **Evolution API** para sync **1:1 em tempo real**, **somente leitura**, **sem envio de mensagens**.

Análise de mercado (ChatLab, ChatStats, WhatsAnalyze, Unsaid) e riscos (ToS Meta, **ban do número** do usuário, LGPD multi-tenant) indicaram que Evolution **não é viável** como base de um **SaaS comercial** para análise pessoal 1:1 — mesmo com uso individual, o produto hospedaria sessões em escala.

### O que foi considerado e descartado (v0.4.0)

| Requisito | Evolution API |
|-----------|---------------|
| Público 1:1 pessoal | ✅ Fit de produto |
| Tempo real | ✅ Webhooks |
| Nunca enviar mensagens | ✅ Compatível |
| **Comercializável como SaaS** | ❌ Inviável |
| Risco ban (número WhatsApp) | ❌ Alto |
| ToS Meta | ❌ Cliente não oficial |

Evolution pode existir como **experimento pessoal / self-hosted** fora do roadmap comercial — **não** será implementado na ACA como produto.

### Decisão revisada (v0.5.0)

| Aspecto | Decisão |
|---------|---------|
| Público | Conversas **pessoais 1:1** — inalterado |
| Captura de dados | **Export oficial** do WhatsApp (`.txt` / `.zip` com mídia) |
| Envio de mensagens | **Nunca** — sugestões só para copiar |
| Evolução pós-MVP | **Import 2.0** (Fase 9) |
| Padrão de mercado | Usuário exporta no app oficial → ACA analisa (ChatLab, ChatStats, etc.) |
| `WhatsAppProvider` | Abstração de **import de arquivos** — não conexão live |

### Import 2.0 — Fase 9

```
WhatsApp (app oficial)
    → Exportar conversa (.txt ou .zip com mídia)
    → ACA Import 2.0
         ├─ Parser txt (existente)
         ├─ Extrair áudios do .zip
         ├─ Match + Whisper → transcrição na timeline
         └─ Reimport incremental + fingerprint (ADR-017)
```

| Entrega | Descrição |
|---------|-----------|
| **Wizard de export** | Guia iOS/Android; recomendar *com mídia* se houver áudios |
| **Import `.zip`** | Um upload: chat + áudios (fim da pasta manual) |
| **Reimport incremental** | Novo export → append + dedupe |
| **Timeline unificada** | Uma mensagem por áudio; fim duplicata `MEDIA_OCULTA` + `analysis_only` |
| **Watch folder (opcional)** | Detectar export em Downloads (Windows) |
| **Share target (futuro)** | Mobile: “Abrir com ACA” |

**Fora do escopo:** QR code, webhooks, Evolution em produção, envio de mensagens.

### O que o mercado faz (referência)

| Abordagem | Comercial SaaS? |
|-----------|-----------------|
| Export + upload | ✅ Padrão dominante |
| Desktop / browser local-first | ✅ ChatLab, WhatsAnalyze |
| Extensão WhatsApp Web | ⚠️ Zona cinza; ADR futuro se priorizado |
| Evolution em nuvem | ❌ Grey-market |
| Cloud API Meta | ✅ B2B atendimento — **produto separado** |

### Abstração `WhatsAppProvider` (escopo reduzido)

```python
class WhatsAppProvider(Protocol):
    async def import_file(self, upload: UploadFile, *, owner_name: str | None) -> ImportSummary
    # Futuro: import_zip(), import_incremental()
    # NÃO: start_connect(), send_message()
```

### Plano Fase 9 (3–5 sem)

| Subfase | Entrega |
|---------|---------|
| **9a** | Import `.zip` (txt + áudios) |
| **9b** | Wizard export + timeline unificada no backend |
| **9c** | Reimport incremental + testes E2E |
| **9d** | Watch folder (opcional) + docs |

### Consequências

- Evolution **removido** do roadmap comercial.
- Posicionamento: *“Importe como o WhatsApp permite — análise com Interest Engine”*.
- Diferencial permanece **Interest & Reciprocity Engine**, não integração live.
- Risco de **ban WhatsApp eliminado** (export usa app oficial).

### Histórico deste ADR

| Versão | Conteúdo |
|--------|----------|
| 0.4.0 | Evolution API, tempo real — **revogado** |
| 0.5.0 | Import 2.0, export oficial — **vigente** |

---

## Histórico de Revisões

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-08-19 | 0.1.0 | Decisões iniciais — Fase 0 |
| 2026-08-19 | 0.2.0 | ADR-016: portas de host não padrão |
| 2026-08-19 | 0.3.0 | ADR-017: fingerprint semântico e cache de análise LLM |
| 2026-08-19 | 0.4.0 | ADR-018 v0.4.0: Evolution (revogado na v0.5.0) |
| 2026-08-19 | 0.5.0 | ADR-018 v0.5.0: Import 2.0; Evolution descartado para SaaS |
