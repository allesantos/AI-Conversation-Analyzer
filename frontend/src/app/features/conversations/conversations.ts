import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { firstValueFrom } from 'rxjs';
import { Conversation } from '../../core/models/api.models';
import { ConversationService } from '../../core/services/conversation.service';
import { PendingImportService } from '../../core/services/pending-import.service';

@Component({
  selector: 'app-conversations',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './conversations.html',
  styleUrl: './conversations.scss',
})
export class ConversationsComponent implements OnInit {
  private readonly conversationsApi = inject(ConversationService);
  private readonly pendingImport = inject(PendingImportService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly items = signal<Conversation[]>([]);
  readonly error = signal<string | null>(null);
  readonly creating = signal(false);
  readonly importWelcome = signal(false);
  readonly pendingFileName = signal<string | null>(null);
  readonly autoImporting = signal(false);

  readonly form = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
  });

  ngOnInit(): void {
    const wantsImport = this.route.snapshot.queryParamMap.get('import') === '1';
    const auto = this.route.snapshot.queryParamMap.get('auto') === '1';
    this.importWelcome.set(wantsImport);
    void this.bootstrapPending(wantsImport, auto);
    this.reload();
  }

  create(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.creating.set(true);
    this.error.set(null);
    this.conversationsApi.create(this.form.controls.title.value.trim()).subscribe({
      next: (conversation) => {
        this.form.reset({ title: '' });
        this.creating.set(false);
        if (this.pendingFileName()) {
          void this.router.navigate(['/conversations', conversation.id], {
            queryParams: { pendingImport: '1' },
          });
          return;
        }
        this.reload();
      },
      error: (err: HttpErrorResponse) => {
        this.creating.set(false);
        this.error.set(
          typeof err.error?.detail === 'string' ? err.error.detail : 'Falha ao criar conversa.',
        );
      },
    });
  }

  remove(event: Event, conversation: Conversation): void {
    event.preventDefault();
    event.stopPropagation();
    this.conversationsApi.delete(conversation.id).subscribe({
      next: () => this.reload(),
      error: () => this.error.set('Falha ao excluir conversa.'),
    });
  }

  private async bootstrapPending(wantsImport: boolean, auto: boolean): Promise<void> {
    const name = await this.pendingImport.peekName();
    this.pendingFileName.set(name);
    if (!wantsImport || !auto || !name) {
      return;
    }
    this.autoImporting.set(true);
    this.error.set(null);
    const title = name.replace(/\.(txt|zip)$/i, '').slice(0, 200) || 'Nova conversa';
    try {
      const conversation = await firstValueFrom(this.conversationsApi.create(title));
      this.autoImporting.set(false);
      void this.router.navigate(['/conversations', conversation.id], {
        queryParams: { pendingImport: '1' },
      });
    } catch (err: unknown) {
      this.autoImporting.set(false);
      this.error.set(
        err instanceof HttpErrorResponse && typeof err.error?.detail === 'string'
          ? err.error.detail
          : 'Falha ao preparar a importação automática.',
      );
    }
  }

  private reload(): void {
    this.conversationsApi.list().subscribe({
      next: (result) => this.items.set(result.items),
      error: () => this.error.set('Falha ao carregar conversas.'),
    });
  }
}
