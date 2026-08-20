# Projetos de Referência e Licenças

> Documento da **Fase 0** — AI Conversation Analyzer  
> Data: 2026-08-19

Este documento registra a análise de projetos externos consultados durante a Fase 0, incluindo licenças, componentes estudados e decisões sobre reutilização de código.

---

## Resumo Executivo

| Projeto | Licença | Uso comercial SaaS | Código reutilizado | Decisão |
|---------|---------|-------------------|-------------------|---------|
| [ChatLab](https://github.com/ChatLab/ChatLab) | **AGPL-3.0** | ❌ Restrito | Nenhum | Estudar arquitetura apenas |
| [WhatsVector](https://github.com/samirsalman/whatsvector) | **MIT** | ✅ Permitido | Nenhum (implementação própria) | Estudar padrões; implementar do zero |
| [WhatsApp Audio Transcriber](https://github.com/LEstradioto/whatsapp-audio-transcriber) | **MIT** | ✅ Permitido | Nenhum | Estudar abstração de providers apenas |

---

## 1. ChatLab

| Campo | Valor |
|-------|-------|
| **URL** | https://github.com/ChatLab/ChatLab |
| **Autor** | hellodigua |
| **Licença** | GNU Affero General Public License v3.0 (AGPL-3.0) |
| **Stars** | ~7.200 |
| **Tipo** | Desktop app (Electron) local-first |
| **Última análise** | v0.17.5 / main (2026-08) |

### O que o projeto faz

- Analisador local de históricos de chat com IA
- Suporta WhatsApp, LINE, QQ, Discord, Instagram, Telegram, iMessage, Google Chat
- Importação via export `.txt` do WhatsApp (entre outros formatos)
- Parser streaming para conversas com milhões de mensagens
- Métricas visuais: frequência, heatmaps, rankings, padrões temporais
- Agente IA com Function Calling (24+ ferramentas) sobre dados estruturados
- Normalização cross-platform para modelo unificado (ChatLab Format)
- Privacidade: dados locais, desensibilização antes de enviar ao LLM

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Desktop | Electron |
| Frontend | Vue 3 + Nuxt UI + Tailwind CSS |
| Runtime | Node.js + TypeScript (pnpm monorepo) |
| Persistência | SQLite local + índices FTS |
| Vetores | SQLite-vec / busca semântica local |
| IA | Agent + Tool Calling (LangChain.js) |
| Workers | Worker threads para import/query |

### Componentes analisados

| Componente | Localização (referência) | Relevância para nós |
|-----------|-------------------------|---------------------|
| Parser WhatsApp | `parser/formats/*` | Alta — edge cases de formato |
| Stream import | `streamImport.ts`, `incrementalImport.ts` | Alta — conversas grandes |
| Modelo normalizado | ChatLab Format v0.0.2 | Média — inspiração de schema |
| Query/metrics | `worker/query/*` | Alta — métricas objetivas |
| Agent + tools | `electron/main/ai/` | Alta — padrão de orquestração |
| Desensibilização | docs/ai/why-chatlab | Alta — privacidade/LGPD |

### Análise de licença (AGPL-3.0)

**Obrigações da AGPL-3.0:**
- Disponibilizar código-fonte completo ao distribuir o software
- Software derivado deve usar a mesma licença
- **Cláusula de rede (Section 13):** usuários que interagem via rede (SaaS) têm direito ao código-fonte

**Impacto no AI Conversation Analyzer:**
- ❌ **NÃO copiar código** para o núcleo proprietário do produto
- ❌ **NÃO usar como dependência** em serviço SaaS fechado
- ✅ **Estudar arquitetura**, ideias e padrões
- ✅ **Implementação própria** inspirada nos conceitos (sem copiar código)

### Decisão

| Ação | Status |
|------|--------|
| Copiar parser WhatsApp | ❌ Proibido — implementar `WhatsAppParser` próprio |
| Copiar métricas/query | ❌ Proibido — implementar `interest_engine/` próprio |
| Estudar streaming parser | ✅ Permitido |
| Estudar agent + tools pattern | ✅ Permitido |
| Estudar ChatLab Format | ✅ Permitido (spec pública, não código) |
| Estudar desensibilização | ✅ Permitido |

---

## 2. WhatsVector

| Campo | Valor |
|-------|-------|
| **URL** | https://github.com/samirsalman/whatsvector |
| **Autor** | Samir Salman |
| **Licença** | MIT License |
| **Stars** | ~1 |
| **Tipo** | CLI Python |
| **Versão analisada** | 0.1.0 |

### O que o projeto faz

- Vectoriza exportações `.txt` do WhatsApp
- Armazena embeddings no Qdrant
- Agente LangGraph para chat semântico sobre conversas
- Suporte a múltiplos LLM providers (OpenAI, Groq)
- Filtros por remetente e intervalo de datas

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11+ |
| CLI | Typer |
| Validação | Pydantic v2 |
| Agente | LangGraph 1.0.3 |
| Vetores | Qdrant + FastEmbed |
| Embeddings | jinaai/jina-embeddings-v3 (default) |

### Componentes analisados

| Componente | Arquivo | Relevância |
|-----------|---------|-----------|
| Parser WhatsApp | `whatsvector/types/data.py` | Média — formato limitado |
| Data loader abstrato | `whatsvector/data/loaders/loader.py` | Alta — padrão de abstração |
| Agente LangGraph | `whatsvector/agent/agent.py` | Alta — referência de agente RAG |
| Tool de busca | `whatsvector/agent/tools.py` | Alta — padrão retrieval |
| Config por profile | `whatsvector/config/config_file.py` | Média |

### Limitações identificadas

- Parser suporta **apenas** formato `[DD/MM/YY, HH:MM:SS] Sender: message`
- **Não suporta** formato brasileiro `DD/MM/YYYY HH:MM - Nome: mensagem`
- **Não trata** mensagens multilinha
- **Sem testes** unitários
- **Sem métricas** objetivas ou análise de reciprocidade
- Performance ruim em datasets grandes sem GPU (nota no próprio TODO)
- Projeto imaturo (v0.1.0, 1 star)

### Análise de licença (MIT)

**Permite:**
- Uso comercial ✅
- Modificação ✅
- Distribuição ✅
- Uso privado ✅

**Obrigações:**
- Incluir copyright e licença MIT em cópias/distribuições

### Decisão

| Ação | Status |
|------|--------|
| Copiar parser | ⚠️ Possível legalmente, mas **não recomendado** — parser incompleto |
| Copiar loader/agent | ⚠️ Possível, mas stack diferente (Qdrant vs pgvector) |
| Estudar abstração DataLoader | ✅ |
| Estudar padrão LangGraph agent + tools | ✅ |
| Estudar rich_content para embeddings | ✅ |
| Implementar do zero | ✅ **Recomendado** — adaptar à nossa stack |

---

## 3. WhatsApp Audio Transcriber

| Campo | Valor |
|-------|-------|
| **URL** | https://github.com/LEstradioto/whatsapp-audio-transcriber |
| **Autor** | Luan Estradioto (LEstradioto) |
| **Licença** | MIT License |
| **Stars** | ~4 |
| **Tipo** | Chrome Extension (WhatsApp Web) |

### O que o projeto faz

- Injeta botão "Transcrever" em mensagens de áudio no WhatsApp Web
- Suporta providers: Groq, OpenAI, Local (Transformers.js no browser)
- Cache de transcrições por 3 dias (`chrome.storage.local`)
- Modo local experimental com Whisper via ONNX no browser

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Extensão | Chrome Manifest V3 |
| Scripts | JavaScript vanilla |
| API local | Transformers.js + ONNX Runtime Web |
| Providers remotos | Groq API, OpenAI API (`/audio/transcriptions`) |

### Componentes analisados

| Componente | Arquivo | Relevância |
|-----------|---------|-----------|
| Abstração de provider | `background.js` → `transcribeWithProvider()` | Alta |
| Config de modelos | `popup.js`, `DEFAULT_SETTINGS` | Média |
| Engine local | `local-engine.js` | Baixa — browser-only, não aplicável ao backend |
| Injeção WhatsApp Web | `injected.js`, `content.js` | ❌ Não aplicável |

### Análise de licença (MIT)

Compatível com SaaS proprietário. Dependências bundled:
- Transformers.js — Apache-2.0 ✅
- onnxruntime-web — MIT ✅

### Decisão

| Ação | Status |
|------|--------|
| Copiar injeção WhatsApp Web | ❌ Fora de escopo (MVP usa upload, não integração) |
| Copiar engine local browser | ❌ Backend usará Whisper API |
| Estudar padrão multi-provider | ✅ Inspirar `TranscriptionProvider` |
| Estudar endpoints OpenAI-compatible | ✅ Groq/OpenAI usam mesmo formato |
| Implementar do zero | ✅ **Recomendado** — abstração Python no backend |

---

## 4. Matriz de Compatibilidade de Licenças

| Licença | Uso comercial | Modificação | SaaS fechado | Copiar código | Estudar arquitetura |
|---------|--------------|-------------|--------------|---------------|---------------------|
| AGPL-3.0 (ChatLab) | ⚠️ Com restrições | ✅ | ❌ Exige source | ❌ | ✅ |
| MIT (WhatsVector) | ✅ | ✅ | ✅ | ✅ (com atribuição) | ✅ |
| MIT (Audio Transcriber) | ✅ | ✅ | ✅ | ✅ (com atribuição) | ✅ |

---

## 5. Riscos de Licença Identificados

| Risco | Severidade | Mitigação |
|-------|-----------|-----------|
| Copiar acidentalmente código AGPL do ChatLab | **Alta** | Implementação 100% própria; documentar inspirações sem copiar |
| Reutilizar parser MIT incompleto do WhatsVector | **Média** | Parser próprio com testes extensivos para formatos BR |
| Dependência de libs com licença copyleft | **Baixa** | Auditar dependências antes de adicionar (uv/pnpm) |
| Transformers.js/ONNX no backend | **N/A** | Não aplicável — backend usará Whisper API |

---

## 6. Registro de Decisões de Reutilização

### O que REUTILIZAR (conceitos/padrões, não código)

1. **ChatLab:** streaming parser, modelo normalizado, agent + tools, métricas antes do LLM, desensibilização
2. **WhatsVector:** abstração de DataLoader, LangGraph agent + retrieval tool, rich content para embeddings
3. **Audio Transcriber:** abstração multi-provider de transcrição, endpoints OpenAI-compatible

### O que NÃO REUTILIZAR

1. **Qualquer código do ChatLab** (AGPL-3.0)
2. **Parser do WhatsVector** (incompleto para formatos BR)
3. **Injeção WhatsApp Web** do Audio Transcriber (fora de escopo MVP)
4. **Qdrant como store principal** (spec define pgvector)
5. **Electron/Vue** do ChatLab (spec define Angular + FastAPI)

---

## Histórico de Revisões

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-08-19 | 0.1.0 | Análise inicial — Fase 0 |
