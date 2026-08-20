import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';
import {
  AnalysisEvidence,
  AnalyzeResponse,
  AskResponse,
  ConversationAnalysis,
  ConversationDetail,
  ConversationMessage,
  ImportSummary,
  InterestLevel,
  InterestSignal,
  Participant,
  SuggestionRead,
  TimelinePeriod,
} from '../../core/models/api.models';
import { ConversationService } from '../../core/services/conversation.service';
import {
  DEFAULT_EMBEDDING_PROCESSING_MESSAGE,
  DEFAULT_TRANSCRIPTION_PROCESSING_MESSAGE,
  ProcessingPollTimeoutError,
} from '../../core/utils/processing-poll';
import { SignalPulseComponent } from '../../shared/signal-pulse/signal-pulse';
import {
  AnalysisImportItem,
  AnalysisImportStatus,
  analysisImportSenderHint as formatAnalysisImportSenderHint,
  analysisImportStatusLabel,
  buildAnalysisImportPlan,
  findAnalysisOnlyForTimelineMessage,
  isAnalysisOnlyMessage,
  isTimelineHiddenMediaMessage,
  mergeTimelineMessageWithTranscription,
  messageNeedsTranscriptionContent,
  ANALYSIS_AUDIO_PLACEHOLDER,
  uniqueMessageIds,
} from './audio-analysis-import';

export type DetailTab = 'analise' | 'conversa' | 'explorar';

