import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import {
  AnalyzeResponse,
  AskResponse,
  AudioTranscription,
  AudioTranscriptionStartedResponse,
  Conversation,
  ConversationAnalysis,
  ConversationDetail,
  ConversationList,
  ConversationMessage,
  ImportSummary,
  Participant,
  ProcessingStatusResponse,
  SuggestionsResponse,
  TimelineResponse,
} from '../models/api.models';
import { pollHttpGet, pollHttpPost } from '../utils/processing-poll';

@Injectable({ providedIn: 'root' })
export class ConversationService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/conversations`;

  list(): Observable<ConversationList> {
    return this.http.get<ConversationList>(this.baseUrl);
  }

  create(title: string): Observable<Conversation> {
    return this.http.post<Conversation>(this.baseUrl, { title });
  }

  get(id: string, offset = 0, limit = 50): Observable<ConversationDetail> {
    const params = new HttpParams().set('offset', offset).set('limit', limit);
    return this.http.get<ConversationDetail>(`${this.baseUrl}/${id}`, { params });
  }

  getMessage(conversationId: string, messageId: string): Observable<ConversationMessage> {
    return this.http.get<ConversationMessage>(
      `${this.baseUrl}/${conversationId}/messages/${messageId}`,
    );
  }

  listAnalysisOnlyMessages(conversationId: string): Observable<ConversationMessage[]> {
    return this.http.get<ConversationMessage[]>(
      `${this.baseUrl}/${conversationId}/messages/analysis-only`,
    );
  }

  deleteAnalysisMessage(conversationId: string, messageId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${conversationId}/messages/${messageId}`);
  }

  getAudioTranscription(
    conversationId: string,
    transcriptionId: string,
  ): Observable<AudioTranscription> {
    return this.http.get<AudioTranscription>(
      `${this.baseUrl}/${conversationId}/audio/${transcriptionId}`,
    );
  }

  importTxt(id: string, file: File, ownerName?: string): Observable<ImportSummary> {
    const body = new FormData();
    body.append('file', file);
    if (ownerName) {
      body.append('owner_name', ownerName);
    }
    return this.http.post<ImportSummary>(`${this.baseUrl}/${id}/import`, body);
  }

  setOwner(id: string, participantId: string): Observable<Participant[]> {
    return this.http.post<Participant[]>(`${this.baseUrl}/${id}/owner`, {
      participant_id: participantId,
    });
  }

  analyze(
    id: string,
    onProcessing?: (status: ProcessingStatusResponse) => void,
    options?: { force?: boolean },
  ): Observable<AnalyzeResponse> {
    const force = options?.force ?? false;
    return pollHttpPost(
      () =>
        this.http.post<AnalyzeResponse | ProcessingStatusResponse>(
          `${this.baseUrl}/${id}/analyze`,
          {},
          {
            observe: 'response',
            params: force ? { force: 'true' } : undefined,
          },
        ),
      onProcessing,
    );
  }

  getAnalysis(id: string): Observable<AnalyzeResponse> {
    return this.http.get<AnalyzeResponse>(`${this.baseUrl}/${id}/analysis`);
  }

  ask(
    id: string,
    question: string,
    onProcessing?: (status: ProcessingStatusResponse) => void,
  ): Observable<AskResponse> {
    return pollHttpPost(
      () =>
        this.http.post<AskResponse | ProcessingStatusResponse>(
          `${this.baseUrl}/${id}/ask`,
          { question },
          { observe: 'response' },
        ),
      onProcessing,
    );
  }

  getTimeline(id: string): Observable<TimelineResponse> {
    return this.http.get<TimelineResponse>(`${this.baseUrl}/${id}/timeline`);
  }

  uploadAudio(
    conversationId: string,
    messageId: string,
    file: File,
    onProcessing?: (status: AudioTranscription) => void,
  ): Observable<AudioTranscription> {
    const body = new FormData();
    body.append('file', file);
    body.append('message_id', messageId);
    return this.pollAudioUpload(conversationId, body, onProcessing);
  }

  uploadAudioForAnalysis(
    conversationId: string,
    senderId: string,
    timestamp: string,
    file: File,
    onProcessing?: (status: AudioTranscription) => void,
  ): Observable<AudioTranscription> {
    const body = new FormData();
    body.append('file', file);
    body.append('sender_id', senderId);
    body.append('timestamp', timestamp);
    return this.pollAudioUpload(conversationId, body, onProcessing);
  }

  createManualTranscription(
    conversationId: string,
    payload: {
      text: string;
      message_id: string;
    },
  ): Observable<ConversationMessage> {
    return this.http.post<ConversationMessage>(
      `${this.baseUrl}/${conversationId}/manual-transcription`,
      payload,
    );
  }

  private pollAudioUpload(
    conversationId: string,
    body: FormData,
    onProcessing?: (status: AudioTranscription) => void,
  ): Observable<AudioTranscription> {
    return this.http
      .post<AudioTranscriptionStartedResponse>(
        `${this.baseUrl}/${conversationId}/audio`,
        body,
        { observe: 'response' },
      )
      .pipe(
        switchMap((response) => {
          if (response.status !== 202 || !response.body) {
            throw new HttpErrorResponse({
              status: response.status,
              statusText: response.statusText,
              error: response.body,
            });
          }
          const started = response.body;
          if (started.status === 'COMPLETED' || started.status === 'FAILED') {
            return this.http.get<AudioTranscription>(
              `${this.baseUrl}/${conversationId}/audio/${started.transcription_id}`,
            );
          }
          return pollHttpGet(
            () =>
              this.http.get<AudioTranscription>(
                `${this.baseUrl}/${conversationId}/audio/${started.transcription_id}`,
              ),
            (item) => item.status === 'COMPLETED' || item.status === 'FAILED',
            onProcessing,
          );
        }),
      );
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  generateSuggestions(
    id: string,
    payload: { incoming_message: string },
  ): Observable<SuggestionsResponse> {
    return this.http.post<SuggestionsResponse>(`${this.baseUrl}/${id}/suggestions`, payload);
  }
}
