import { ConversationMessage } from '../../core/models/api.models';

export const BATCH_MATCH_TOLERANCE_SECONDS = 5 * 60;

const WHATSAPP_FILENAME_RE = /^(PTT|AUD|IMG|VID)-(\d{8})-WA(\d+)\./i;

export type BatchUploadStatus = 'pending' | 'uploading' | 'completed' | 'failed' | 'skipped';

export interface AudioMatchCandidate {
  messageId: string;
  timestampMs: number;
}

export interface AudioFileInput {
  fileKey: string;
  fileName: string;
  lastModifiedMs: number;
}

export interface AudioMatchResult {
  messageId: string;
  diffSeconds: number;
  matchedByFilenameFallback?: boolean;
}

export interface BatchUploadReviewItem {
  id: string;
  file: File;
  fileName: string;
  lastModifiedMs: number;
  suggestedMessageId: string | null;
  selectedMessageId: string | null;
  diffSeconds: number | null;
  withinTolerance: boolean;
  attach: boolean;
  matchedByFilenameFallback: boolean;
  status: BatchUploadStatus;
  errorMessage: string | null;
}

export function audioFileKey(file: File): string {
  return `${file.name}::${file.lastModified}::${file.size}`;
}

export function isHiddenMediaCandidate(message: ConversationMessage): boolean {
  return message.type === 'MEDIA_OCULTA' && message.metadata?.['transcribed'] !== true;
}

export function messageTimestampMs(message: ConversationMessage): number {
  return new Date(message.timestamp).getTime();
}

