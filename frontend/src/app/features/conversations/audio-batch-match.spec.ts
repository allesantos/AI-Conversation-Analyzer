import { ConversationMessage } from '../../core/models/api.models';
import {
  BATCH_MATCH_TOLERANCE_SECONDS,
  audioFileKey,
  buildBatchUploadReviewItems,
  isLastModifiedCorrupted,
  matchAudioFilesToMessages,
  parseWhatsAppFilenameDate,
  parseWhatsAppFilenameSequence,
} from './audio-batch-match';

function hiddenMessage(id: string, timestamp: string): ConversationMessage {
  return {
    id,
    sender_id: 'sender-1',
    sender_name: 'Marina',
    timestamp,
    type: 'MEDIA_OCULTA',
    content: '<Mídia oculta>',
    metadata: {},
  };
}

function file(name: string, lastModified: number): File {
  return new File(['audio'], name, {
    type: 'audio/opus',
    lastModified,
  });
}

describe('audio-batch-match', () => {
  const baseMs = new Date('2026-08-18T14:30:00.000Z').getTime();

  it('matches file and message with exact timestamp', () => {
    const matches = matchAudioFilesToMessages(
      [{ fileKey: 'a', fileName: 'a.opus', lastModifiedMs: baseMs }],
      [{ messageId: 'msg-1', timestampMs: baseMs }],
    );

    expect(matches.get('a')?.messageId).toBe('msg-1');
    expect(matches.get('a')?.diffSeconds).toBe(0);
  });

  it('matches within tolerance', () => {
    const matches = matchAudioFilesToMessages(
      [{ fileKey: 'a', fileName: 'a.opus', lastModifiedMs: baseMs + 12_000 }],
      [{ messageId: 'msg-1', timestampMs: baseMs }],
      BATCH_MATCH_TOLERANCE_SECONDS,
    );

    expect(matches.get('a')?.messageId).toBe('msg-1');
    expect(matches.get('a')?.diffSeconds).toBe(12);
  });

  it('does not match above tolerance', () => {
    const matches = matchAudioFilesToMessages(
      [{ fileKey: 'a', fileName: 'a.opus', lastModifiedMs: baseMs + 400_000 }],
      [{ messageId: 'msg-1', timestampMs: baseMs }],
      BATCH_MATCH_TOLERANCE_SECONDS,
    );

    expect(matches.size).toBe(0);
  });

  it('assigns closest pairs without reusing messages in a dispute', () => {
    const msg1Ms = baseMs;
    const msg2Ms = baseMs + 30_000;

    const matches = matchAudioFilesToMessages(
      [
        { fileKey: 'f1', fileName: '1.opus', lastModifiedMs: baseMs + 5_000 },
        { fileKey: 'f2', fileName: '2.opus', lastModifiedMs: baseMs + 35_000 },
      ],
      [
        { messageId: 'msg-1', timestampMs: msg1Ms },
        { messageId: 'msg-2', timestampMs: msg2Ms },
      ],
    );

    expect(matches.get('f1')?.messageId).toBe('msg-1');
    expect(matches.get('f2')?.messageId).toBe('msg-2');
  });

  it('buildBatchUploadReviewItems marks unmatched files as without correspondence', () => {
    const items = buildBatchUploadReviewItems(
      [file('far.opus', baseMs + 600_000)],
      [hiddenMessage('msg-1', new Date(baseMs).toISOString())],
    );

    expect(items).toHaveSize(1);
    expect(items[0].withinTolerance).toBeFalse();
    expect(items[0].attach).toBeFalse();
    expect(items[0].selectedMessageId).toBeNull();
  });

  it('uses stable file keys for review items', () => {
    const audio = file('clip.opus', baseMs);
    const items = buildBatchUploadReviewItems(
      [audio],
      [hiddenMessage('msg-1', new Date(baseMs).toISOString())],
    );

    expect(items[0].id).toContain(audioFileKey(audio));
  });

  it('extracts date and sequence from WhatsApp filenames', () => {
    expect(parseWhatsAppFilenameDate('PTT-20260818-WA0007.opus')).toBe('2026-08-18');
    expect(parseWhatsAppFilenameDate('AUD-20260101-WA0123.opus')).toBe('2026-01-01');
    expect(parseWhatsAppFilenameDate('random.opus')).toBeNull();
    expect(parseWhatsAppFilenameSequence('PTT-20260818-WA0007.opus')).toBe(7);
  });

  it('detects corrupted lastModified when date differs from filename', () => {
    const corruptedMs = new Date('2026-08-19T15:00:00').getTime();
    expect(isLastModifiedCorrupted('PTT-20260818-WA0001.opus', corruptedMs)).toBeTrue();
    expect(isLastModifiedCorrupted('PTT-20260818-WA0001.opus', baseMs)).toBeFalse();
  });

  it('matches WhatsApp files by WA index even when timestamp is far off', () => {
    const dayStartMs = new Date('2026-08-18T10:00:00.000Z').getTime();

    const matches = matchAudioFilesToMessages(
      [
        {
          fileKey: 'f1',
          fileName: 'PTT-20260818-WA0000.opus',
          lastModifiedMs: dayStartMs + 400_000,
        },
      ],
      [{ messageId: 'msg-1', timestampMs: dayStartMs }],
      BATCH_MATCH_TOLERANCE_SECONDS,
    );

    expect(matches.get('f1')?.messageId).toBe('msg-1');
    expect(matches.get('f1')?.matchedByFilenameFallback).toBeTrue();
  });

  it('matches corrupted files by filename day and WA sequence order', () => {
    const dayStartMs = new Date('2026-08-18T10:00:00.000Z').getTime();
    const corruptedMs = new Date('2026-08-19T15:00:00').getTime();

    const matches = matchAudioFilesToMessages(
      [
        {
          fileKey: 'f1',
          fileName: 'PTT-20260818-WA0001.opus',
          lastModifiedMs: corruptedMs,
        },
        {
          fileKey: 'f2',
          fileName: 'PTT-20260818-WA0000.opus',
          lastModifiedMs: corruptedMs,
        },
      ],
      [
        { messageId: 'msg-1', timestampMs: dayStartMs },
        { messageId: 'msg-2', timestampMs: dayStartMs + 60_000 },
      ],
    );

    expect(matches.get('f2')?.messageId).toBe('msg-1');
    expect(matches.get('f1')?.messageId).toBe('msg-2');
    expect(matches.get('f2')?.matchedByFilenameFallback).toBeTrue();
    expect(matches.get('f1')?.matchedByFilenameFallback).toBeTrue();
  });

  it('buildBatchUploadReviewItems flags filename fallback matches', () => {
    const dayStartMs = new Date('2026-08-18T10:00:00.000Z').getTime();
    const corruptedMs = new Date('2026-08-19T15:00:00').getTime();

    const items = buildBatchUploadReviewItems(
      [file('PTT-20260818-WA0000.opus', corruptedMs)],
      [hiddenMessage('msg-1', new Date(dayStartMs).toISOString())],
    );

    expect(items[0].selectedMessageId).toBe('msg-1');
    expect(items[0].matchedByFilenameFallback).toBeTrue();
    expect(items[0].attach).toBeTrue();
  });
});
