import { ConversationMessage, Participant } from '../../core/models/api.models';
import {
  audioFileKey,
  isHiddenMediaCandidate,
  matchAudioFilesToMessages,
  messageTimestampMs,
  parseWhatsAppFilenameDate,
  parseWhatsAppFilenameSequence,
} from './audio-batch-match';

export type AnalysisImportStatus = 'pending' | 'uploading' | 'completed' | 'failed' | 'skipped';

export interface AnalysisImportItem {
  id: string;
  file: File;
  fileName: string;
  senderId: string;
  senderName: string;
  timestamp: string;
  /** Quando pareado a uma MEDIA_OCULTA, anexa nela em vez de criar áudio solto. */
  matchedMessageId: string | null;
  matchedFromChat: boolean;
  status: AnalysisImportStatus;
  errorMessage: string | null;
}

export function sortAudioFilesForImport(files: File[]): File[] {
  return [...files].sort((left, right) => {
    const dayLeft = parseWhatsAppFilenameDate(left.name);
    const dayRight = parseWhatsAppFilenameDate(right.name);
    if (dayLeft && dayRight && dayLeft !== dayRight) {
      return dayLeft.localeCompare(dayRight);
    }

    const seqLeft = parseWhatsAppFilenameSequence(left.name);
    const seqRight = parseWhatsAppFilenameSequence(right.name);
    if (seqLeft != null && seqRight != null && seqLeft !== seqRight) {
      return seqLeft - seqRight;
    }

    return left.lastModified - right.lastModified;
  });
}

export function timestampForAnalysisImport(file: File): string {
  return new Date(file.lastModified).toISOString();
}

function participantName(participants: Participant[], senderId: string): string {
  return participants.find((participant) => participant.id === senderId)?.name ?? 'Desconhecido';
}

export function alreadyImportedAudioFilenames(messages: ConversationMessage[]): Set<string> {
  const names = new Set<string>();
  for (const message of messages) {
    const filename = message.metadata?.['filename'];
    if (typeof filename !== 'string' || !filename.trim()) {
      continue;
    }
    const transcribed = message.metadata?.['transcribed'] === true;
    const status = message.metadata?.['transcription_status'];
    if (transcribed || status === 'COMPLETED') {
      names.add(filename.trim().toLowerCase());
    }
  }
  return names;
}

export function buildAnalysisImportPlan(
  files: File[],
  messages: ConversationMessage[],
  fallbackSenderId: string,
  participants: Participant[],
): AnalysisImportItem[] {
  const alreadyImported = alreadyImportedAudioFilenames(messages);
  const candidates = messages
    .filter(isHiddenMediaCandidate)
    .map((message) => ({
      messageId: message.id,
      timestampMs: messageTimestampMs(message),
    }));

  const filesToMatch = files.filter(
    (file) => !alreadyImported.has(file.name.trim().toLowerCase()),
  );
  const fileInputs = filesToMatch.map((file) => ({
    fileKey: audioFileKey(file),
    fileName: file.name,
    lastModifiedMs: file.lastModified,
  }));

  const matches = matchAudioFilesToMessages(fileInputs, candidates);
  const messageById = new Map(messages.map((message) => [message.id, message]));

  return sortAudioFilesForImport(files).map((file, index) => {
    const normalizedName = file.name.trim().toLowerCase();
    if (alreadyImported.has(normalizedName)) {
      return {
        id: `analysis-import-${index}-${audioFileKey(file)}`,
        file,
        fileName: file.name,
        senderId: fallbackSenderId,
        senderName: participantName(participants, fallbackSenderId),
        timestamp: timestampForAnalysisImport(file),
        matchedMessageId: null,
        matchedFromChat: false,
        status: 'skipped' as const,
        errorMessage: 'Já transcrito — ignorado.',
      };
    }

    const match = matches.get(audioFileKey(file));
    const message = match ? messageById.get(match.messageId) : undefined;
    const senderId = message?.sender_id ?? fallbackSenderId;
    const timestamp = message?.timestamp ?? timestampForAnalysisImport(file);
    const matchedMessageId = message?.id ?? null;
    const matchedFromChat = matchedMessageId != null;

    return {
      id: `analysis-import-${index}-${audioFileKey(file)}`,
      file,
      fileName: file.name,
      senderId,
      senderName: matchedFromChat
        ? message?.sender_name || participantName(participants, senderId)
        : participantName(participants, senderId),
      timestamp,
      matchedMessageId,
      matchedFromChat,
      status: 'pending',
      errorMessage: null,
    };
  });
}

export function analysisImportStatusLabel(status: AnalysisImportStatus): string {
  const labels: Record<AnalysisImportStatus, string> = {
    pending: 'Pendente',
    uploading: 'Transcrevendo',
    completed: 'Concluído',
    failed: 'Falhou',
    skipped: 'Já existia',
  };
  return labels[status];
}

export function analysisImportSenderHint(item: AnalysisImportItem): string {
  return item.matchedFromChat ? 'identificado no chat' : 'autor padrão';
}

export const ANALYSIS_AUDIO_PLACEHOLDER = 'Áudio enviado pelo usuário';

export function isAnalysisOnlyMessage(metadata: Record<string, unknown> | undefined): boolean {
  return metadata?.['analysis_only'] === true;
}

export function messageNeedsTranscriptionContent(message: ConversationMessage): boolean {
  if (!isAnalysisOnlyMessage(message.metadata)) {
    return false;
  }
  const transcriptionId = message.metadata?.['transcription_id'];
  if (typeof transcriptionId !== 'string' || !transcriptionId) {
    return false;
  }
  const trimmed = message.content.trim();
  return !trimmed || trimmed === ANALYSIS_AUDIO_PLACEHOLDER;
}

export function isTimelineHiddenMediaMessage(message: ConversationMessage): boolean {
  const normalized = message.content.trim().toLowerCase();
  return (
    message.type === 'MEDIA_OCULTA' ||
    normalized === '<mídia oculta>' ||
    normalized === '<midia oculta>'
  );
}

export function uniqueMessageIds(messageIds: string[]): string[] {
  return [...new Set(messageIds)];
}

export function findAnalysisOnlyForTimelineMessage(
  message: ConversationMessage,
  analysisOnlyMessages: ConversationMessage[],
): ConversationMessage | undefined {
  const targetMs = messageTimestampMs(message);
  const senderId = message.sender_id;
  return analysisOnlyMessages.find((item) => {
    if (senderId && item.sender_id !== senderId) {
      return false;
    }
    return Math.abs(messageTimestampMs(item) - targetMs) <= 2_000;
  });
}

export function mergeTimelineMessageWithTranscription(
  message: ConversationMessage,
  analysisOnlyMessages: ConversationMessage[],
): ConversationMessage {
  if (!isTimelineHiddenMediaMessage(message)) {
    return message;
  }
  const matched = findAnalysisOnlyForTimelineMessage(message, analysisOnlyMessages);
  if (!matched) {
    return message;
  }
  const content = matched.content.trim();
  if (!content || content === ANALYSIS_AUDIO_PLACEHOLDER) {
    return message;
  }
  return {
    ...message,
    type: 'AUDIO',
    content,
    metadata: {
      ...(message.metadata ?? {}),
      transcribed: true,
      linked_analysis_only_id: matched.id,
      transcription_id: matched.metadata?.['transcription_id'],
    },
  };
}