export function parseWhatsAppFilenameDate(fileName: string): string | null {
  const match = WHATSAPP_FILENAME_RE.exec(fileName);
  if (!match) {
    return null;
  }
  const raw = match[2];
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

export function parseWhatsAppFilenameSequence(fileName: string): number | null {
  const match = WHATSAPP_FILENAME_RE.exec(fileName);
  if (!match) {
    return null;
  }
  return Number.parseInt(match[3], 10);
}

export function isWhatsAppMediaFilename(fileName: string): boolean {
  return WHATSAPP_FILENAME_RE.test(fileName);
}

export function dateKeyFromMs(timestampMs: number): string {
  const date = new Date(timestampMs);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export function isLastModifiedCorrupted(fileName: string, lastModifiedMs: number): boolean {
  const filenameDate = parseWhatsAppFilenameDate(fileName);
  if (!filenameDate) {
    return false;
  }
  return dateKeyFromMs(lastModifiedMs) !== filenameDate;
}

function groupMessagesByDay(
  messages: AudioMatchCandidate[],
): Map<string, AudioMatchCandidate[]> {
  const grouped = new Map<string, AudioMatchCandidate[]>();

  for (const message of messages) {
    const day = dateKeyFromMs(message.timestampMs);
    const bucket = grouped.get(day) ?? [];
    bucket.push(message);
    grouped.set(day, bucket);
  }

  for (const bucket of grouped.values()) {
    bucket.sort((left, right) => left.timestampMs - right.timestampMs);
  }

  return grouped;
}

function matchByWhatsAppFilenameIndex(
  files: AudioFileInput[],
  messagesByDay: Map<string, AudioMatchCandidate[]>,
  usedFiles: Set<string>,
  usedMessages: Set<string>,
): Map<string, AudioMatchResult> {
  const matches = new Map<string, AudioMatchResult>();

  for (const file of files) {
    if (usedFiles.has(file.fileKey) || !isWhatsAppMediaFilename(file.fileName)) {
      continue;
    }

    const day = parseWhatsAppFilenameDate(file.fileName);
    const sequence = parseWhatsAppFilenameSequence(file.fileName);
    if (day === null || sequence === null) {
      continue;
    }

    const dayMessages = messagesByDay.get(day) ?? [];
    const message = dayMessages[sequence];
    if (!message || usedMessages.has(message.messageId)) {
      continue;
    }

    usedFiles.add(file.fileKey);
    usedMessages.add(message.messageId);
    matches.set(file.fileKey, {
      messageId: message.messageId,
      diffSeconds: Math.abs(file.lastModifiedMs - message.timestampMs) / 1000,
      matchedByFilenameFallback: true,
    });
  }

  return matches;
}

function matchByTimestamp(
  files: AudioFileInput[],
  messages: AudioMatchCandidate[],
  usedFiles: Set<string>,
  usedMessages: Set<string>,
  toleranceSeconds: number,
): Map<string, AudioMatchResult> {
  const matches = new Map<string, AudioMatchResult>();
  const availableMessages = messages.filter((message) => !usedMessages.has(message.messageId));
  const remainingFiles = files.filter((file) => !usedFiles.has(file.fileKey));

  const pairs: { fileKey: string; messageId: string; diffSeconds: number }[] = [];
  for (const file of remainingFiles) {
    for (const message of availableMessages) {
      pairs.push({
        fileKey: file.fileKey,
        messageId: message.messageId,
        diffSeconds: Math.abs(file.lastModifiedMs - message.timestampMs) / 1000,
      });
    }
  }

  pairs.sort((left, right) => left.diffSeconds - right.diffSeconds);

  for (const pair of pairs) {
    if (pair.diffSeconds > toleranceSeconds) {
      continue;
    }
    if (usedFiles.has(pair.fileKey) || usedMessages.has(pair.messageId)) {
      continue;
    }

    usedFiles.add(pair.fileKey);
    usedMessages.add(pair.messageId);
    matches.set(pair.fileKey, {
      messageId: pair.messageId,
      diffSeconds: pair.diffSeconds,
      matchedByFilenameFallback: false,
    });
  }

  return matches;
}

export function matchAudioFilesToMessages(
  files: AudioFileInput[],
  messages: AudioMatchCandidate[],
  toleranceSeconds: number = BATCH_MATCH_TOLERANCE_SECONDS,
): Map<string, AudioMatchResult> {
  const matches = new Map<string, AudioMatchResult>();
  const usedFiles = new Set<string>();
  const usedMessages = new Set<string>();
  const messagesByDay = groupMessagesByDay(messages);

  const filenameMatches = matchByWhatsAppFilenameIndex(
    files,
    messagesByDay,
    usedFiles,
    usedMessages,
  );
  for (const [fileKey, result] of filenameMatches) {
    matches.set(fileKey, result);
  }

  const timestampMatches = matchByTimestamp(
    files,
    messages,
    usedFiles,
    usedMessages,
    toleranceSeconds,
  );
  for (const [fileKey, result] of timestampMatches) {
    matches.set(fileKey, result);
  }

  return matches;
}

export function buildBatchUploadReviewItems(
  files: File[],
  messages: ConversationMessage[],
  toleranceSeconds: number = BATCH_MATCH_TOLERANCE_SECONDS,
): BatchUploadReviewItem[] {
  const candidates: AudioMatchCandidate[] = messages
    .filter(isHiddenMediaCandidate)
    .map((message) => ({
      messageId: message.id,
      timestampMs: messageTimestampMs(message),
    }));

  const fileInputs: AudioFileInput[] = files.map((file) => ({
    fileKey: audioFileKey(file),
    fileName: file.name,
    lastModifiedMs: file.lastModified,
  }));

  const matches = matchAudioFilesToMessages(fileInputs, candidates, toleranceSeconds);

  return files.map((file, index) => {
    const key = audioFileKey(file);
    const match = matches.get(key);
    const hasMatch = match != null;
    const matchedByFilenameFallback = match?.matchedByFilenameFallback ?? false;
    const withinTolerance =
      hasMatch &&
      (matchedByFilenameFallback || (match?.diffSeconds ?? Infinity) <= toleranceSeconds);

    return {
      id: `batch-${index}-${key}`,
      file,
      fileName: file.name,
      lastModifiedMs: file.lastModified,
      suggestedMessageId: match?.messageId ?? null,
      selectedMessageId: match?.messageId ?? null,
      diffSeconds: match?.diffSeconds ?? null,
      withinTolerance,
      attach: withinTolerance,
      matchedByFilenameFallback,
      status: 'pending',
      errorMessage: null,
    };
  });
}

export function formatTimeDiffSeconds(seconds: number | null, matchedByFilenameFallback = false): string {
  if (seconds === null) {
    return 'Sem correspondência';
  }
  if (matchedByFilenameFallback) {
    return 'Casado pelo índice WA do nome';
  }
  if (seconds < 60) {
    return `${Math.round(seconds)}s de diferença`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  if (remainder === 0) {
    return `${minutes}min de diferença`;
  }
  return `${minutes}min ${remainder}s de diferença`;
}

export function truncateText(text: string, maxLength = 48): string {
  const trimmed = text.trim().replace(/\s+/g, ' ');
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength - 1)}…`;
}

export function messageContextSnippet(
  messages: ConversationMessage[],
  messageId: string,
): string {
  const index = messages.findIndex((item) => item.id === messageId);
  if (index < 0) {
    return '';
  }

  const parts: string[] = [];
  if (index > 0) {
    const previous = messages[index - 1];
    parts.push(
      `${previous.sender_name || 'Sistema'}: ${truncateText(previous.content)}`,
    );
  }
  const current = messages[index];
  parts.push(`${current.sender_name || 'Sistema'}: ${truncateText(current.content)}`);
  if (index < messages.length - 1) {
    const next = messages[index + 1];
    parts.push(`${next.sender_name || 'Sistema'}: ${truncateText(next.content)}`);
  }
  return parts.join(' · ');
}
