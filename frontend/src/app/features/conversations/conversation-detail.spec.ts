import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import {
  AudioTranscription,
  ConversationDetail,
  ConversationMessage,
  Participant,
} from '../../core/models/api.models';
import { ConversationService } from '../../core/services/conversation.service';
import { ConversationDetailComponent } from './conversation-detail';

describe('ConversationDetailComponent', () => {
  let component: ConversationDetailComponent;
  let conversationsApi: jasmine.SpyObj<ConversationService>;

  const baseMs = new Date('2026-08-18T10:00:00.000Z').getTime();
  const giulia: Participant = { id: 'participant-giulia', name: 'Giulia', role: 'OTHER' };
  const alle: Participant = { id: 'participant-alle', name: 'Alle', role: 'OWNER' };

  function hiddenMessage(
    id: string,
    timestamp: string,
    sender: Participant,
  ): ConversationMessage {
    return {
      id,
      sender_id: sender.id,
      sender_name: sender.name,
      timestamp,
      type: 'MEDIA_OCULTA',
      content: '<Mídia oculta>',
      metadata: {},
    };
  }

  function audioFile(name: string, lastModified: number): File {
    return new File(['audio'], name, { type: 'audio/opus', lastModified });
  }

  function fileInputEvent(files: File[]): Event {
    const input = document.createElement('input');
    Object.defineProperty(input, 'files', { value: files });
    return { target: input } as unknown as Event;
  }

  function transcription(messageId: string): AudioTranscription {
    return {
      id: `tx-${messageId}`,
      conversation_id: 'conv-1',
      message_id: messageId,
      status: 'COMPLETED',
      transcribed_text: 'texto',
      transcription_provider: 'openai',
      transcription_model: 'whisper-1',
      duration_seconds: 1,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }

  function setConversation(messages: ConversationMessage[]): void {
    component.messages.set(messages);
    component.detail.set({
      id: 'conv-1',
      title: 'Teste',
      created_at: '2026-08-18T10:00:00Z',
      updated_at: '2026-08-18T10:00:00Z',
      participants: [alle, giulia],
      messages,
      total_messages: messages.length,
      offset: 0,
      limit: 200,
    });
    component.analysisImportSenderId.set(giulia.id);
  }

  beforeEach(async () => {
    conversationsApi = jasmine.createSpyObj('ConversationService', [
      'importTxt',
      'get',
      'getMessage',
      'getAudioTranscription',
      'listAnalysisOnlyMessages',
      'deleteAnalysisMessage',
      'getAnalysis',
      'getTimeline',
      'analyze',
      'ask',
      'generateSuggestions',
      'uploadAudio',
      'uploadAudioForAnalysis',
      'createManualTranscription',
    ]);
    conversationsApi.get.and.callFake((_id: string, offset = 0) => {
      const messages = component.messages().slice(offset);
      return of({
        id: 'conv-1',
        title: 'Teste',
        created_at: '2026-08-18T10:00:00Z',
        updated_at: '2026-08-18T10:00:00Z',
        participants: [alle, giulia],
        messages,
        total_messages: component.messages().length,
        offset,
        limit: 200,
      } satisfies ConversationDetail);
    });
    conversationsApi.getMessage.and.callFake((_convId: string, messageId: string) => {
      const message = component.messages().find((item) => item.id === messageId);
      if (!message) {
        return throwError(() => ({ status: 404 }));
      }
      return of(message);
    });
    conversationsApi.listAnalysisOnlyMessages.and.returnValue(of([]));

    conversationsApi.getAnalysis.and.returnValue(
      of({
        analysis: {
          id: 'analysis-1',
          conversation_id: 'conv-1',
          summary: 'Resumo persistido.',
          metrics: {},
          llm_provider: 'fake',
          llm_model: 'fake-model',
          input_tokens: 10,
          output_tokens: 20,
          interest_score: 55,
          interest_level: 'MODERADO',
          confidence_score: 79,
          created_at: '2026-08-18T10:00:00Z',
          updated_at: '2026-08-18T10:00:00Z',
        },
        observations: ['Observação persistida.'],
        inferences: ['Inferência persistida.'],
        interest_score: 55,
        interest_level: 'MODERADO',
        confidence_score: 79,
        positive_signals: [
          {
            key: 'initiates_conversations',
            label: 'Inicia conversas',
            participant: 'Giulia',
            strength: 0.8,
            observation: 'Giulia iniciou 2 conversas.',
            message_ids: ['msg-g'],
            metadata: {},
          },
        ],
        neutral_signals: [],
        negative_signals: [],
        evidence: [
          {
            id: 'evidence-1',
            signal_key: 'initiates_conversations',
            signal_label: 'Inicia conversas',
            polarity: 'POSITIVE',
            message_ids: ['msg-g'],
            observation: 'Giulia iniciou 2 conversas.',
          },
        ],
      }),
    );
    conversationsApi.getTimeline.and.returnValue(of({ conversation_id: 'conv-1', periods: [] }));

    await TestBed.configureTestingModule({
      imports: [ConversationDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ConversationService, useValue: conversationsApi },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => 'conv-1' } } },
        },
      ],
    }).compileComponents();

    component = TestBed.createComponent(ConversationDetailComponent).componentInstance;
  });

  it('restores persisted analysis after reload', () => {
    component.ngOnInit();

    expect(component.analysis()?.summary).toBe('Resumo persistido.');
    expect(component.analysisInsights()?.observations).toEqual(['Observação persistida.']);
    expect(component.positiveSignals().length).toBe(1);
    expect(component.evidence().length).toBe(1);
    expect(component.interestLevel()).toBe('MODERADO');
  });

  it('imports mixed audios with per-file sender detection', async () => {
    setConversation([
      hiddenMessage('msg-g', new Date(baseMs).toISOString(), giulia),
      hiddenMessage('msg-a', new Date(baseMs + 60_000).toISOString(), alle),
    ]);
    conversationsApi.uploadAudio.and.returnValue(of(transcription('msg-g')));
    spyOn(component as unknown as { reload: (reset: boolean) => void }, 'reload');
    spyOn(
      component as unknown as { loadExistingAnalysis: () => void },
      'loadExistingAnalysis',
    );
    spyOn(
      component as unknown as { loadAnalysisOnlyMessages: () => void },
      'loadAnalysisOnlyMessages',
    );

    await (
      component as unknown as { runAudioBatchImport: (files: File[]) => Promise<void> }
    ).runAudioBatchImport([
      audioFile('PTT-20260818-WA0000.opus', baseMs),
      audioFile('PTT-20260818-WA0001.opus', baseMs + 60_000),
    ]);

    expect(conversationsApi.uploadAudio).toHaveBeenCalledTimes(2);
    expect(conversationsApi.uploadAudio).toHaveBeenCalledWith(
      'conv-1',
      'msg-g',
      jasmine.any(File),
    );
    expect(conversationsApi.uploadAudio).toHaveBeenCalledWith(
      'conv-1',
      'msg-a',
      jasmine.any(File),
    );
    expect(component.analysisImportItems()[0].matchedFromChat).toBeTrue();
    expect(component.analysisImportItems()[1].matchedFromChat).toBeTrue();
  });

  it('hides analysis-only messages from visible thread', () => {
    setConversation([
      hiddenMessage('msg-1', new Date(baseMs).toISOString(), giulia),
      {
        ...hiddenMessage('msg-2', new Date(baseMs + 60_000).toISOString(), giulia),
        metadata: { analysis_only: true },
      },
    ]);

    expect(component.visibleMessages().length).toBe(1);
  });

  it('shows imported transcription inline on timeline hidden media', () => {
    const timestamp = new Date(baseMs).toISOString();
    setConversation([
      {
        id: 'msg-hidden',
        sender_id: giulia.id,
        sender_name: 'Giulia',
        timestamp,
        type: 'MEDIA_OCULTA',
        content: '<Mídia oculta>',
        metadata: { hidden_media: true },
      },
    ]);
    component.analysisOnlyMessages.set([
      {
        id: 'msg-audio',
        sender_id: giulia.id,
        sender_name: 'Giulia',
        timestamp,
        type: 'AUDIO',
        content: 'Oi, bom dia! Tudo bem por aí?',
        metadata: { analysis_only: true },
      },
    ]);

    expect(component.visibleMessages()[0].content).toBe('Oi, bom dia! Tudo bem por aí?');
    expect(component.visibleMessages()[0].metadata?.['transcribed']).toBeTrue();
  });

  it('retries failed imports preserving per-file sender', async () => {
    setConversation([hiddenMessage('msg-g', new Date(baseMs).toISOString(), giulia)]);
    conversationsApi.uploadAudio.and.callFake(() => {
      if (conversationsApi.uploadAudio.calls.count() === 1) {
        return throwError(() => ({ status: 429, error: { detail: 'Rate limit' } }));
      }
      return of(transcription('msg-g'));
    });
    spyOn(component as unknown as { reload: (reset: boolean) => void }, 'reload');
    spyOn(
      component as unknown as { loadExistingAnalysis: () => void },
      'loadExistingAnalysis',
    );
    spyOn(
      component as unknown as { loadAnalysisOnlyMessages: () => void },
      'loadAnalysisOnlyMessages',
    );

    await (
      component as unknown as { runAudioBatchImport: (files: File[]) => Promise<void> }
    ).runAudioBatchImport([audioFile('PTT-20260818-WA0000.opus', baseMs)]);
    expect(component.analysisImportItems()[0].status).toBe('failed');

    await (
      component as unknown as { retryFailedAnalysisImportsAsync: () => Promise<void> }
    ).retryFailedAnalysisImportsAsync();
    expect(component.analysisImportItems()[0].status).toBe('completed');
    expect(conversationsApi.uploadAudio).toHaveBeenCalledWith(
      'conv-1',
      'msg-g',
      jasmine.any(File),
    );
  });

  it('opens evidence preview for analysis-only messages', async () => {
    const hiddenAudio: ConversationMessage = {
      id: 'msg-audio',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp: new Date(baseMs).toISOString(),
      type: 'AUDIO',
      content: 'Transcrição do áudio importado.',
      metadata: { analysis_only: true },
    };
    setConversation([hiddenAudio]);

    await (component as unknown as { openEvidenceMessage: (evidenceId: string, messageId: string) => Promise<void> })
      .openEvidenceMessage('evidence-1', 'msg-audio');

    expect(component.evidencePreviewMessage()?.content).toBe('Transcrição do áudio importado.');
    expect(component.isEvidencePreviewOpenFor('evidence-1')).toBeTrue();
    expect(component.isEvidencePreviewOpenFor('evidence-2')).toBeFalse();
  });

  it('loads transcription text when analysis-only message still has placeholder', async () => {
    const hiddenAudio: ConversationMessage = {
      id: 'msg-audio',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp: new Date(baseMs).toISOString(),
      type: 'AUDIO',
      content: 'Áudio enviado pelo usuário',
      metadata: { analysis_only: true, transcription_id: 'tx-1' },
    };
    setConversation([hiddenAudio]);
    conversationsApi.getMessage.and.returnValue(of(hiddenAudio));
    conversationsApi.getAudioTranscription.and.returnValue(
      of({
        id: 'tx-1',
        conversation_id: 'conv-1',
        message_id: 'msg-audio',
        status: 'COMPLETED',
        transcribed_text: 'Oi, tudo bem por aí?',
        transcription_provider: 'openai',
        transcription_model: 'whisper-1',
        duration_seconds: 3,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    );

    await (component as unknown as { openEvidenceMessage: (evidenceId: string, messageId: string) => Promise<void> })
      .openEvidenceMessage('evidence-audio', 'msg-audio');

    expect(conversationsApi.getAudioTranscription).toHaveBeenCalledWith('conv-1', 'tx-1');
    expect(component.evidencePreviewMessage()?.content).toBe('Oi, tudo bem por aí?');
  });

  it('resolves timeline hidden media to imported transcription in evidence preview', async () => {
    const timestamp = new Date(baseMs).toISOString();
    const hiddenTimeline: ConversationMessage = {
      id: 'msg-hidden',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp,
      type: 'MEDIA_OCULTA',
      content: '<Mídia oculta>',
      metadata: { hidden_media: true },
    };
    const analysisOnly: ConversationMessage = {
      id: 'msg-audio-linked',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp,
      type: 'AUDIO',
      content: 'Transcrição real do áudio da Giulia.',
      metadata: { analysis_only: true },
    };
    setConversation([hiddenTimeline]);
    conversationsApi.getMessage.and.returnValue(of(hiddenTimeline));
    conversationsApi.listAnalysisOnlyMessages.and.returnValue(of([analysisOnly]));

    await (component as unknown as { openEvidenceMessage: (evidenceId: string, messageId: string) => Promise<void> })
      .openEvidenceMessage('evidence-hidden', 'msg-hidden');

    expect(component.evidencePreviewMessage()?.content).toBe(
      'Transcrição real do áudio da Giulia.',
    );
    expect(component.evidencePreviewMessage()?.metadata?.['transcription_resolved']).toBeTrue();
    expect(component.analysisRemovalMessageId(component.evidencePreviewMessage()!)).toBe(
      'msg-audio-linked',
    );
  });

  it('shows timeline messages inline below evidence instead of scrolling the thread', async () => {
    const textMessage: ConversationMessage = {
      id: 'msg-text',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp: new Date(baseMs).toISOString(),
      type: 'TEXT',
      content: 'Mensagem visível na timeline.',
      metadata: {},
    };
    setConversation([textMessage]);
    conversationsApi.getMessage.and.returnValue(of(textMessage));

    await (component as unknown as { openEvidenceMessage: (evidenceId: string, messageId: string) => Promise<void> })
      .openEvidenceMessage('evidence-text', 'msg-text');

    expect(component.evidencePreviewMessage()?.content).toBe('Mensagem visível na timeline.');
    expect(component.isEvidencePreviewActive('evidence-text', 'msg-text')).toBeTrue();
    expect(component.isEvidencePreviewActive('evidence-other', 'msg-text')).toBeFalse();
  });

  it('opens preview only for the clicked evidence when message ids overlap', async () => {
    const sharedMessage: ConversationMessage = {
      id: 'msg-shared',
      sender_id: giulia.id,
      sender_name: 'Giulia',
      timestamp: new Date(baseMs).toISOString(),
      type: 'AUDIO',
      content: 'Mensagem compartilhada entre evidências.',
      metadata: { analysis_only: true },
    };
    setConversation([sharedMessage]);
    conversationsApi.getMessage.and.returnValue(of(sharedMessage));
    component.evidence.set([
      {
        id: 'evidence-share',
        signal_key: 'compartilha_informacao',
        signal_label: 'Compartilha informação espontaneamente',
        polarity: 'POSITIVE',
        message_ids: ['msg-shared'],
        observation: 'Giulia compartilhou informações extensas.',
      },
      {
        id: 'evidence-audio',
        signal_key: 'envia_audio_espontaneo',
        signal_label: 'Envia áudio espontaneamente',
        polarity: 'POSITIVE',
        message_ids: ['msg-shared'],
        observation: 'Giulia enviou áudio espontaneamente.',
      },
    ]);

    await (component as unknown as { openEvidenceMessage: (evidenceId: string, messageId: string) => Promise<void> })
      .openEvidenceMessage('evidence-share', 'msg-shared');

    expect(component.isEvidencePreviewOpenFor('evidence-share')).toBeTrue();
    expect(component.isEvidencePreviewOpenFor('evidence-audio')).toBeFalse();
    expect(component.isEvidencePreviewActive('evidence-share', 'msg-shared')).toBeTrue();
    expect(component.isEvidencePreviewActive('evidence-audio', 'msg-shared')).toBeFalse();
  });
});
