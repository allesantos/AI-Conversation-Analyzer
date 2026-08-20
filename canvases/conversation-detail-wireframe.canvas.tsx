import {
  BarChart,
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  CollapsibleSection,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  LineChart,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
  UsageBar,
  useHostTheme,
} from "cursor/canvas";

const PAGE_MAX = 1280;

const timelineCategories = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago"];
const interestSeries = [
  { name: "Score de interesse", data: [42, 48, 51, 55, 58, 62, 68, 71], tone: "info" as const },
];
const volumeSeries = [
  { name: "Mensagens / semana", data: [120, 95, 140, 110, 88, 130, 105, 98], tone: "neutral" as const },
];

const evidenceRows = [
  ["Inicia conversas", "Giulia iniciou 4 das últimas 10 threads", "Ver 3 msgs", "success"],
  ["Respostas elaboradas", "Média 2,3× maior que Alle em áudios transcritos", "Ver 2 msgs", "success"],
  ["Tempo de resposta", "Mediana 47 min (neutro isolado)", "Ver 1 msg", "neutral"],
  ["Evita assuntos", "2 perguntas sem retorno em 30 dias", "Ver 2 msgs", "warning"],
];

export default function ConversationDetailWireframe() {
  const theme = useHostTheme();

  const pageStyle = {
    maxWidth: PAGE_MAX,
    margin: "0 auto",
    width: "100%",
    padding: "0 32px 48px",
  };

  const dashedZone = {
    border: `1px dashed ${theme.stroke.secondary}`,
    borderRadius: 10,
    padding: 16,
    background: theme.fill.quaternary,
  };

  return (
    <Stack gap={20} style={pageStyle}>
      <Row align="center" gap={12} wrap>
        <Text tone="secondary" size="small">
          Conversas / Giulia
        </Text>
        <Spacer />
        <Pill tone="info" size="sm">
          Wireframe v1
        </Pill>
        <Text tone="tertiary" size="small">
          Largura alvo {PAGE_MAX}px · hoje 860px
        </Text>
      </Row>

      <H1>Giulia — Análise de conversa</H1>
      <Text tone="secondary">
        Inspirado em Flemm, Mosaic, Lucen e ThreadRecap. Layout full-width com hierarquia clara:
        score hero → gráficos → sinais → evidências clicáveis.
      </Text>

      <Callout tone="info">
        Objetivo: substituir a coluna única estreita por um dashboard de 2–3 colunas. Import e
        controles secundários ficam colapsáveis ou na sidebar direita.
      </Callout>

      {/* Toolbar */}
      <Card variant="borderless">
        <CardBody>
          <Row align="center" gap={12} wrap>
            <Button variant="ghost">← Voltar</Button>
            <Text weight="semibold">Giulia</Text>
            <Pill tone="neutral" size="sm">
              4.218 msgs
            </Pill>
            <Pill tone="neutral" size="sm">
              43 áudios
            </Pill>
            <Spacer />
            <Button variant="secondary">Importar áudios</Button>
            <Button variant="secondary">Importar .txt / .zip</Button>
            <Button variant="primary">Reanalisar</Button>
          </Row>
        </CardBody>
      </Card>

      {/* Hero row — score + quick stats */}
      <Grid columns="2fr 1fr 1fr" gap={16}>
        <Card>
          <CardHeader>Nível de interesse</CardHeader>
          <CardBody>
            <Row align="end" gap={24}>
              <Stack gap={4}>
                <Text tone="tertiary" size="small">
                  Conclusão calibrada
                </Text>
                <Text weight="bold" style={{ fontSize: 36, lineHeight: 1.1 }}>
                  Moderado
                </Text>
                <Text tone="secondary" size="small">
                  Com base nas evidências disponíveis — não é certeza absoluta.
                </Text>
              </Stack>
              <Stack gap={4}>
                <Stat label="Confiança" value="79%" tone="success" />
                <Stat label="Reciprocidade" value="62/100" tone="info" />
              </Stack>
            </Row>
            <Divider style={{ margin: "16px 0" }} />
            <UsageBar
              total={100}
              topLeftLabel="Balanceamento de iniciativa (últimos 90 dias)"
              topRightLabel="Giulia 58% · Alle 42%"
              segments={[
                { id: "giulia", value: 58, color: "blue" },
                { id: "alle", value: 42, color: "gray" },
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Métricas rápidas</CardHeader>
          <CardBody>
            <Grid columns={2} gap={12}>
              <Stat label="Msgs Giulia" value="2.341" />
              <Stat label="Msgs Alle" value="1.877" />
              <Stat label="Inícios Giulia" value="34" tone="success" />
              <Stat label="Resp. mediana" value="47 min" />
            </Grid>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Resumo (LLM)</CardHeader>
          <CardBody>
            <Text tone="secondary" size="small">
              Nos últimos 30 dias houve aumento de reciprocidade em relação ao período anterior.
              Giulia mantém continuidade em assuntos pessoais e responde áudios com elaboração
              moderada. Sinais negativos isolados — não determinam o resultado sozinhos.
            </Text>
            <Row gap={8} style={{ marginTop: 12 }}>
              <Pill tone="warning" size="sm">
                summary_stale: false
              </Pill>
              <Pill tone="neutral" size="sm">
                from_cache
              </Pill>
            </Row>
          </CardBody>
        </Card>
      </Grid>

      {/* Charts full width */}
      <Grid columns="1.4fr 1fr" gap={16}>
        <Card>
          <CardHeader>Evolução temporal — interesse</CardHeader>
          <CardBody>
            <H3>Evolução temporal — interesse</H3>
            <LineChart
              categories={timelineCategories}
              series={interestSeries}
              height={220}
              yMin={0}
              yMax={100}
              referenceLines={[{ value: 50, label: "Neutro", tone: "neutral" }]}
            />
            <Text tone="tertiary" size="small" style={{ marginTop: 8 }}>
              Fonte: timeline backend · período completo · equivalente ao sparkline do Mosaic
            </Text>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Volume e ritmo</CardHeader>
          <CardBody>
            <H3>Volume e ritmo</H3>
            <BarChart
              categories={["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]}
              series={volumeSeries}
              height={220}
            />
            <Text tone="tertiary" size="small" style={{ marginTop: 8 }}>
              Heatmap hora/dia pode substituir este gráfico na v2 (estilo Flemm)
            </Text>
          </CardBody>
        </Card>
      </Grid>

      {/* Main 2-column: signals + sidebar */}
      <Grid columns="1fr 340px" gap={16} align="start">
        <Stack gap={16}>
          <H2>Sinais</H2>
          <Grid columns={3} gap={12}>
            <Card variant="borderless">
              <CardHeader trailing={<Pill tone="success" size="sm">5</Pill>}>
                Positivos
              </CardHeader>
              <CardBody>
                <Stack gap={10}>
                  <SignalItem title="Inicia conversas" detail="4/10 últimas threads" />
                  <SignalItem title="Faz perguntas" detail="Curiosidade recorrente" />
                  <SignalItem title="Retoma assuntos" detail="3 retomadas espontâneas" />
                </Stack>
              </CardBody>
            </Card>

            <Card variant="borderless">
              <CardHeader trailing={<Pill tone="neutral" size="sm">4</Pill>}>
                Neutros
              </CardHeader>
              <CardBody>
                <Stack gap={10}>
                  <SignalItem title="Tempo de resposta" detail="Mediana 47 min" />
                  <SignalItem title="Tamanho médio" detail="Estável no período" />
                  <SignalItem title="Emojis" detail="Sem tendência clara" />
                </Stack>
              </CardBody>
            </Card>

            <Card variant="borderless">
              <CardHeader trailing={<Pill tone="warning" size="sm">2</Pill>}>
                Negativos
              </CardHeader>
              <CardBody>
                <Stack gap={10}>
                  <SignalItem title="Evita assuntos" detail="2 perguntas ignoradas" />
                  <SignalItem title="Respostas curtas" detail="Padrão pontual" />
                </Stack>
              </CardBody>
            </Card>
          </Grid>

          <H2>Evidências</H2>
          <Grid columns="1fr 1fr" gap={16}>
            <Table
              headers={["Sinal", "Observação", "Ação"]}
              rows={evidenceRows.map((row) => [row[0], row[1], row[2]])}
              rowTone={evidenceRows.map((row) =>
                row[3] === "success"
                  ? "success"
                  : row[3] === "warning"
                    ? "warning"
                    : "neutral",
              )}
            />
            <Card>
              <CardHeader>Preview da mensagem</CardHeader>
              <CardBody>
                <Stack gap={8}>
                  <Row gap={8}>
                    <Pill tone="info" size="sm">
                      Giulia
                    </Pill>
                    <Text tone="tertiary" size="small">
                      18/08/2026 22:14
                    </Text>
                  </Row>
                  <Text>
                    "Amanhã eu te conto melhor, prometo — hoje foi corrido demais"
                  </Text>
                  <Text tone="secondary" size="small" italic>
                    Inferência: pode indicar continuidade de interesse, não confirmação.
                  </Text>
                  <Button variant="secondary">Abrir na timeline</Button>
                </Stack>
              </CardBody>
            </Card>
          </Grid>

          <CollapsibleSection title="Timeline de mensagens" count={4218} defaultOpen={false}>
            <div style={dashedZone}>
              <Text tone="secondary" size="small">
                Lista estilo chat (ThreadRecap) ocupa largura total. Áudios transcritos inline.
                Filtro por participante e tipo. Não competir visualmente com o bloco de análise
                acima — fica colapsado por padrão após primeira análise.
              </Text>
            </div>
          </CollapsibleSection>
        </Stack>

        {/* Right sidebar */}
        <Stack gap={16}>
          <CollapsibleSection
            title="Importar conversa"
            trailing={<Text tone="tertiary" size="small">.txt / .zip</Text>}
            defaultOpen={false}
          >
            <div style={dashedZone}>
              <Text tone="secondary" size="small">
                Drag-and-drop (Flemm). Campo "Seu nome" compacto. Resumo: msgs · áudios
                vinculados.
              </Text>
            </div>
          </CollapsibleSection>

          <Card>
            <CardHeader>Importar áudios (batch)</CardHeader>
            <CardBody>
              <Stack gap={10}>
                <Text tone="secondary" size="small">
                  Fluxo Giulia: .txt + pasta Android. Autor fallback + multi-select .opus.
                </Text>
                <Button variant="secondary">Selecionar arquivos</Button>
                <Pill tone="success" size="sm">
                  43 importados
                </Pill>
              </Stack>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>Perguntar sobre o histórico</CardHeader>
            <CardBody>
              <Stack gap={10}>
                <div
                  style={{
                    ...dashedZone,
                    minHeight: 72,
                    padding: 12,
                  }}
                >
                  <Text tone="tertiary" size="small">
                    "Ela mencionou encontro nas últimas 2 semanas?"
                  </Text>
                </div>
                <Button variant="primary">Perguntar</Button>
              </Stack>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>Sugestões de resposta</CardHeader>
            <CardBody>
              <Stack gap={8}>
                <SuggestionChip label="Natural" preview="Faz sentido, me conta quando der" />
                <SuggestionChip label="Direta" preview="Beleza — qual dia funciona?" />
                <SuggestionChip label="Conservadora" preview="Sem pressa, quando puder" />
              </Stack>
            </CardBody>
          </Card>
        </Stack>
      </Grid>

      <Divider />

      <H2>Mapa: wireframe → implementação Angular</H2>
      <Table
        headers={["Zona", "Componente atual", "Mudança proposta"]}
        rows={[
          ["Largura", "max-width 860px", "1280px (ou 100% até 1400px)"],
          ["Hero score", "Card pequeno empilhado", "Grid 3 colunas — destaque visual"],
          ["Gráficos", "Sparkline mínimo", "LineChart + heatmap/volume full width"],
          ["Sinais", "Lista vertical longa", "3 colunas Pos / Neutro / Neg"],
          ["Evidências", "Lista + preview ok", "Tabela + preview lado a lado"],
          ["Import", "Painel grande no topo", "Sidebar colapsável ou modal"],
          ["Timeline msgs", "Abaixo de tudo", "Colapsável — foco na análise"],
        ]}
        striped
      />

      <Text tone="tertiary" size="small">
        Próximo passo sugerido: refatorar só conversation-detail (HTML/SCSS) sem mudar backend.
        Fase visual separada da 9b (wizard).
      </Text>
    </Stack>
  );
}

function SignalItem({ title, detail }: { title: string; detail: string }) {
  return (
    <Stack gap={2}>
      <Text weight="semibold" size="small">
        {title}
      </Text>
      <Text tone="secondary" size="small">
        {detail}
      </Text>
    </Stack>
  );
}

function SuggestionChip({ label, preview }: { label: string; preview: string }) {
  return (
    <Stack gap={4}>
      <Pill tone="neutral" size="sm">
        {label}
      </Pill>
      <Text tone="secondary" size="small">
        {preview}
      </Text>
    </Stack>
  );
}
