export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationList {
  items: Conversation[];
  total: number;
}

export type ParticipantRole = 'OWNER' | 'OTHER';
export type MessageType = 'TEXT' | 'MEDIA_OCULTA' | 'AUDIO' | 'IMAGE' | 'SYSTEM';

export interface Participant {
  id: string;
  name: string;
  role: ParticipantRole;
}

export interface ConversationMessage {
  id: string;
  sender_id: string | null;
  sender_name: string | null;
  timestamp: string;
  type: MessageType;
  content: string;
  metadata: Record<string, unknown>;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  participants: Participant[];
  messages: ConversationMessage[];
  total_messages: number;
  offset: number;
  limit: number;
}

export interface ImportSummary {
  conversation_id: string;
  total_messages: number;
  skipped_lines: number;
  participants: Participant[];
  first_message_at: string | null;
  last_message_at: string | null;
  import_format?: 'txt' | 'zip';
  messages_added?: number;
  messages_skipped_duplicate?: number;
  audio_files_found?: number;
  audio_files_matched?: number;
  audio_transcriptions_started?: number;
  audio_transcriptions_reused?: number;
}

export type InterestLevel =
  | 'MUITO_BAIXO'
  | 'BAIXO'
  | 'MODERADO'
  | 'ALTO'
  | 'MUITO_ALTO';

export interface InterestSignal {
  key: string;
  label: string;
  participant: string;
  strength: number;
  observation: string;
  message_ids: string[];
  metadata?: Record<string, unknown>;
}

export interface AnalysisEvidence {
  id: string;
  signal_key: string;
  signal_label: string;
  polarity: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | string;
  message_ids: string[];
  observation: string;
}

export interface TimelinePeriod {
  key: string;
  label: string;
  message_count: number;
  interest_score: number;
  interest_level: InterestLevel;
  confidence_score: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  summary_observation: string;
}

export interface TimelineResponse {
  conversation_id: string;
  periods: TimelinePeriod[];
}

export interface ConversationAnalysis {
  id: string;
  conversation_id: string;
  summary: string;
  metrics: Record<string, unknown>;
  llm_provider: string;
  llm_model: string;
  input_tokens: number;
  output_tokens: number;
  interest_score?: number | null;
  interest_level?: InterestLevel | null;
  confidence_score?: number | null;
  positive_signals?: InterestSignal[];
  neutral_signals?: InterestSignal[];
  negative_signals?: InterestSignal[];
  created_at: string;
  updated_at: string;
}

export interface AnalyzeResponse {
  analysis: ConversationAnalysis;
  observations: string[];
  inferences: string[];
  context_strategy?: string;
  interest_score?: number | null;
  interest_level?: InterestLevel | null;
  confidence_score?: number | null;
  positive_signals?: InterestSignal[];
  neutral_signals?: InterestSignal[];
  negative_signals?: InterestSignal[];
  evidence?: AnalysisEvidence[];
  reciprocity?: Record<string, unknown> | null;
  summary_stale?: boolean;
  from_cache?: boolean;
}

export interface ProcessingStatusResponse {
  status: 'PENDING' | 'PROCESSING' | string;
  message: string;
}

export interface AskResponse {
  answer: string;
  observations: string[];
  inferences: string[];
  llm_provider: string;
  llm_model: string;
  context_strategy?: string;
}

export type TranscriptionStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface AudioTranscriptionStartedResponse {
  transcription_id: string;
  message_id: string;
  status: TranscriptionStatus | string;
  message: string;
}

export interface AudioTranscription {
  id: string;
  conversation_id: string;
  message_id: string;
  status: TranscriptionStatus | string;
  transcribed_text: string | null;
  transcription_provider: string;
  transcription_model: string;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UsageRecord {
  id: string;
  conversation_id: string | null;
  operation: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  audio_seconds: number | null;
  estimated_cost: number;
  created_at: string;
}

export interface UsageSummary {
  total_records: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_audio_seconds: number;
  total_estimated_cost: number;
  records: UsageRecord[];
}

export interface DashboardConversationItem {
  id: string;
  title: string;
  updated_at: string;
  total_messages: number;
  interest_level: InterestLevel | null;
  interest_score: number | null;
  confidence_score: number | null;
  analyzed_at: string | null;
}

export interface DashboardSummary {
  total_conversations: number;
  analyzed_conversations: number;
  interest_distribution: Record<string, number>;
  recent: DashboardConversationItem[];
  usage: UsageSummary;
}

export type SuggestionCategory = 'NATURAL' | 'DIVERTIDA' | 'DIRETA' | 'CONSERVADORA';

export interface SuggestionRead {
  id: string;
  category: SuggestionCategory;
  suggested_text: string;
  created_at: string;
}

export interface SuggestionsRequest {
  incoming_message: string;
}

export interface SuggestionsResponse {
  conversation_id: string;
  based_on_message_id: string | null;
  incoming_message: string;
  suggestions: SuggestionRead[];
  llm_provider: string;
  llm_model: string;
}
