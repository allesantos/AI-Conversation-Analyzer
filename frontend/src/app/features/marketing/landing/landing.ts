import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { PhotoComponent } from '../../../shared/photo/photo';

@Component({
  selector: 'app-landing',
  imports: [RouterLink, PhotoComponent],
  templateUrl: './landing.html',
  styleUrl: './landing.scss',
})
export class LandingComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly selectedFile = signal<File | null>(null);
  readonly consent = signal(false);
  readonly dragOver = signal(false);

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile.set(input.files?.[0] ?? null);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.selectedFile.set(file);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  startAnalysis(): void {
    if (!this.consent()) {
      return;
    }
    const file = this.selectedFile();
    if (this.auth.isAuthenticated()) {
      sessionStorage.setItem('aca.pendingImportName', file?.name ?? '');
      this.router.navigate(['/conversations'], { queryParams: { import: '1' } });
      return;
    }
    if (file) {
      sessionStorage.setItem('aca.pendingImportName', file.name);
    }
    this.router.navigate(['/register'], { queryParams: { next: 'import' } });
  }
}
