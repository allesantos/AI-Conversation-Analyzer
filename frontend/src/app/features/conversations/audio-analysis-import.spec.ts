import { ConversationMessage } from '../../core/models/api.models';
import {
  buildAnalysisImportPlan,
  findAnalysisOnlyForTimelineMessage,
  isAnalysisOnlyMessage,
  isTimelineHiddenMediaMessage,
  mergeTimelineMessageWithTranscription,
  messageNeedsTranscriptionContent,
  sortAudioFilesForImport,
  uniqueMessageIds,
} from './audio-analysis-import';

function file(name: string, lastModified: number): File {
  return new File(['audio'], name, { type: 'audio/opus', lastModified });
}

function hiddenMessage(
  id: string,
  timestamp: string,
  senderId: string,
  senderName: string,
): ConversationMessage {
  return {
    id,
    sender_id: senderId,
    sender_name: senderName,
    timestamp,
    type: 'MEDIA_OCULTA',
    content: '<Mídia oculta>',
    metadata: {},
  };
}

describe('audio-analysis-import', () => {
  const giuliaId = 'participant-giulia';
  const alleId = 'participant-alle';
  const participants = [
    { id: alleId, name: 'Alle', role: 'OWNER' as const },
    { id: giuliaId, name: 'Giulia', role: 'OTHER' as const },
  ];

  it('sorts WhatsApp files by date then WA index', () => {
    const sorted = sortAudioFilesForImport([
      file('PTT-20260819-WA0001.opus', 0),
      file('PTT-20260818-WA0002.opus', 0),
      file('PTT-20260818-WA0000.opus', 0),
    ]);

    expect(sorted.map((item) => item.name)).toEqual([
      'PTT-20260818-WA0000.opus',
      'PTT-20260818-WA0002.opus',
      'PTT-20260819-WA0001.opus',
    ]);
  });

  it('assigns sender from matched hidden media messages', () => {
    const dayStartMs = new Date('2026-08-18T10:00:00.000Z').getTime();
    const messages = [
      hiddenMessage('msg-g', new Date(dayStartMs).toISOString(), giuliaId, 'Giulia'),
      hiddenMessage(
        'msg-a',
        new Date(dayStartMs + 60_000).toISOString(),
        alleId,
        'Alle',
      ),
    ];

    const items = buildAnalysisImportPlan(
      [
        file('PTT-20260818-WA0000.opus', dayStartMs),
        file('PTT-20260818-WA0001.opus', dayStartMs + 60_000),
      ],
      messages,
      giuliaId,
      participants,
    );

    expect(items[0].senderName).toBe('Giulia');
    expect(items[0].matchedFromChat).toBeTrue();
    expect(items[0].matchedMessageId).toBe('msg-g');
    expect(items[1].senderName).toBe('Alle');
    expect(items[1].matchedFromChat).toBeTrue();
    expect(items[1].matchedMessageId).toBe('msg-a');
  });

  it('uses fallback sender when chat match is missing', () => {
    const items = buildAnalysisImportPlan(
      [file('unknown.opus', Date.now())],
      [],
      giuliaId,
      participants,
    );

    expect(items[0].senderName).toBe('Giulia');
    expect(items[0].matchedFromChat).toBeFalse();
    expect(items[0].matchedMessageId).toBeNull();
  });

  it('skips files already transcribed by filename', () => {
    const messages = [
      {
        id: 'msg-audio',
        sender_id: giuliaId,
        sender_name: 'Giulia',
        timestamp: '2026-08-18T10:00:00.000Z',
        type: 'AUDIO' as const,
        content: 'Já transcrito',
        metadata: {
          analysis_only: true,
          transcribed: true,
          filename: 'PTT-20260818-WA0000.opus',
        },
      },
      hiddenMessage('msg-new', '2026-08-20T15:25:00.000Z', giuliaId, 'Giulia'),
    ];

    const items = buildAnalysisImportPlan(
      [
        file('PTT-20260818-WA0000.opus', Date.parse('2026-08-18T10:00:00.000Z')),
        file('PTT-20260820-WA0000.opus', Date.parse('2026-08-20T15:25:00.000Z')),
      ],
      messages,
      giuliaId,
      participants,
    );

    expect(items[0].status).toBe('skipped');
    expect(items[1].status).toBe('pending');
    expect(items[1].matchedMessageId).toBe('msg-new');
  });

  it('detects analysis-only messages', () => {
    expect(isAnalysisOnlyMessage({ analysis_only: true })).toBeTrue();
    expect(isAnalysisOnlyMessage({ uploaded: true })).toBeFalse();
  });

  it('detects when analysis-only message still needs transcription content', () => {
    expect(
      messageNeedsTranscriptionContent({
        id: 'msg-1',
        sender_id: giuliaId,
        sender_name: 'Giulia',
        timestamp: '2026-08-18T10:00:00Z',
        type: 'AUDIO',
        content: 'Áudio enviado pelo usuário',
        metadata: { analysis_only: true, transcription_id: 'tx-1' },
      }),
    ).toBeTrue();
    expect(
      messageNeedsTranscriptionContent({
        id: 'msg-2',
        sender_id: giuliaId,
        sender_name: 'Giulia',
        timestamp: '2026-08-18T10:00:00Z',
        type: 'AUDIO',
        content: 'Texto transcrito.',
        metadata: { analysis_only: true, transcription_id: 'tx-2' },
      }),
    ).toBeFalse();
  });

  it('deduplicates evidence message ids for repeated replies', () => {
    expect(uniqueMessageIds(['a', 'b', 'a', 'c', 'b'])).toEqual(['a', 'b', 'c']);
  });

  it('matches analysis-only audio to timeline hidden media by timestamp', () => {
    const timestamp = '2026-08-18T12:26:00.000Z';
    const hidden = {
      id: 'timeline-hidden',
      sender_id: giuliaId,
      sender_name: 'Giulia',
      timestamp,
      type: 'MEDIA_OCULTA' as const,
      content: '<Mídia oculta>',
      metadata: { hidden_media: true },
    };
    const analysisOnly = {
      id: 'analysis-audio',
      sender_id: giuliaId,
      sender_name: 'Giulia',
      timestamp,
      type: 'AUDIO' as const,
      content: 'Transcrição do áudio importado.',
      metadata: { analysis_only: true },
    };

    expect(isTimelineHiddenMediaMessage(hidden)).toBeTrue();
    expect(findAnalysisOnlyForTimelineMessage(hidden, [analysisOnly])?.id).toBe('analysis-audio');
  });

  it('merges transcription into timeline hidden media message', () => {
    const timestamp = '2026-08-18T12:26:00.000Z';
    const hidden = {
      id: 'timeline-hidden',
      sender_id: giuliaId,
      sender_name: 'Giulia',
      timestamp,
      type: 'MEDIA_OCULTA' as const,
      content: '<Mídia oculta>',
      metadata: { hidden_media: true },
    };
    const analysisOnly = {
      id: 'analysis-audio',
      sender_id: giuliaId,
      sender_name: 'Giulia',
      timestamp,
      type: 'AUDIO' as const,
      content: 'Transcrição do áudio importado.',
      metadata: { analysis_only: true },
    };

    const merged = mergeTimelineMessageWithTranscription(hidden, [analysisOnly]);
    expect(merged.content).toBe('Transcrição do áudio importado.');
    expect(merged.type).toBe('AUDIO');
    expect(merged.metadata?.['transcribed']).toBeTrue();
  });
});
