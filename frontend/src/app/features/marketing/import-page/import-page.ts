import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { PendingImportService } from '../../../core/services/pending-import.service';
import { PhotoComponent } from '../../../shared/photo/photo';

@Component({
  selector: 'app-import-page',
  imports: [RouterLink, PhotoComponent],
  templateUrl: './import-page.html',
  styleUrl: './import-page.scss',
})
export class ImportPageComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly pendingImport = inject(PendingImportService);

  readonly selectedFile = signal<File | null>(null);
  readonly consent = signal(false);
  readonly dragOver = signal(false);
  readonly pendingError = signal<string | null>(null);
  readonly savingFile = signal(false);

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    void this.rememberFile(input.files?.[0] ?? null);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    void this.rememberFile(event.dataTransfer?.files?.[0] ?? null);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  async startAnalysis(): Promise<void> {
    if (!this.consent() || this.savingFile()) {
      return;
    }
    this.pendingError.set(null);
    const file = this.selectedFile();
    if (file) {
      this.savingFile.set(true);
      try {
        await this.pendingImport.save(file);
      } catch (err: unknown) {
        this.savingFile.set(false);
        this.pendingError.set(
          err instanceof Error ? err.message : 'Não foi possível guardar o arquivo.',
        );
        return;
      }
      this.savingFile.set(false);
    }

    if (this.auth.isAuthenticated()) {
      void this.router.navigate(['/conversations'], {
        queryParams: { import: '1', auto: '1' },
      });
      return;
    }

    void this.router.navigate(['/register'], { queryParams: { next: 'import' } });
  }

  private async rememberFile(file: File | null): Promise<void> {
    this.selectedFile.set(file);
    this.pendingError.set(null);
    if (!file) {
      return;
    }
    this.savingFile.set(true);
    try {
      await this.pendingImport.save(file);
    } catch (err: unknown) {
      this.pendingError.set(
        err instanceof Error ? err.message : 'Não foi possível guardar o arquivo.',
      );
    } finally {
      this.savingFile.set(false);
    }
  }
}