@Component({
  selector: 'app-conversation-detail',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressBarModule,
    MatSelectModule,
    MatSnackBarModule,
    SignalPulseComponent,
  ],
  templateUrl: './conversation-detail.html',
  styleUrl: './conversation-detail.scss',
})
export class ConversationDetailComponent implements OnInit {
  private readonly conversationsApi = inject(ConversationService);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);
  /** Impede reload de fechar o painel no meio de um Atualizar. */
  private retainImportPanel = false;

  readonly pageSize = 50;
  readonly activeTab = signal<DetailTab>('analise');
  readonly detail = signal<ConversationDetail | null>(null);
  readonly messages = signal<ConversationMessage[]>([]);
  readonly error = signal<string | null>(null);
  readonly importing = signal(false);
  readonly analyzing = signal(false);
  readonly asking = signal(false);
  readonly analyzeProcessingMessage = signal<string | null>(null);
  readonly askProcessingMessage = signal<string | null>(null);
  readonly importSummary = signal<ImportSummary | null>(null);
  readonly analysis = signal<ConversationAnalysis | null>(null);
  readonly analysisInsights = signal<{ observations: string[]; inferences: string[] } | null>(
    null,
  );
  readonly interestLevel = signal<InterestLevel | null>(null);
  readonly interestScore = signal<number | null>(null);
  readonly confidenceScore = signal<number | null>(null);
  readonly positiveSignals = signal<InterestSignal[]>([]);
  readonly neutralSignals = signal<InterestSignal[]>([]);
  readonly negativeSignals = signal<InterestSignal[]>([]);
  readonly evidence = signal<AnalysisEvidence[]>([]);
  readonly timeline = signal<TimelinePeriod[]>([]);
  readonly highlightedMessageId = signal<string | null>(null);
  readonly evidencePreviewMessage = signal<ConversationMessage | null>(null);
  readonly evidencePreviewEvidenceId = signal<string | null>(null);
  readonly evidencePreviewLoading = signal(false);
  readonly askAnswer = signal<AskResponse | null>(null);
  readonly selectedUpdateFiles = signal<File[]>([]);
  readonly transcribingMessageId = signal<string | null>(null);
  readonly transcriptionProcessingMessage = signal<string | null>(null);
  readonly pendingAudioMessageId = signal<string | null>(null);
  readonly generatingSuggestions = signal(false);
  readonly suggestions = signal<SuggestionRead[]>([]);
  readonly copiedSuggestionId = signal<string | null>(null);
  readonly analysisImportItems = signal<AnalysisImportItem[]>([]);
  readonly analysisImportPhase = signal<'uploading' | 'done' | null>(null);
  readonly analysisImportSenderId = signal<string | null>(null);
  readonly analysisOnlyMessages = signal<ConversationMessage[]>([]);
  readonly analysisOnlyPanelOpen = signal(false);
  readonly deletingAnalysisMessageId = signal<string | null>(null);
  readonly analysisNeedsRefresh = signal(false);
  readonly summaryStale = signal(false);
  readonly analysisCachedNotice = signal<string | null>(null);
  readonly audioImportNotice = signal<string | null>(null);
  readonly importPanelOpen = signal(false);
  readonly savingManualTranscription = signal(false);
  readonly pastingMessageId = signal<string | null>(null);
  readonly pasteTranscriptionControl = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.maxLength(20_000)],
  });

  readonly timelineScores = computed(() => this.timeline().map((p) => p.interest_score));
  readonly importedAudioCount = computed(() => {
    const analysisOnly = this.analysisOnlyMessages().length;
    const timelineTranscribed = this.messages().filter(
      (message) =>
        message.metadata?.['transcribed'] === true && !isAnalysisOnlyMessage(message.metadata),
    ).length;
    return analysisOnly + timelineTranscribed;
  });
  readonly visibleMessages = computed(() =>
    this.messages()
      .filter((message) => !isAnalysisOnlyMessage(message.metadata))
      .map((message) =>
        mergeTimelineMessageWithTranscription(message, this.analysisOnlyMessages()),
      ),
  );
  readonly otherParticipants = computed(
    () => this.detail()?.participants.filter((participant) => participant.role !== 'OWNER') ?? [],
  );
  readonly analysisImportSummary = computed(() => {
    const items = this.analysisImportItems();
    return {
      completed: items.filter((item) => item.status === 'completed').length,
      failed: items.filter((item) => item.status === 'failed').length,
      skipped: items.filter((item) => item.status === 'skipped').length,
      total: items.length,
    };
  });
  readonly showAudioFallbackSender = computed(() => {
    const files = this.selectedUpdateFiles();
    const hasAudio = files.some((file) => isAudioUpdateFile(file));
    const hasChat = files.some((file) => isChatExportFile(file));
    return hasAudio && !hasChat && (this.detail()?.participants.length || 0) > 1;
  });
  readonly selectedUpdateAudioCount = computed(
    () => this.selectedUpdateFiles().filter((file) => isAudioUpdateFile(file)).length,
  );
  readonly selectedUpdateChatCount = computed(
    () => this.selectedUpdateFiles().filter((file) => isChatExportFile(file)).length,
  );
  readonly pendingMediaMessages = computed(() =>
    this.visibleMessages().filter((message) => this.canTranscribe(message)),
  );
  readonly pendingMediaCount = computed(() => this.pendingMediaMessages().length);

  private readonly audioInputId = 'audio-upload-input';

  readonly askForm = this.fb.nonNullable.group({
    question: ['', [Validators.required, Validators.maxLength(1000)]],
  });
  readonly suggestionsForm = this.fb.nonNullable.group({
    incomingMessage: ['', [Validators.required, Validators.maxLength(4000)]],
  });

  readonly needsOwnerSelection = computed(() => {
    const participants = this.detail()?.participants ?? [];
    if (participants.length < 2) {
      return false;
    }
    return !participants.some((participant) => participant.role === 'OWNER');
  });
  readonly settingOwner = signal(false);

  ngOnInit(): void {
    this.reload(true);
    this.loadExistingAnalysis();
    this.loadAnalysisOnlyMessages();
  }

  onUpdateFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    this.selectedUpdateFiles.set(files);
    // NÃO limpar aviso/resultado quando o browser dispara change vazio após o clique.
    if (!files.length) {
      return;
    }

    this.error.set(null);
    this.audioImportNotice.set(null);
    this.analysisImportPhase.set(null);
    this.analysisImportItems.set([]);

    const audioCount = files.filter((file) => isAudioUpdateFile(file)).length;
    const chatCount = files.filter((file) => isChatExportFile(file)).length;
    if (audioCount === 0 && chatCount === 0) {
      this.error.set(
        'Nenhum .txt, .zip ou áudio (.opus etc.) reconhecido. Selecione os arquivos soltos, não uma pasta zipada só de áudio sem o chat.',
      );
    }
  }

  toggleImportPanel(): void {
    const next = !this.importPanelOpen();
    this.importPanelOpen.set(next);
    if (next) {
      this.activeTab.set('conversa');
    }
  }

  setActiveTab(tab: DetailTab): void {
    this.activeTab.set(tab);
  }

  metricMessagesByParticipant(): Array<{ name: string; count: number }> {
    const raw = this.analysis()?.metrics?.['messages_by_participant'];
    if (!raw || typeof raw !== 'object') {
      return [];
    }
    return Object.entries(raw as Record<string, number>)
      .map(([name, count]) => ({ name, count }))
      .sort((left, right) => right.count - left.count);
  }

  metricMedianResponseLabel(): string {
    const raw = this.analysis()?.metrics?.['response_time'];
    if (!raw || typeof raw !== 'object') {
      return '—';
    }
    const median = (raw as Record<string, unknown>)['median'];
    if (typeof median !== 'number') {
      return '—';
    }
    if (median < 60) {
      return `${Math.round(median)}s`;
    }
    if (median < 3600) {
      return `${Math.round(median / 60)} min`;
    }
    return `${(median / 3600).toFixed(1)} h`;
  }

  submitConversationUpdate(): void {
    const count = this.selectedUpdateFiles().length;
    this.retainImportPanel = true;
    this.importPanelOpen.set(true);
    if (!count) {
      this.setError('Nenhum arquivo selecionado.');
      return;
    }
    this.notifySuccess(`Iniciando atualização (${count} arquivo(s))…`);
    void this.runConversationUpdate().catch((err: unknown) => {
      const message =
        err instanceof Error ? err.message : 'Falha inesperada ao atualizar a conversa.';
      this.analysisImportPhase.set(null);
      this.setError(message);
    });
  }

  private async runConversationUpdate(): Promise<void> {
    const id = this.conversationId();
    const files = this.selectedUpdateFiles();
    if (!id || !files.length) {
      this.error.set('Selecione um .txt, .zip ou áudios exportados do WhatsApp.');
      return;
    }

    const chatFile = pickChatExportFile(files);
    const audioFiles = files.filter((file) => isAudioUpdateFile(file));
    if (!chatFile && !audioFiles.length) {
      this.error.set('Selecione um .txt, .zip ou arquivos de áudio (.opus, etc.).');
      return;
    }

    this.error.set(null);
    this.importSummary.set(null);
    this.retainImportPanel = true;
    this.importPanelOpen.set(true);
    // Evita o reload do .txt fechar o painel antes do lote de áudio.
    if (audioFiles.length) {
      this.analysisImportPhase.set('uploading');
      this.notifySuccess(
        `Processando ${audioFiles.length} áudio(s)${chatFile ? ' (+ chat)' : ''}…`,
      );
    }

    if (chatFile) {
      const imported = await this.importChatExport(id, chatFile);
      if (imported) {
        await this.reloadAsync(true);
        this.importPanelOpen.set(true);
      } else if (!audioFiles.length) {
        this.analysisImportPhase.set(null);
        return;
      }
    }

    if (audioFiles.length) {
      await this.runAudioBatchImport(audioFiles);
    } else if (chatFile) {
      this.loadExistingAnalysis();
      this.loadAnalysisOnlyMessages();
      this.notifySuccess('Conversa atualizada.');
    }

    this.selectedUpdateFiles.set([]);
    this.importPanelOpen.set(true);
  }

  private async importChatExport(conversationId: string, file: File): Promise<boolean> {
    this.importing.set(true);
    try {
      const summary = await firstValueFrom(this.conversationsApi.importTxt(conversationId, file));
      this.importing.set(false);
      this.importSummary.set(summary);
      return true;
    } catch (err: unknown) {
      this.importing.set(false);
      this.setError(
        err instanceof HttpErrorResponse
          ? this.readError(err, 'Falha ao importar o arquivo.')
          : 'Falha ao importar o arquivo.',
      );
      return false;
    }
  }

  selectOwner(participantId: string): void {
    const conversationId = this.conversationId();
    if (!conversationId || this.settingOwner()) {
      return;
    }
    this.settingOwner.set(true);
    this.error.set(null);
    this.conversationsApi.setOwner(conversationId, participantId).subscribe({
      next: (participants) => {
        this.settingOwner.set(false);
        const current = this.detail();
        if (current) {
          this.detail.set({ ...current, participants });
        }
        if (!this.analysisImportSenderId()) {
          const other = participants.find((participant) => participant.role !== 'OWNER');
          if (other) {
            this.analysisImportSenderId.set(other.id);
          }
        }
        this.notifySuccess('Identidade definida nesta conversa.');
      },
      error: (err: HttpErrorResponse) => {
        this.settingOwner.set(false);
        this.setError(this.readError(err, 'Falha ao definir quem é você na conversa.'));
      },
    });
  }

  analyzeConversation(): void {
    if (this.needsOwnerSelection()) {
      this.setError('Escolha quem é você na conversa antes de analisar.');
      return;
    }
    const id = this.conversationId();
    if (!id) {
      return;
    }
    this.analyzing.set(true);
    this.error.set(null);
    this.analysisCachedNotice.set(null);
    this.analyzeProcessingMessage.set(null);
    // Só consome LLM se o fingerprint do conteúdo mudou (cache no backend).
    this.conversationsApi
      .analyze(id, (status) => {
        this.analyzeProcessingMessage.set(
          status.message?.trim() || DEFAULT_EMBEDDING_PROCESSING_MESSAGE,
        );
      })
      .subscribe({
        next: (result: AnalyzeResponse) => {
          this.analyzing.set(false);
          this.analyzeProcessingMessage.set(null);
          this.applyAnalysisResult(result);
          if (result.from_cache && !result.summary_stale) {
            this.notifySuccess('Análise já estava atualizada — sem consumo de LLM.');
          } else {
            this.notifySuccess('Análise concluída.');
          }
        },
        error: (err: unknown) => {
          this.analyzing.set(false);
          this.analyzeProcessingMessage.set(null);
          this.analysisNeedsRefresh.set(true);
          this.setError(this.readActionError(err, 'Falha ao analisar a conversa.'));
        },
      });
  }

  askQuestion(): void {
    const id = this.conversationId();
    if (!id || this.askForm.invalid) {
      this.askForm.markAllAsTouched();
      return;
    }
    this.asking.set(true);
    this.error.set(null);
    this.askProcessingMessage.set(null);
    const question = this.askForm.controls.question.value.trim();
    this.conversationsApi
      .ask(id, question, (status) => {
        this.askProcessingMessage.set(
          status.message?.trim() || DEFAULT_EMBEDDING_PROCESSING_MESSAGE,
        );
      })
      .subscribe({
        next: (result) => {
          this.asking.set(false);
          this.askProcessingMessage.set(null);
          this.askAnswer.set(result);
          this.notifySuccess('Resposta pronta.');
        },
        error: (err: unknown) => {
          this.asking.set(false);
          this.askProcessingMessage.set(null);
          this.setError(this.readActionError(err, 'Falha ao responder a pergunta.'));
        },
      });
  }

  loadMore(): void {
    const current = this.detail();
    if (!current) {
      return;
    }
    if (this.messages().length >= current.total_messages) {
      return;
    }
    this.fetchPage(this.messages().length, false);
  }

  highlightEvidence(evidenceId: string, messageId: string): void {
    void this.openEvidenceMessage(evidenceId, messageId);
  }

  closeEvidencePreview(): void {
    this.evidencePreviewMessage.set(null);
    this.evidencePreviewEvidenceId.set(null);
  }

  toggleAnalysisOnlyPanel(): void {
    this.analysisOnlyPanelOpen.update((open) => !open);
  }

  analysisOnlyPreview(message: ConversationMessage): string {
    const text = message.content.trim();
    if (!text || text === ANALYSIS_AUDIO_PLACEHOLDER) {
      return '(sem transcrição)';
    }
    return text.length > 140 ? `${text.slice(0, 140)}…` : text;
  }

  removeAnalysisMessage(messageId: string): void {
    const conversationId = this.conversationId();
    if (!conversationId || this.deletingAnalysisMessageId()) {
      return;
    }

    this.deletingAnalysisMessageId.set(messageId);
    this.error.set(null);
    this.conversationsApi.deleteAnalysisMessage(conversationId, messageId).subscribe({
      next: () => {
        this.deletingAnalysisMessageId.set(null);
        if (this.evidencePreviewMessage()?.id === messageId) {
          this.closeEvidencePreview();
        }
        this.loadAnalysisOnlyMessages();
        this.reload(true);
        this.loadExistingAnalysis();
      },
      error: (err: HttpErrorResponse) => {
        this.deletingAnalysisMessageId.set(null);
        this.analysisNeedsRefresh.set(true);
        this.error.set(this.readError(err, 'Falha ao excluir o áudio da análise.'));
      },
    });
  }

  isEvidencePreviewActive(evidenceId: string, messageId: string): boolean {
    return (
      this.evidencePreviewEvidenceId() === evidenceId &&
      this.evidencePreviewMessage()?.id === messageId
    );
  }

  isEvidencePreviewOpenFor(evidenceId: string): boolean {
    return this.evidencePreviewEvidenceId() === evidenceId;
  }

  isHiddenFromTimeline(message: ConversationMessage): boolean {
    return isAnalysisOnlyMessage(message.metadata);
  }

  analysisRemovalMessageId(message: ConversationMessage): string | null {
    if (isAnalysisOnlyMessage(message.metadata)) {
      return message.id;
    }
    const linked = message.metadata?.['linked_analysis_only_id'];
    return typeof linked === 'string' && linked ? linked : null;
  }

  uniqueEvidenceMessageIds(messageIds: string[]): string[] {
    return uniqueMessageIds(messageIds);
  }

  private async ensureAnalysisOnlyMessagesLoaded(): Promise<ConversationMessage[]> {
    if (this.analysisOnlyMessages().length > 0) {
      return this.analysisOnlyMessages();
    }
    const conversationId = this.conversationId();
    if (!conversationId) {
      return [];
    }
    const items = await firstValueFrom(
      this.conversationsApi.listAnalysisOnlyMessages(conversationId),
    );
    this.analysisOnlyMessages.set(items);
    return items;
  }

  private async openEvidenceMessage(evidenceId: string, messageId: string): Promise<void> {
    this.evidencePreviewLoading.set(true);
    this.error.set(null);

    try {
      const message = await this.resolveEvidenceMessage(messageId);
      if (!message) {
        this.error.set('Mensagem não encontrada nesta conversa.');
        this.closeEvidencePreview();
        return;
      }

      this.evidencePreviewEvidenceId.set(evidenceId);
      this.evidencePreviewMessage.set(message);
      this.scrollToInlineEvidencePreview(evidenceId);
    } catch (err: unknown) {
      this.error.set(this.readActionError(err, 'Falha ao abrir a mensagem da evidência.'));
    } finally {
      this.evidencePreviewLoading.set(false);
    }
  }

  private async resolveEvidenceMessage(messageId: string): Promise<ConversationMessage | null> {
    const conversationId = this.conversationId();
    if (!conversationId) {
      return null;
    }

    try {
      let message = await firstValueFrom(
        this.conversationsApi.getMessage(conversationId, messageId),
      );
      message = await this.enrichMessageWithTranscription(conversationId, message);
      this.upsertMessageInState(message);
      return message;
    } catch (err: unknown) {
      if (err instanceof HttpErrorResponse && err.status === 404) {
        return null;
      }
      throw err;
    }
  }

  private async enrichMessageWithTranscription(
    conversationId: string,
    message: ConversationMessage,
  ): Promise<ConversationMessage> {
    if (messageNeedsTranscriptionContent(message)) {
      const transcriptionId = message.metadata?.['transcription_id'];
      if (typeof transcriptionId !== 'string' || !transcriptionId) {
        return message;
      }

      const transcription = await firstValueFrom(
        this.conversationsApi.getAudioTranscription(conversationId, transcriptionId),
      );
      if (!transcription.transcribed_text?.trim()) {
        return message;
      }

      return {
        ...message,
        content: transcription.transcribed_text,
      };
    }

    if (isTimelineHiddenMediaMessage(message)) {
      await this.ensureAnalysisOnlyMessagesLoaded();
      const matched = findAnalysisOnlyForTimelineMessage(message, this.analysisOnlyMessages());
      if (matched) {
        const enriched = await this.enrichMessageWithTranscription(conversationId, matched);
        return {
          ...message,
          content: enriched.content,
          metadata: {
            ...message.metadata,
            linked_analysis_only_id: enriched.id,
            transcription_resolved: true,
          },
        };
      }
    }

    return message;
  }

  private upsertMessageInState(message: ConversationMessage): void {
    this.messages.update((items) => {
      const index = items.findIndex((item) => item.id === message.id);
      if (index === -1) {
        return [...items, message];
      }
      const next = [...items];
      next[index] = message;
      return next;
    });
  }

  private scrollToInlineEvidencePreview(evidenceId: string): void {
    requestAnimationFrame(() => {
      document.getElementById(`evidence-inline-preview-${evidenceId}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    });
  }

  canTranscribe(message: ConversationMessage): boolean {
    if (message.metadata?.['transcribed'] === true || message.metadata?.['linked_analysis_only_id']) {
      return false;
    }
    if (message.type !== 'AUDIO' && message.type !== 'MEDIA_OCULTA') {
      return false;
    }
    return message.metadata?.['transcribed'] !== true;
  }

  transcribeButtonLabel(message: ConversationMessage): string {
    return message.type === 'AUDIO' ? 'Transcrever' : 'Anexar áudio';
  }

  setAnalysisImportSender(participantId: string): void {
    this.analysisImportSenderId.set(participantId);
  }

  startPasteTranscription(messageId: string): void {
    this.pastingMessageId.set(messageId);
    this.pasteTranscriptionControl.reset('');
    this.error.set(null);
  }

  cancelPasteTranscription(): void {
    this.pastingMessageId.set(null);
    this.pasteTranscriptionControl.reset('');
  }

  submitPasteTranscription(): void {
    void this.submitPasteTranscriptionAsync();
  }

  private async submitPasteTranscriptionAsync(): Promise<void> {
    const conversationId = this.conversationId();
    const messageId = this.pastingMessageId();
    const text = this.pasteTranscriptionControl.value.trim();
    if (!conversationId || !messageId) {
      return;
    }
    if (!text) {
      this.pasteTranscriptionControl.markAsTouched();
      this.setError('Cole o texto da transcrição.');
      return;
    }

    this.savingManualTranscription.set(true);
    this.error.set(null);
    try {
      await firstValueFrom(
        this.conversationsApi.createManualTranscription(conversationId, {
          text,
          message_id: messageId,
        }),
      );
      this.cancelPasteTranscription();
      await this.reloadAsync(true);
      this.loadAnalysisOnlyMessages();
      this.analysisNeedsRefresh.set(true);
      this.loadExistingAnalysis();
      this.notifySuccess('Texto salvo na mídia.');
    } catch (err: unknown) {
      this.setError(this.readActionError(err, 'Falha ao salvar o texto na mensagem.'));
    } finally {
      this.savingManualTranscription.set(false);
    }
  }

  private async runAudioBatchImport(files: File[]): Promise<void> {
    if (!files.length) {
      return;
    }

    const conversationId = this.conversationId();
    const fallbackSenderId = this.resolveAnalysisImportFallbackSenderId();
    const participants = this.detail()?.participants ?? [];
    if (!conversationId || !fallbackSenderId) {
      this.analysisImportPhase.set(null);
      this.audioImportNotice.set(null);
      this.error.set(
        'Importe o chat primeiro (ou defina participantes) antes de enviar áudios soltos.',
      );
      return;
    }

    this.error.set(null);
    this.importPanelOpen.set(true);
    this.analysisImportPhase.set('uploading');

    try {
      const timelineMessages = await this.ensureAllMessagesLoaded();
      const analysisOnly = await this.ensureAnalysisOnlyMessagesLoaded();
      const byId = new Map<string, (typeof timelineMessages)[number]>();
      for (const message of [...timelineMessages, ...analysisOnly]) {
        byId.set(message.id, message);
      }
      this.analysisImportItems.set(
        buildAnalysisImportPlan(files, [...byId.values()], fallbackSenderId, participants),
      );
    } catch (err: unknown) {
      this.analysisImportPhase.set(null);
      this.error.set(this.readActionError(err, 'Falha ao preparar a importação de áudios.'));
      return;
    }

    const pendingItems = this.analysisImportItems().filter((item) => item.status === 'pending');
    const skippedCount = this.analysisImportItems().filter((item) => item.status === 'skipped').length;
    if (!pendingItems.length) {
      this.analysisImportPhase.set('done');
      this.publishAudioImportNotice(0, skippedCount, 0);
      return;
    }

    let hadFailure = false;
    let completedCount = 0;
    for (const item of pendingItems) {
      this.patchAnalysisImportItem(item.id, { status: 'uploading', errorMessage: null });
      try {
        const result = await firstValueFrom(
          item.matchedMessageId
            ? this.conversationsApi.uploadAudio(
                conversationId,
                item.matchedMessageId,
                item.file,
              )
            : this.conversationsApi.uploadAudioForAnalysis(
                conversationId,
                item.senderId,
                item.timestamp,
                item.file,
              ),
        );
        if (result.status === 'FAILED') {
          hadFailure = true;
          this.patchAnalysisImportItem(item.id, {
            status: 'failed',
            errorMessage: result.error_message || 'Falha ao transcrever o áudio.',
          });
          continue;
        }
        completedCount += 1;
        this.patchAnalysisImportItem(item.id, { status: 'completed', errorMessage: null });
      } catch (err: unknown) {
        hadFailure = true;
        this.patchAnalysisImportItem(item.id, {
          status: 'failed',
          errorMessage: this.readActionError(err, 'Falha ao importar o áudio.'),
        });
      }
    }

    const failedCount = this.analysisImportItems().filter((item) => item.status === 'failed').length;
    this.analysisImportPhase.set('done');
    this.publishAudioImportNotice(completedCount, skippedCount, failedCount);
    // Mantém o painel aberto: reload não deve fechar o resultado do lote.
    await this.reloadAsync(true);
    this.importPanelOpen.set(true);
    this.loadAnalysisOnlyMessages();
    this.analysisNeedsRefresh.set(completedCount > 0);
    if (completedCount > 0) {
      this.loadExistingAnalysis();
    }

    if (hadFailure) {
      this.error.set(
        'Alguns áudios não foram transcritos. Tente novamente os que falharam e depois reanalise.',
      );
    }
  }

  private publishAudioImportNotice(completed: number, skipped: number, failed: number): void {
    const message = `Áudios: ${completed} novos · ${skipped} já existiam · ${failed} falha(s).`;
    this.audioImportNotice.set(null);
    this.importPanelOpen.set(true);
    if (failed > 0) {
      this.notifyError(message);
    } else {
      this.notifySuccess(message);
    }
  }

  retryFailedAnalysisImports(): void {
    void this.retryFailedAnalysisImportsAsync();
  }

  private async retryFailedAnalysisImportsAsync(): Promise<void> {
    const conversationId = this.conversationId();
    if (!conversationId || this.analysisImportPhase() === 'uploading') {
      return;
    }

    const failedItems = this.analysisImportItems().filter((item) => item.status === 'failed');
    if (!failedItems.length) {
      return;
    }

    this.analysisImportPhase.set('uploading');
    this.error.set(null);
    let hadFailure = false;

    for (const item of failedItems) {
      this.patchAnalysisImportItem(item.id, { status: 'uploading', errorMessage: null });
      try {
        const result = await firstValueFrom(
          item.matchedMessageId
            ? this.conversationsApi.uploadAudio(
                conversationId,
                item.matchedMessageId,
                item.file,
              )
            : this.conversationsApi.uploadAudioForAnalysis(
                conversationId,
                item.senderId,
                item.timestamp,
                item.file,
              ),
        );
        if (result.status === 'FAILED') {
          hadFailure = true;
          this.patchAnalysisImportItem(item.id, {
            status: 'failed',
            errorMessage: result.error_message || 'Falha ao transcrever o áudio.',
          });
          continue;
        }
        this.patchAnalysisImportItem(item.id, { status: 'completed', errorMessage: null });
      } catch (err: unknown) {
        hadFailure = true;
        this.patchAnalysisImportItem(item.id, {
          status: 'failed',
          errorMessage: this.readActionError(err, 'Falha ao importar o áudio.'),
        });
      }
    }

    this.analysisImportPhase.set('done');
    const skipped = this.analysisImportItems().filter((item) => item.status === 'skipped').length;
    const completed = this.analysisImportItems().filter((item) => item.status === 'completed').length;
    const failed = this.analysisImportItems().filter((item) => item.status === 'failed').length;
    this.publishAudioImportNotice(completed, skipped, failed);
    await this.reloadAsync(true);
    this.importPanelOpen.set(true);
    if (hadFailure) {
      this.error.set('Ainda há áudios com falha na transcrição.');
    }
  }

  dismissAnalysisImportPanel(): void {
    if (this.analysisImportPhase() === 'uploading') {
      return;
    }
    this.retainImportPanel = false;
    this.analysisImportItems.set([]);
    this.analysisImportPhase.set(null);
    this.audioImportNotice.set(null);
  }

  analysisImportStatusLabel(status: AnalysisImportStatus): string {
    return analysisImportStatusLabel(status);
  }

  trackAnalysisImportItem(_index: number, item: AnalysisImportItem): string {
    return item.id;
  }

  analysisImportSenderHint(item: AnalysisImportItem): string {
    return formatAnalysisImportSenderHint(item);
  }

  audioInputElementId(): string {
    return this.audioInputId;
  }

  startAudioUpload(messageId: string): void {
    this.pendingAudioMessageId.set(messageId);
    document.getElementById(this.audioInputId)?.click();
  }

  onAudioFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    const messageId = this.pendingAudioMessageId();
    const conversationId = this.conversationId();
    input.value = '';
    this.pendingAudioMessageId.set(null);
    if (!file || !messageId || !conversationId) {
      return;
    }
    this.transcribingMessageId.set(messageId);
    this.transcriptionProcessingMessage.set(null);
    this.error.set(null);
    this.conversationsApi
      .uploadAudio(conversationId, messageId, file, (status) => {
        this.transcriptionProcessingMessage.set(
          status.error_message?.trim() ||
            (status.status === 'PROCESSING' ? DEFAULT_TRANSCRIPTION_PROCESSING_MESSAGE : null),
        );
      })
      .subscribe({
        next: (result) => {
          this.transcribingMessageId.set(null);
          this.transcriptionProcessingMessage.set(null);
          if (result.status === 'FAILED') {
            this.setError(result.error_message || 'Falha ao transcrever o áudio.');
            return;
          }
          this.analysis.set(null);
          this.analysisInsights.set(null);
          this.resetInterestState();
          this.askAnswer.set(null);
          this.analysisNeedsRefresh.set(true);
          this.reload(true);
          this.notifySuccess('Áudio transcrito e vinculado à mensagem.');
        },
        error: (err: unknown) => {
          this.transcribingMessageId.set(null);
          this.transcriptionProcessingMessage.set(null);
          this.setError(this.readActionError(err, 'Falha ao enviar o áudio para transcrição.'));
        },
      });
  }

  interestLevelLabel(level: InterestLevel | null | undefined): string {
    const labels: Record<InterestLevel, string> = {
      MUITO_BAIXO: 'Muito baixo',
      BAIXO: 'Baixo',
      MODERADO: 'Moderado',
      ALTO: 'Alto',
      MUITO_ALTO: 'Muito alto',
    };
    return level ? labels[level] : '—';
  }

  generateSuggestions(): void {
    const id = this.conversationId();
    if (!id || this.suggestionsForm.invalid) {
      this.suggestionsForm.markAllAsTouched();
      return;
    }
    const incomingMessage = this.suggestionsForm.controls.incomingMessage.value.trim();
    if (!incomingMessage) {
      this.suggestionsForm.controls.incomingMessage.setErrors({ required: true });
      return;
    }
    this.generatingSuggestions.set(true);
    this.error.set(null);
    this.suggestions.set([]);
    this.conversationsApi.generateSuggestions(id, { incoming_message: incomingMessage }).subscribe({
      next: (result) => {
        this.generatingSuggestions.set(false);
        this.suggestions.set(result.suggestions);
        this.notifySuccess(
          result.suggestions.length
            ? `${result.suggestions.length} sugestões geradas.`
            : 'Nenhuma sugestão gerada.',
        );
      },
      error: (err: unknown) => {
        this.generatingSuggestions.set(false);
        this.setError(this.readActionError(err, 'Falha ao gerar sugestões de resposta.'));
      },
    });
  }

  copySuggestion(suggestion: SuggestionRead): void {
    navigator.clipboard.writeText(suggestion.suggested_text).then(() => {
      this.copiedSuggestionId.set(suggestion.id);
      this.notifySuccess('Sugestão copiada.');
      setTimeout(() => this.copiedSuggestionId.set(null), 2000);
    });
  }

  categoryLabel(category: string): string {
    const labels: Record<string, string> = {
      NATURAL: 'Natural',
      DIVERTIDA: 'Divertida',
      DIRETA: 'Direta',
      CONSERVADORA: 'Conservadora',
    };
    return labels[category] ?? category;
  }

  participantLabel(participant: Participant): string {
    return participant.role === 'OWNER' ? `${participant.name} (você)` : participant.name;
  }

  private setError(message: string): void {
    this.error.set(message);
    this.notifyError(message);
  }

  private notifySuccess(message: string): void {
    this.snackBar.open(message, 'OK', {
      duration: 4500,
      horizontalPosition: 'center',
      verticalPosition: 'top',
      panelClass: ['aca-toast-success'],
    });
  }

  private notifyError(message: string): void {
    this.snackBar.open(message, 'OK', {
      duration: 7000,
      horizontalPosition: 'center',
      verticalPosition: 'top',
      panelClass: ['aca-toast-error'],
    });
  }

  private conversationId(): string | null {
    return this.route.snapshot.paramMap.get('id');
  }

  private reload(resetMessages: boolean): void {
    void this.reloadAsync(resetMessages);
  }

  private reloadAsync(resetMessages: boolean): Promise<void> {
    return this.fetchPageAsync(0, resetMessages);
  }

  private fetchPage(offset: number, reset: boolean): void {
    void this.fetchPageAsync(offset, reset);
  }

  private fetchPageAsync(offset: number, reset: boolean): Promise<void> {
    const id = this.conversationId();
    if (!id) {
      this.error.set('Conversa não encontrada.');
      return Promise.resolve();
    }
    return firstValueFrom(this.conversationsApi.get(id, offset, this.pageSize))
      .then((detail) => {
        this.detail.set(detail);
        this.messages.set(reset ? detail.messages : [...this.messages(), ...detail.messages]);
        this.error.set(null);
        if (reset && !this.retainImportPanel) {
          const empty = detail.total_messages === 0;
          this.importPanelOpen.set(empty);
          if (empty) {
            this.activeTab.set('conversa');
          }
        }
        if (!this.analysisImportSenderId() && this.otherParticipants().length === 1) {
          this.analysisImportSenderId.set(this.otherParticipants()[0].id);
        }
      })
      .catch((err: unknown) => {
        this.error.set(
          err instanceof HttpErrorResponse
            ? this.readError(err, 'Falha ao carregar a conversa.')
            : 'Falha ao carregar a conversa.',
        );
      });
  }

  private loadAnalysisOnlyMessages(): void {
    const id = this.conversationId();
    if (!id) {
      return;
    }
    this.conversationsApi.listAnalysisOnlyMessages(id).subscribe({
      next: (items) => {
        this.analysisOnlyMessages.set(items);
        if (!items.length) {
          this.analysisOnlyPanelOpen.set(false);
        }
      },
      error: () => this.analysisOnlyMessages.set([]),
    });
  }

  private loadExistingAnalysis(): void {
    const id = this.conversationId();
    if (!id) {
      return;
    }
    this.conversationsApi.getAnalysis(id).subscribe({
      next: (result) => {
        this.applyAnalysisResult(result);
      },
      error: () => {
        this.analysis.set(null);
        this.resetInterestState();
        this.summaryStale.set(false);
        this.analysisCachedNotice.set(null);
      },
    });
  }

  private loadTimeline(): void {
    const id = this.conversationId();
    if (!id) {
      return;
    }
    this.conversationsApi.getTimeline(id).subscribe({
      next: (result) => this.timeline.set(result.periods),
      error: () => this.timeline.set([]),
    });
  }

  private applyAnalysisResult(result: AnalyzeResponse): void {
    this.analysis.set(result.analysis);
    this.analysisInsights.set({
      observations: result.observations ?? [],
      inferences: result.inferences ?? [],
    });
    this.applyInterestResult(result);
    this.summaryStale.set(result.summary_stale ?? false);
    this.analysisNeedsRefresh.set(false);
    this.analysisCachedNotice.set(null);
    this.loadTimeline();
  }

  private applyInterestResult(result: AnalyzeResponse): void {
    this.interestLevel.set(result.interest_level ?? result.analysis.interest_level ?? null);
    this.interestScore.set(result.interest_score ?? result.analysis.interest_score ?? null);
    this.confidenceScore.set(result.confidence_score ?? result.analysis.confidence_score ?? null);
    this.positiveSignals.set(result.positive_signals ?? []);
    this.neutralSignals.set(result.neutral_signals ?? []);
    this.negativeSignals.set(result.negative_signals ?? []);
    this.evidence.set(result.evidence ?? []);
  }

  private resetInterestState(): void {
    this.interestLevel.set(null);
    this.interestScore.set(null);
    this.confidenceScore.set(null);
    this.positiveSignals.set([]);
    this.neutralSignals.set([]);
    this.negativeSignals.set([]);
    this.evidence.set([]);
    this.timeline.set([]);
    this.highlightedMessageId.set(null);
    this.closeEvidencePreview();
  }

  private readActionError(err: unknown, fallback: string): string {
    if (err instanceof ProcessingPollTimeoutError) {
      return err.message;
    }
    if (err instanceof HttpErrorResponse) {
      return this.readError(err, fallback);
    }
    return fallback;
  }

  private readError(err: HttpErrorResponse, fallback: string): string {
    if (typeof err.error?.detail === 'string') {
      return err.error.detail;
    }
    return fallback;
  }

  private patchAnalysisImportItem(itemId: string, patch: Partial<AnalysisImportItem>): void {
    this.analysisImportItems.update((items) =>
      items.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
    );
  }

  private async ensureMessageLoaded(messageId: string): Promise<ConversationMessage | null> {
    const existing = this.messages().find((message) => message.id === messageId);
    if (existing) {
      return existing;
    }

    const conversationId = this.conversationId();
    if (!conversationId) {
      return null;
    }

    const fetchLimit = 200;
    let loaded = [...this.messages()];
    let total = this.detail()?.total_messages ?? loaded.length;

    while (loaded.length < total) {
      const detail = await firstValueFrom(
        this.conversationsApi.get(conversationId, loaded.length, fetchLimit),
      );
      loaded = [...loaded, ...detail.messages];
      total = detail.total_messages;
      const found = loaded.find((message) => message.id === messageId);
      this.messages.set(loaded);
      this.detail.set({ ...detail, messages: loaded });
      if (found) {
        return found;
      }
    }

    return loaded.find((message) => message.id === messageId) ?? null;
  }

  private resolveAnalysisImportFallbackSenderId(): string | null {
    const selected = this.analysisImportSenderId();
    if (selected) {
      return selected;
    }
    const participants = this.detail()?.participants ?? [];
    const other = participants.find((participant) => participant.role !== 'OWNER');
    if (other) {
      return other.id;
    }
    return participants[0]?.id ?? null;
  }

  private async ensureAllMessagesLoaded(): Promise<ConversationMessage[]> {
    const conversationId = this.conversationId();
    if (!conversationId) {
      throw new Error('Conversa não encontrada.');
    }

    const fetchLimit = 200;
    let loaded = [...this.messages()];
    let total = this.detail()?.total_messages ?? loaded.length;

    while (loaded.length < total) {
      const detail = await firstValueFrom(
        this.conversationsApi.get(conversationId, loaded.length, fetchLimit),
      );
      loaded = [...loaded, ...detail.messages];
      total = detail.total_messages;
      this.detail.set({ ...detail, messages: loaded });
    }

    this.messages.set(loaded);
    return loaded;
  }
}

function isChatExportFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith('.txt') || name.endsWith('.zip') || file.type === 'application/zip';
}

function isAudioUpdateFile(file: File): boolean {
  if (isChatExportFile(file)) {
    return false;
  }
  const name = file.name.toLowerCase();
  return (
    name.endsWith('.opus') ||
    name.endsWith('.ogg') ||
    name.endsWith('.mp3') ||
    name.endsWith('.m4a') ||
    name.endsWith('.wav') ||
    name.endsWith('.aac') ||
    name.endsWith('.amr') ||
    file.type.startsWith('audio/')
  );
}

function pickChatExportFile(files: File[]): File | null {
  const zip = files.find((file) => file.name.toLowerCase().endsWith('.zip'));
  if (zip) {
    return zip;
  }
  return files.find((file) => file.name.toLowerCase().endsWith('.txt')) ?? null;
}
