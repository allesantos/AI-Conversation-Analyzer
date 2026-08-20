# Wireframe — Tela de conversa (largura full)

> Referência visual para refatorar `conversation-detail`.  
> Canvas interativo: `docs/wireframes/conversation-detail-wireframe.canvas.tsx`  
> Largura alvo: **1280px** (hoje: 860px na página, 1080px no shell).

## Layout (ASCII)

```
┌────────────────────────────────────────────────────────────────────────────── max 1280px ──┐
│ Conversas / Giulia                                                          Wireframe v1 │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ [← Voltar]  Giulia   [4218 msgs] [43 áudios]     [Importar áudios] [Import] [Reanalisar] │
├──────────────────────────────────────────────────────────────────────────┬───────────────┤
│ HERO (3 colunas)                                                         │               │
│ ┌─────────────────────────┬──────────────┬──────────────┐                │  SIDEBAR      │
│ │ NÍVEL DE INTERESSE      │ Métricas     │ Resumo LLM   │                │  340px        │
│ │ MODERADO (grande)       │ msgs, inícios│ parágrafo    │                │               │
│ │ Confiança 79%           │ resp. mediana│              │                │ ▼ Import      │
│ │ barra reciprocidade     │              │              │                │ ▼ Batch áudio │
│ └─────────────────────────┴──────────────┴──────────────┘                │   Perguntar   │
├──────────────────────────────────────────────────────────────────────────┤   Sugestões   │
│ GRÁFICOS (2 colunas, largura total)                                      │               │
│ [ LineChart — evolução interesse ]  [ BarChart — volume semanal ]        │               │
├──────────────────────────────────────────────────────────────────────────┤               │
│ SINAIS (3 colunas)                                                       │               │
│ [ Positivos 5 ]    [ Neutros 4 ]    [ Negativos 2 ]                      │               │
├──────────────────────────────────────────────────────────────────────────┤               │
│ EVIDÊNCIAS (2 colunas)                                                   │               │
│ [ Tabela sinal | observação | ação ]  [ Preview mensagem + inferência ]  │               │
├──────────────────────────────────────────────────────────────────────────┤               │
│ ▼ Timeline de mensagens (colapsada por padrão)                           │               │
└──────────────────────────────────────────────────────────────────────────┴───────────────┘
```

## Mudanças vs. hoje

| Zona | Hoje | Proposta |
|------|------|----------|
| Largura | `max-width: 860px` | 1280px (+ shell 1080→1280) |
| Import | Painel grande no topo | Sidebar colapsável |
| Score | Card pequeno | Hero 2× maior |
| Sinais | Lista vertical | 3 colunas |
| Gráficos | Sparkline mínimo | 2 charts full-width |

## Inspiração

- **Flemm** — hero + upload discreto  
- **Mosaic** — grids e charts  
- **Lucen** — score + confiança  
- **ThreadRecap** — evidências clicáveis  

## Como abrir o Canvas no Cursor

1. **Dentro do Cursor** (não clique o link do chat — o Windows quebra o caminho).
2. `Ctrl + P` → digite `conversation-detail-wireframe.canvas`
3. Abra o arquivo em `docs/wireframes/` ou `canvases/`.
4. No editor, use **Open Canvas** / preview do Cursor (se disponível na sua versão).

Caminho completo no disco:

`C:\Users\Alle\.cursor\projects\e-Projetos-AI-Conversation-Analyzer\canvases\conversation-detail-wireframe.canvas.tsx`

(Copie e cole na barra de endereço do **Abrir arquivo** do Cursor, não do Explorer.)
