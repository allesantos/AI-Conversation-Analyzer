# API

Base URL de desenvolvimento: `http://localhost:18000`

OpenAPI: `/docs` · ReDoc: `/redoc` · Schema: `/openapi.json`

Autenticação: header `Authorization: Bearer <token>` (JWT).

---

## Saúde

### `GET /health`

Sem autenticação. `{ "status": "ok" }`

### `GET /ready`

Sem autenticação. Executa `SELECT 1` no banco. `{ "status": "ready" }`

---

## Auth

### `POST /api/v1/auth/register`

```json
{ "email": "ana@example.com", "password": "password123", "terms_accepted": true }
```

**201** — `{ "access_token": "<jwt>", "token_type": "bearer", "user": {...} }`

Erros: `409` e-mail duplicado · `422` termos não aceitos.

### `POST /api/v1/auth/login`

```json
{ "email": "ana@example.com", "password": "password123" }
```

**200** — mesmo formato do register. Erro: `401`.

### `GET /api/v1/auth/me`

Requer JWT. Retorna o usuário autenticado.

---

## Dashboard

### `GET /api/v1/dashboard`

Resumo da conta autenticada:

- `total_conversations` / `analyzed_conversations`
- `interest_distribution` (contagem por nível MUITO_BAIXO…MUITO_ALTO)
- `recent` — até 8 conversas com nível, confiança, msgs e datas
- `usage` — totais de consumo de IA (sem lista detalhada de records)

**200** — objeto agregado. Requer JWT.

---

## Conversas

Isolamento: todas as queries filtram por `user_id`. Recurso de outro usuário → **404**.

### `POST /api/v1/conversations`

```json
{ "title": "Conversa com João" }
```

**201** — objeto da conversa.

### `GET /api/v1/conversations`

**200** — `{ "items": [...], "total": N }`

### `GET /api/v1/conversations/{id}?offset=0&limit=50`

**200** — detalhe com participantes, mensagens paginadas e contagem total.

### `POST /api/v1/conversations/{id}/import`

Multipart: `file` (`.txt` ou `.zip` do WhatsApp) + `owner_name` opcional.

**Formatos:**

| Formato | Conteúdo |
|---------|----------|
| `.txt` | Apenas mensagens de texto (comportamento original) |
| `.zip` | Chat `.txt` + arquivos de áudio; áudios são pareados com `<Mídia oculta>` e transcrições iniciadas automaticamente |

**200** — resumo de importação. Campos adicionais no `.zip`:

| Campo | Descrição |
|-------|-----------|
| `import_format` | `"txt"` ou `"zip"` |
| `audio_files_found` | Áudios encontrados no pacote |
| `audio_files_matched` | Áudios vinculados a mensagens `<Mídia oculta>` |
| `audio_transcriptions_started` | Jobs de transcrição enfileirados |

**Reimportação:** substitui mensagens e participantes da conversa. Se já existir uma análise salva, o backend reconcilia automaticamente:

- **Mesmo conteúdo analisável** (timestamp, remetente, tipo, texto) → mantém resumo do LLM, remapeia evidências para os novos IDs de mensagem, `summary_stale=false`.
- **Conteúdo alterado** → recalcula métricas e sinais localmente (sem LLM), marca `summary_stale=true`; o resumo só é atualizado se o usuário chamar `/analyze` de novo.

O fingerprint de cache ignora UUIDs de mensagem/participante — reimportar o mesmo `.txt` não invalida o resumo salvo.

### `DELETE /api/v1/conversations/{id}`

**204** — exclusão completa (conversa, mensagens, análises, embeddings, áudio, sugestões).

---

## Análise

### `POST /api/v1/conversations/{id}/analyze`

Gera análise completa (métricas, resumo, sinais de interesse, reciprocidade, evidências).

**200** — resultado completo. **202** — embeddings em processamento (polling necessário). **429** — rate limit.

**Cache de LLM:** se o conteúdo analisável não mudou desde a última análise com LLM, a resposta é servida do banco **sem nova chamada à API OpenAI**. Campos relevantes na resposta:

| Campo | Descrição |
|-------|-----------|
| `from_cache` | `true` quando nenhum token de LLM foi consumido nesta requisição |
| `summary_stale` | `true` quando métricas/sinais foram recalculados localmente, mas o resumo textual ainda reflete uma versão anterior do conteúdo |

Situações típicas:

| Ação | LLM? |
|------|------|
| Primeira análise | Sim |
| Reanalisar sem mudanças | Não (`from_cache: true`) |
| Reimportar mesmo `.txt` | Não (reconciliação no import) |
| Reanalisar após reimport idêntico | Não |
| Excluir áudio `analysis_only` | Não (refresh local; `summary_stale: true`) |
| Reanalisar após exclusão de áudio | Sim (se quiser resumo atualizado) |
| Reimportar `.txt` com conteúdo diferente | Não no import; `/analyze` gasta LLM se quiser novo resumo |

Análises gravadas antes da migração para fingerprint semântico podem exigir **uma** reanálise para normalizar o cache; depois disso, reimports idênticos passam a reutilizar o resumo.

### `GET /api/v1/conversations/{id}/analysis`

**200** — última análise salva (inclui evidências, observações, inferências, `summary_stale`, `from_cache: false`). **404** se nunca analisou.

### `GET /api/v1/conversations/{id}/timeline`

**200** — períodos temporais (7d/30d/90d/completo) com score, sinais e observações.

### `POST /api/v1/conversations/{id}/ask`

```json
{ "question": "Quem inicia mais as conversas?" }
```

**200** — resposta com observações e inferências. **202** — embeddings pendentes. **429** — rate limit.

---

## Sugestões de resposta

### `POST /api/v1/conversations/{id}/suggestions`

Body: `{ "incoming_message": "texto colado do WhatsApp" }` (1–4000 caracteres).

Gera 4 sugestões (NATURAL, DIVERTIDA, DIRETA, CONSERVADORA) para responder à mensagem colada, usando o histórico importado só como contexto (métricas + RAG quando aplicável). `based_on_message_id` fica `null`.

**200** — sugestões + `incoming_message` + provider/model. **400** — histórico vazio ou mensagem em branco. **429** — rate limit.

---

## Áudio

### `POST /api/v1/conversations/{id}/audio`

Multipart: `file` (áudio) + `message_id` (UUID). Extensões aceitas: `.opus .ogg .mp3 .m4a .wav .aac .amr`.

**202** — transcrição enfileirada. Polling via GET abaixo.

### `GET /api/v1/conversations/{id}/audio/{transcription_id}`

**200** — status da transcrição (PENDING/PROCESSING/COMPLETED/FAILED), texto transcrito quando pronto.

---

## Uso de IA

### `GET /api/v1/usage`

**200** — consumo acumulado do usuário autenticado.

```json
{
  "total_records": 12,
  "total_input_tokens": 45000,
  "total_output_tokens": 8000,
  "total_audio_seconds": 120.5,
  "total_estimated_cost": 0.0234,
  "records": [...]
}

```

---

## Cabeçalhos

| Header | Descrição |
|--------|-----------|
| `Authorization` | `Bearer <jwt>` |
| `X-Request-ID` | Ecoado na resposta (gerado se ausente) |

---

## Rate Limiting

Endpoints de IA (`/analyze`, `/ask`, `/suggestions`) têm rate limiting por usuário: 5 requisições em burst, reposição de ~12/min. Erro: **429** com mensagem descritiva.
