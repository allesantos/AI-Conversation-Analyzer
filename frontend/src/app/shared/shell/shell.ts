import { Component, OnInit, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService, DEMO_CONTACT_EMAIL } from '../../core/services/auth.service';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class ShellComponent implements OnInit {
  readonly auth = inject(AuthService);
  readonly year = new Date().getFullYear();
  readonly contactEmail = DEMO_CONTACT_EMAIL;
  readonly contactMailto = `mailto:${DEMO_CONTACT_EMAIL}?subject=Liberação%20Analyzer%20demo`;

  readonly quotaLabel = computed(() => {
    const quota = this.auth.user()?.demo_quota;
    if (!quota || quota.unlimited || !this.auth.hasAiAccess()) {
      return null;
    }
    const llmLeft = Math.max(0, quota.llm_limit - quota.llm_used);
    const audioLeftMin = Math.max(0, (quota.audio_seconds_limit - quota.audio_seconds_used) / 60);
    return (
      `Cota demo deste mês: ${llmLeft}/${quota.llm_limit} usos de IA restantes · ` +
      `${audioLeftMin.toFixed(1)}/${(quota.audio_seconds_limit / 60).toFixed(0)} min de áudio restantes`
    );
  });

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.auth.refreshMe().subscribe({ error: () => undefined });
    }
  }
}
