import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Conversation } from '../../core/models/api.models';
import { ConversationService } from '../../core/services/conversation.service';

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
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);

  readonly items = signal<Conversation[]>([]);
  readonly error = signal<string | null>(null);
  readonly creating = signal(false);
  readonly importWelcome = signal(false);

  readonly form = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
  });

  ngOnInit(): void {
    this.importWelcome.set(this.route.snapshot.queryParamMap.get('import') === '1');
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
      next: () => {
        this.form.reset({ title: '' });
        this.creating.set(false);
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

  private reload(): void {
    this.conversationsApi.list().subscribe({
      next: (result) => this.items.set(result.items),
      error: () => this.error.set('Falha ao carregar conversas.'),
    });
  }
}
